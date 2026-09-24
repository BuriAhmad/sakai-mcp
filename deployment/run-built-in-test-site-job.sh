#!/usr/bin/env bash
set -Eeuo pipefail

# Run Sakai's own Quartz SeedSitesAndUsersJob once. Sakai's legacy Job Scheduler
# UI is the normal entry point, but the same supported AutoRun hook is useful in
# non-interactive deployments. It creates no LMS records itself; Sakai's job does.
[[ "${SAKAI_TEST_JOB_CONFIRM:-}" == "YES" ]] || {
  echo 'Refusing to alter the one-time Quartz setting. Re-run with SAKAI_TEST_JOB_CONFIRM=YES.' >&2
  exit 2
}

TOMCAT_HOME='/opt/tomcat'
PROPERTIES="$TOMCAT_HOME/sakai/local.properties"
LOG="$TOMCAT_HOME/logs/catalina.out"
sudo test -r "$PROPERTIES" || { echo "Missing $PROPERTIES" >&2; exit 1; }

# `AutoRun` in Sakai's site-manage component maps this property to the
# registered 'Create sites, users and content for testing.' Quartz job.
sudo sed -i '/^quartz\.seedsites\.autorun=/d' "$PROPERTIES"
echo 'quartz.seedsites.autorun=true' | sudo tee -a "$PROPERTIES" >/dev/null
if [[ "${SAKAI_SEED_EID_PASSWORD:-false}" == 'true' ]]; then
  # Makes generated test-account credentials deterministic for a one-time UI
  # verification. This is a documented Sakai SeedSitesAndUsersJob property.
  sudo sed -i '/^site\.seed\.eid\.password=/d' "$PROPERTIES"
  echo 'site.seed.eid.password=true' | sudo tee -a "$PROPERTIES" >/dev/null
fi
start_line=$(sudo sh -c "wc -l < '$LOG'")

sudo systemctl restart tomcat
for _ in {1..90}; do
  new_log=$(sudo tail -n +"$((start_line + 1))" "$LOG")
  if grep -q 'SeedSitesAndUsersJob completed\.' <<<"$new_log"; then
    sudo sed -i '/^quartz\.seedsites\.autorun=/d' "$PROPERTIES"
    sudo sed -i '/^site\.seed\.eid\.password=/d' "$PROPERTIES"
    echo 'Built-in Quartz test-site job completed; autorun disabled for future starts.'
    exit 0
  fi
  if grep -q 'SeedSitesAndUsersJob.*ERROR\|SeedSitesAndUsersJob.*Exception' <<<"$new_log"; then
    echo 'Built-in Quartz test-site job reported an error; autorun remains enabled for diagnosis.' >&2
    exit 1
  fi
  sleep 20
done

echo 'Timed out waiting for the built-in Quartz test-site job; autorun remains enabled for diagnosis.' >&2
exit 1
