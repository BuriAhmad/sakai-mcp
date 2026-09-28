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

sudo test -r "$PROPERTIES" || { echo "Missing $PROPERTIES" >&2; exit 1; }
if ! sudo test -e "$PROPERTIES.pre-course-layout-migration"; then
  sudo cp -a "$PROPERTIES" "$PROPERTIES.pre-course-layout-migration"
fi

site_ids=$(IFS=,; printf '%s' "$*")
sudo sed -i '/^quartz\.course\.layout\.migration\.autorun=/d;/^course\.site\.layout\.migration\.siteids=/d' "$PROPERTIES"
printf 'quartz.course.layout.migration.autorun=true\ncourse.site.layout.migration.siteids=%s\n' "$site_ids" \
  | sudo tee -a "$PROPERTIES" >/dev/null
start_line=$(sudo sh -c "wc -l < '$LOG'")

sudo systemctl restart tomcat

for _ in {1..90}; do
  new_log=$(sudo tail -n +"$((start_line + 1))" "$LOG")
  failed=false
  completed=0
  for site_id in "$@"; do
    if grep -Fq "Could not standardize course layout for site $site_id" <<<"$new_log" \
        || grep -Fq "Refusing course-layout migration for non-course or template site $site_id" <<<"$new_log" \
        || grep -Fq "Requested course-layout migration site was not found: $site_id" <<<"$new_log"; then
      failed=true
    elif grep -Fq "Standardized course navigation for site $site_id" <<<"$new_log" \
        || grep -Fq "Course navigation is already standardized for site $site_id" <<<"$new_log"; then
      completed=$((completed + 1))
    fi
  done
  if [[ "$failed" == true ]]; then
    echo 'Course layout migration reported an error; its scoped runtime settings remain for diagnosis.' >&2
    exit 1
  fi
  if [[ "$completed" -eq "$#" ]]; then
    sudo sed -i '/^quartz\.course\.layout\.migration\.autorun=/d;/^course\.site\.layout\.migration\.siteids=/d' "$PROPERTIES"
    echo "Course layout migration completed for $completed explicitly selected course sites; autorun disabled."
    exit 0
  fi
  sleep 10
done

echo 'Timed out waiting for the scoped course layout migration; settings remain enabled for diagnosis.' >&2
exit 1
