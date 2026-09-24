#!/usr/bin/env bash
set -Eeuo pipefail

SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
BUDGET_NAME='sakai-dev-monthly-20usd'
CONTACT_EMAIL='b.ahmadkhan3@gmail.com'

[[ "$(az account show --query id -o tsv)" == "$SUBSCRIPTION_ID" ]] || {
  echo "Refusing: the intended subscription is $SUBSCRIPTION_ID." >&2
  exit 1
}

BODY="$(cat <<JSON
{
  "properties": {
    "category": "Cost",
    "amount": 20,
    "timeGrain": "Monthly",
    "timePeriod": {"startDate": "2026-09-01T00:00:00Z", "endDate": "2027-09-30T00:00:00Z"},
    "notifications": {
      "actual-80": {"enabled": true, "operator": "GreaterThan", "threshold": 80, "contactEmails": ["$CONTACT_EMAIL"]},
      "forecast-100": {"enabled": true, "operator": "GreaterThan", "threshold": 100, "contactEmails": ["$CONTACT_EMAIL"], "thresholdType": "Forecasted"}
    }
  }
}
JSON
)"

az rest --method put \
  --url "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Consumption/budgets/$BUDGET_NAME?api-version=2023-05-01" \
  --body "$BODY" --output json
