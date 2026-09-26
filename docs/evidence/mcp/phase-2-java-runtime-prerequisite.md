# Phase 2 assignment runtime prerequisite — 2026-09-26

Status: **PASS — configuration and assignment workflow verified**.

The first attempt to post a synthetic assignment reached Sakai over HTTPS, but the Assignments tool frame returned an empty response. Tomcat logged `InaccessibleObjectException` for `java.time.Instant.seconds` during Ignite binary serialization, reached through `AssignmentServiceImpl.getAssignmentsForContext` and the assignment tool's Gradebook integration. The public `/portal` remained healthy. A read-only database check found no assignment with the intended title; the write is **not** counted as a successful fixture.

The tracked Sakai 25.2 `apps/sakai/docker/tomcat/bin/setenv.sh` and `master/pom.xml` include `--add-opens=java.base/java.time=ALL-UNNAMED`. The VM's bootstrap `setenv.sh` lacked that and 13 other upstream module options. `deployment/ensure-sakai-java-opens.sh` now adds the missing options repeatably, and `configure-vm.sh` calls it for future bootstrap. The tracked script was applied to the sandbox VM through `./sakai shell`; the prior runtime file is backed up on the VM. Tomcat was restarted. Public `/portal` readiness returned HTTP 200. The Assignments tool then loaded, four titled assignments were posted in two sites, and three students submitted practice work through the normal UI. The incomplete untitled row from the failed attempt was moved to Trash through the normal UI; zero incomplete assignments remained in the active list.

No credentials, session values, or assignment content are recorded here.
