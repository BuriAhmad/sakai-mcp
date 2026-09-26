# Phase 2 HTTPS form prerequisite — 2026-09-26

Status: **PASS**.

While adding Announcements and Assignments through Site Info → Manage Tools, the browser showed a disabled Continue button and no POST reached Nginx. The form's rendered action was `http://` on a public `https://` page. This is a mixed-content form submission, so the fixture workflow could not complete.

The tracked Sakai 25.2 `default.sakai.properties` recommends Tomcat `RemoteIpValve` when HTTPS terminates at a reverse proxy. The [Tomcat 9 valve reference](https://tomcat.apache.org/tomcat-9.0-doc/config/valve.html#Remote_IP_Valve) documents `protocolHeader`, trusted internal proxies, and HTTPS port handling. Nginx already sent `X-Forwarded-Proto`; Tomcat had no valve, and its 8080 connector listened on all addresses.

`deployment/configure-tomcat-proxy.sh` now configures that valve and binds 8080 to `127.0.0.1`. The tracked `configure-vm.sh` calls it for future bootstrap. The script was applied to the sandbox VM through the established `./sakai shell` access path without placing source changes on the VM. A pre-change `server.xml` backup was retained on the VM. Tomcat was restarted; its XML parsed successfully, the service became active, and `ss` confirmed only a loopback 8080 listener. Public `/portal` returned HTTP 200. The authenticated Manage Tools form then rendered an `https://` action, completed its confirmation step, and the new tools appeared in Course A. Three announcements were also posted through the normal public HTTPS form and appeared in the course list.

No credentials, session values, or LMS content are recorded here.
