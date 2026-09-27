# Phase 8 — guarded Sakai release preflight (2026-09-26)

Status: **IN PROGRESS; deployment and acceptance gate NOT RUN**.

The selected source commit is `d97ce2f7ee45734b95526017ccad0c429c0a9a22`, pushed to `origin/main`. The existing `./sakai deploy HEAD --check-only` gate passed for that exact commit. GitHub repository validation and the [full Sakai source build](https://github.com/BuriAhmad/sakai-mcp/actions/runs/36262764735) passed, satisfying the Phase 7 exact-commit build condition.

Read-only Azure and VM checks confirmed the expected project subscription, running development VM, Ready private MySQL, public HTTPS `/portal` HTTP 200, and 34 GiB available on the VM root filesystem. The current release marker was the previously verified pre-MCP commit `e0553fef88a0ca149be3a33f0cd026aec88e9f16`; the existing `./sakai rollback RELEASE_ID` path remains the code rollback procedure. No new Sakai database schema migration is in this adapter.

A fresh synthetic-user OBO token was compared to Entra discovery metadata. Its issuer and JWKS URI, tenant, audience, and scope were saved as non-secret values in an ignored mode-0600 local runtime file. Two known course fixtures each expose two seeded assignments through Sakai's authenticated direct assignment route. Their live identifiers were saved in a separate ignored mode-0600 fixture file for post-deployment tests. No token, credential, private key, Sakai site or assignment ID, user identifier, grade, submission, or announcement content is in this report.

Next: apply the tracked runtime-property script, deploy through `./sakai deploy <commit>`, then run the public health, ordinary login, delegated bearer, cross-course, permission, and rollback checks. No deployment or MCP property mutation occurred in this preflight.
