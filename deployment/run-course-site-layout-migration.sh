#!/usr/bin/env bash
set -Eeuo pipefail

# Runs on the Sakai VM, triggered through the tracked Quartz AutoRun hook.
TOMCAT_HOME='/opt/tomcat'
PROPERTIES="$TOMCAT_HOME/sakai/local.properties"
LOG="$TOMCAT_HOME/logs/catalina.out"

[[ $# -ge 1 ]] || { echo 'Pass one or more explicit Sakai course site IDs.' >&2; exit 2; }
for site_id in "$@"; do
  [[ "$site_id" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Invalid site ID.' >&2; exit 2; }
done

exec 9>/opt/sakai-releases/.lock
flock -n 9 || { echo 'Another Sakai release or migration is running.' >&2; exit 1; }

sudo test -r "$PROPERTIES" || { echo "Missing $PROPERTIES" >&2; exit 1; }
if ! sudo test -e "$PROPERTIES.pre-course-layout-migration"; then
  sudo cp -a "$PROPERTIES" "$PROPERTIES.pre-course-layout-migration"
fi

disable_trigger() {
  sudo sed -i '/^quartz\.course\.layout\.migration\.autorun=/d;/^course\.site\.layout\.migration\.siteids=/d' "$PROPERTIES"
}
# Even a failed attempt must not retry unexpectedly on a later restart.
trap disable_trigger EXIT

site_ids=$(IFS=,; printf '%s' "$*")
sudo sed -i '/^quartz\.course\.layout\.migration\.autorun=/d;/^course\.site\.layout\.migration\.siteids=/d' "$PROPERTIES"
printf 'quartz.course.layout.migration.autorun=true\ncourse.site.layout.migration.siteids=%s\n' "$site_ids" \
  | sudo tee -a "$PROPERTIES" >/dev/null
start_line=$(sudo sh -c "wc -l < '$LOG'")

sudo systemctl restart tomcat

# Include the scheduler's five-minute delay and the job's registration wait.
for _ in {1..180}; do
  new_log=$(sudo tail -n +"$((start_line + 1))" "$LOG")
  failed=false
  completed=0
  if grep -Fq 'Could not configure standard course Student roster template' <<<"$new_log" \
      || grep -Fq 'Required standard course tools did not all register' <<<"$new_log"; then
    failed=true
  fi
  for site_id in "$@"; do
    if grep -Eq "Could not apply standard course setup v2 for site ${site_id}$" <<<"$new_log"; then
      failed=true
    elif grep -Eq "Standard course setup v2 complete for site ${site_id}$" <<<"$new_log"; then
      completed=$((completed + 1))
    fi
  done
  if [[ "$failed" == true ]]; then
    echo 'Course layout migration reported an error; inspect the Tomcat log; the temporary trigger will be disabled.' >&2
    exit 1
  fi
  if [[ "$completed" -eq "$#" ]] && systemctl is-active --quiet tomcat \
      && curl --fail --silent --max-time 10 --output /dev/null http://127.0.0.1:8080/portal; then
    disable_trigger
    echo "Course layout v2 and Student roster setup completed for $completed explicitly selected course sites; autorun disabled."
    exit 0
  fi
  sleep 10
done

echo 'Timed out waiting for the scoped course layout migration; inspect the Tomcat log; the temporary trigger will be disabled.' >&2
exit 1
