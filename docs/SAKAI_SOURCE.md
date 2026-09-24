# Sakai source in this repository

`apps/sakai/` is a tracked copy of the official Sakai 25.2 source. Its starting point is upstream commit `b5b7800f0fcddf9d0db47276a66065189365d905`, the same commit recorded for the current VM deployment. The upstream repository is <https://github.com/sakaiproject/sakai> and its license is retained at `apps/sakai/LICENSE`.

The source is part of this repository's Git history. Edit and commit it here alongside the MCP service and deployment code. There is no nested `.git` directory and no second project remote to push.

The VM checkout at `/opt/sakai-src` and the deployed Tomcat files are separate runtime copies. Pushing a commit to GitHub does not update the VM. Use the explicit `./sakai deploy COMMIT` release procedure in [SAKAI_RELEASES.md](SAKAI_RELEASES.md) to build and install a chosen commit. The original `deployment/deploy-sakai.sh` remains the guarded, unmodified-25.2 bootstrap script.

This import is a source snapshot, not a copy of upstream's full commit history. For an upstream upgrade, record the new official tag and commit, compare its source against this baseline plus local changes, and review the resulting application and database compatibility before deployment.
