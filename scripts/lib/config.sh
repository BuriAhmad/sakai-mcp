#!/usr/bin/env bash

# Non-secret project resource names shared by local operations.
SAKAI_SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
SAKAI_RESOURCE_GROUP='rg-sakai-mcp-dev'
SAKAI_VM_NAME='vm-sakai-dev'
SAKAI_VM_USER='sakaiadmin'
SAKAI_NSG_NAME='nsg-sakai-app-dev'
SAKAI_SSH_RULE_NAME='allow-ssh-admin-only'
SAKAI_SSH_KEY="${SAKAI_SSH_KEY:-$HOME/.ssh/buriPersonal}"

