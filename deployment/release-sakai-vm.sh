#!/usr/bin/env bash
set -Eeuo pipefail

# Runs on vm-sakai-dev as root. It never modifies the database or sakai/local.properties.
TOMCAT_HOME='/opt/tomcat'
RELEASES='/opt/sakai-releases'
BASELINE_SHA='b5b7800f0fcddf9d0db47276a66065189365d905'
MAVEN='/opt/maven/bin/mvn'
ARTIFACT_DIRS=(webapps components lib)

die() { echo "Error: $*" >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || die 'Run this script with sudo.'
[[ $# -ge 1 ]] || die 'Usage: release-sakai-vm.sh preflight | deploy SHA SHA256 ARCHIVE RELEASE_ID | rollback RELEASE_ID'
command -v flock >/dev/null || die 'flock is required.'
install -d -m 0750 "$RELEASES"
exec 9>"$RELEASES/.lock"
flock -n 9 || die 'Another Sakai release operation is already running.'

check_vm() {
  local name
  [[ -x "$MAVEN" ]] || die 'VM Maven installation is missing.'
  [[ "$(df -BG --output=avail /opt | tail -1 | tr -d ' G')" -ge 12 ]] || \
    die 'At least 12 GiB free under /opt is required.'
  for name in "${ARTIFACT_DIRS[@]}"; do
    [[ -d "$TOMCAT_HOME/$name" ]] || die "Tomcat $name directory is missing."
  done
  [[ -f "$TOMCAT_HOME/sakai/local.properties" ]] || die 'Runtime properties are missing.'
}

wait_for_portal() {
  local attempt
  for attempt in {1..60}; do
    if systemctl is-active --quiet tomcat && \
      curl --fail --silent --max-time 10 --output /dev/null \
        'http://127.0.0.1:8080/portal'; then
      return 0
    fi
    sleep 15
  done
  return 1
}

restore_backup() {
  local release="$1" name
  install -d -m 0750 "$release/failed"
  systemctl stop tomcat || true
  for name in "${ARTIFACT_DIRS[@]}"; do
    if [[ -d "$release/backup/$name" ]]; then
      if [[ -e "$TOMCAT_HOME/$name" ]]; then
        mv "$TOMCAT_HOME/$name" "$release/failed/$name"
      fi
      mv "$release/backup/$name" "$TOMCAT_HOME/$name"
    fi
  done
  if [[ -f "$release/previous-current" ]]; then
    cp "$release/previous-current" "$RELEASES/current"
  fi
  systemctl start tomcat
  wait_for_portal || die 'Previous Tomcat files were restored, but the portal did not become healthy.'
  printf '%s\n' rolled-back > "$release/status"
  echo "Rolled back release ${release##*/}."
}

case "$1" in
  preflight)
    [[ $# -eq 1 ]] || die 'preflight accepts no arguments.'
    check_vm
    echo 'VM Maven, disk space, Tomcat application directories, and runtime properties are ready.'
    ;;
  deploy)
    [[ $# -eq 5 ]] || die 'deploy requires SHA, archive SHA256, archive path, and release ID.'
    commit="$2"; expected_hash="$3"; archive="$4"; release_id="$5"
    [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die 'Invalid commit SHA.'
    [[ "$expected_hash" =~ ^[0-9a-f]{64}$ ]] || die 'Invalid archive SHA256.'
    [[ "$release_id" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$ ]] || die 'Invalid release ID.'
    [[ "${release_id: -12}" == "${commit:0:12}" ]] || die 'Release ID does not match commit.'
    [[ "$archive" =~ ^/var/tmp/sakai-release\.[A-Za-z0-9]{8}/source\.tar\.gz$ ]] || \
      die 'Unexpected archive path.'
    [[ -f "$archive" ]] || die 'Source archive is missing.'
    check_vm
    release="$RELEASES/$release_id"
    [[ ! -e "$release" ]] || die "Release $release_id already exists; choose a new release ID."

    printf '%s  %s\n' "$expected_hash" "$archive" | sha256sum --check --status || \
      die 'Source archive checksum mismatch.'
    install -d -m 0750 "$release/source" "$release/staged-tomcat" "$release/backup"
    tar -xzf "$archive" --strip-components=2 -C "$release/source" apps/sakai
    [[ -f "$release/source/pom.xml" ]] || die 'Archive contains no Sakai POM.'
    printf '%s\n' "$commit" > "$release/commit"
    if [[ -f "$RELEASES/current" ]]; then
      cp "$RELEASES/current" "$release/previous-current"
    else
      printf 'baseline %s\n' "$BASELINE_SHA" > "$release/previous-current"
    fi
    printf '%s\n' preparing > "$release/status"
    chown -R tomcat:tomcat "$release/source" "$release/staged-tomcat"

    stopped=0
    on_exit() {
      local result=$?
      trap - EXIT
      if [[ "$result" -ne 0 && "$stopped" -eq 1 ]]; then
        echo 'Release failed; restoring the previous Tomcat installation...' >&2
        if ! restore_backup "$release"; then
          echo "Automatic rollback failed. Inspect $release and the Tomcat service now." >&2
        fi
      fi
      exit "$result"
    }
    trap on_exit EXIT

    echo 'Stopping Tomcat to leave enough RAM for the Sakai build...'
    stopped=1
    systemctl stop tomcat
    for name in "${ARTIFACT_DIRS[@]}"; do
      cp -a "$TOMCAT_HOME/$name" "$release/staged-tomcat/$name"
    done
    chown -R tomcat:tomcat "$release/staged-tomcat"
    touch "$release/build.log"
    chown tomcat:tomcat "$release/build.log"

    echo "Building Sakai $commit (log: $release/build.log)..."
    if ! sudo -u tomcat -H env MAVEN_OPTS='-Xms512m -Xmx3072m' \
      "$MAVEN" -B -ntp -DskipTests -f "$release/source/master/pom.xml" clean install \
      >> "$release/build.log" 2>&1; then
      tail -n 80 "$release/build.log" >&2
      die 'Sakai parent build failed.'
    fi
    if ! sudo -u tomcat -H env MAVEN_OPTS='-Xms512m -Xmx3072m' \
      "$MAVEN" -B -ntp -DskipTests -f "$release/source/pom.xml" clean install sakai:deploy \
      "-Dmaven.tomcat.home=$release/staged-tomcat" \
      "-Dsakai.home=$TOMCAT_HOME/sakai" >> "$release/build.log" 2>&1; then
      tail -n 80 "$release/build.log" >&2
      die 'Sakai application build or staging failed.'
    fi
    [[ -f "$release/staged-tomcat/lib/mysql-connector-j-9.0.0.jar" ]] || \
      die 'Staged Tomcat is missing the MySQL JDBC driver.'

    # Force Tomcat to expand updated WARs instead of retaining old exploded copies.
    while IFS= read -r -d '' war; do
      expanded="${war%.war}"
      if [[ -d "$expanded" ]]; then
        rm -rf -- "$expanded"
      fi
    done < <(find "$release/staged-tomcat/webapps" -maxdepth 1 -type f -name '*.war' -print0)

    # Keep the first-install Sakai 25.2 lifecycle fix after Maven re-deploys this component.
    demo_component="$release/staged-tomcat/components/coursemanagement-hibernate-pack/WEB-INF/components-demo.xml"
    if [[ -f "$demo_component" ]] && \
      ! grep -q 'depends-on="org.sakaiproject.user.api.UserDirectoryService"' "$demo_component"; then
      sed -i 's#<bean id="org.sakaiproject.coursemanagement.impl.CourseManagementSampleDataLoader"#<bean depends-on="org.sakaiproject.user.api.UserDirectoryService" id="org.sakaiproject.coursemanagement.impl.CourseManagementSampleDataLoader"#' "$demo_component"
    fi

    printf '%s\n' built > "$release/status"
    echo 'Build succeeded. Switching Tomcat application directories...'
    for name in "${ARTIFACT_DIRS[@]}"; do
      mv "$TOMCAT_HOME/$name" "$release/backup/$name"
      mv "$release/staged-tomcat/$name" "$TOMCAT_HOME/$name"
    done
    systemctl start tomcat
    if ! wait_for_portal; then
      journalctl -u tomcat -n 80 --no-pager >&2 || true
      die 'Portal health check failed after deployment.'
    fi
    printf '%s %s\n' "$release_id" "$commit" > "$RELEASES/current"
    printf '%s\n' healthy > "$release/status"
    stopped=0
    trap - EXIT
    echo "RELEASE_ID=$release_id"
    echo 'Local portal health check passed.'
    ;;
  rollback)
    [[ $# -eq 2 ]] || die 'rollback requires a release ID.'
    release_id="$2"
    [[ "$release_id" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$ ]] || die 'Invalid release ID.'
    release="$RELEASES/$release_id"
    [[ -f "$release/status" ]] || die "Unknown release $release_id."
    [[ -f "$RELEASES/current" ]] || die 'No current release record exists.'
    read -r current_id _ < "$RELEASES/current"
    [[ "$current_id" == "$release_id" ]] || \
      die "Only the current release can be rolled back (current: $current_id)."
    for name in "${ARTIFACT_DIRS[@]}"; do
      [[ -d "$release/backup/$name" ]] || die "Missing rollback copy of $name."
    done
    restore_backup "$release"
    ;;
  *) die 'Unknown operation.' ;;
esac
