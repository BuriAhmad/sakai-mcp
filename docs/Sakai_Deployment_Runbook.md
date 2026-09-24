# Sakai 25.2 Azure Sandbox Deployment Runbook

## Goal

Deploy a fully functioning **Sakai 25.2** installation on Azure, populated with **Sakai's built-in demo and test data**, so it can be manually tested as an LMS with different user roles and later used as the backend for MCP testing.

## Scope and Fixed Decisions

This runbook is only for getting **Sakai itself deployed and ready**. It does **not** include the MCP server.

Use the following architecture:

```text
Internet
   |
 HTTPS
   v
Azure Linux VM
   |
   +-- Reverse proxy / TLS
   +-- Tomcat 9
   +-- Sakai 25.2
   |
   | private VNet connection
   v
Azure Database for MySQL Flexible Server 8.0
```

Important decisions:

- Use **Sakai 25.2**, the current supported 25.x release.
- Build Sakai from its **source release/tag**, rather than using an old demo package.
- Use **Java 17**, **Maven 3.9+**, and a fresh **Tomcat 9** installation.
- Use **Azure Database for MySQL Flexible Server 8.0**.
- Keep MySQL private inside the Azure VNet.
- Keep this project isolated from unrelated Azure work by using a **dedicated Sakai resource group** and a **dedicated Sakai VNet**.
- Inspect existing VNets/address spaces in the subscription before choosing this project's CIDR; do not create overlapping address space carelessly.
- Use deterministic names and project/environment tags so every Sakai resource is easy to identify and delete.
- Treat the resource group as the **management/lifecycle boundary** and the VNet/subnets/NSGs as the **network boundary**.
- Do not silently weaken security, increase cost materially, change region, enable public database access, or add major infrastructure merely to work around a deployment problem.
- Populate data using **Sakai's own built-in mechanisms**:
  1. `-Dsakai.demo=true` during the first startup.
  2. Sakai's built-in Quartz test-data job, named **Create Test Sites** / **Create sites, users and content for testing** depending on the UI/version wording.
- Do **not** write a custom seeding script at this stage.
- Do **not** directly insert fake LMS records into Sakai's database.
- Make the deployment reproducible with infrastructure/configuration scripts rather than relying only on one-off commands.

---


# Deployment Architecture and Safety Contract

This section defines the boundaries Codex must preserve **before it creates any Azure resource**.

The Azure subscription may contain unrelated coursework, senior-project infrastructure, experiments, or future services. The Sakai sandbox must therefore be easy to identify, reason about, stop, recreate, and delete without affecting anything else.

## Resource Group Is the Project Lifecycle Boundary

Use one dedicated resource group for this project, for example:

```text
rg-sakai-mcp-dev
```

All Azure resources created specifically for this Sakai sandbox should live in this resource group unless Azure requires otherwise.

Conceptually:

```text
Azure for Students subscription
│
├── rg-sakai-mcp-dev
│   ├── vnet-sakai-dev
│   ├── snet-sakai-app-dev
│   ├── snet-sakai-mysql-dev
│   ├── nsg-sakai-app-dev
│   ├── vm-sakai-dev
│   ├── nic-sakai-dev
│   ├── pip-sakai-dev
│   ├── Azure MySQL Flexible Server
│   ├── MySQL private DNS resources
│   └── other resources belonging only to this sandbox
│
├── unrelated-coursework-rg
├── unrelated-project-rg
└── other Azure resources
```

The resource group is primarily the **management and lifecycle boundary**:

```text
resource organization
cost inspection
RBAC scope
deployment history
tags
cleanup/destruction
```

It is **not** by itself a network-security boundary.

Do not place unrelated Azure resources inside the Sakai project resource group.

Do not place Sakai resources into unrelated existing resource groups merely because they already exist.

## Use a Dedicated Sakai VNet

Create a dedicated VNet for this project instead of reusing an unrelated coursework/project VNet.

Before selecting its address range, Codex must inspect existing VNets and their address spaces in the selected subscription.

Choose a private RFC1918 range that does not conflict with existing or plausibly connected networks.

A suitable example, **only if it is confirmed not to overlap**, is:

```text
vnet-sakai-dev
10.42.0.0/16
```

The `/16` is intentionally larger than the current sandbox needs. Private address space is cheap, and reserving space now avoids painful re-addressing later.

Document the selected VNet CIDR in the repository.

## Planned Subnet Layout

A recommended plan is:

```text
10.42.0.0/16       vnet-sakai-dev
│
├── 10.42.1.0/24   snet-sakai-app-dev
│                  Sakai VM
│
├── 10.42.2.0/24   snet-sakai-mysql-dev
│                  delegated exclusively to Azure MySQL
│
├── 10.42.3.0/24   RESERVED for future MCP / Container Apps networking
│
├── 10.42.4.0/24   RESERVED for possible future private endpoints/services
│
└── remaining address space unallocated for future needs
```

The exact CIDRs can differ if the subscription already uses these ranges.

Do **not** create a CIDR collision merely to preserve the example above.

The MySQL subnet is special:

```text
snet-sakai-mysql-dev
    delegated to Microsoft.DBforMySQL/flexibleServers
    used only by Azure Database for MySQL Flexible Server
```

Do not deploy the Sakai VM or unrelated resources into the delegated MySQL subnet.

The future MCP range is only a reservation in the addressing plan at this stage. It does **not** mean the MCP server should be deployed now.

If Azure Container Apps is later integrated with the VNet, it needs a dedicated subnet appropriate for the chosen Container Apps environment. Current Azure guidance permits a `/27` minimum for workload-profiles environments, so reserving a larger block now keeps that option open.

## Public and Private Network Boundaries

The intended trust model is:

```text
Internet
   |
   | 443 HTTPS
   v
Reverse Proxy on Sakai VM
   |
   | local/private forwarding
   v
Tomcat / Sakai :8080
   |
   | private VNet connection
   v
Azure MySQL :3306
```

### Publicly reachable

Normally only:

```text
443/tcp   HTTPS to Sakai
80/tcp    optional HTTP redirect / certificate-validation traffic
```

### Administrative access

```text
22/tcp    SSH
```

SSH should be restricted to the administrator's required source IP/range where practical.

Do not create a broad `0.0.0.0/0 -> 22` rule merely for convenience.

### Must not be exposed publicly

```text
8080/tcp  raw Tomcat
3306/tcp  MySQL
Tomcat management interfaces
```

The reverse proxy is the public web entry point.

MySQL must remain private.

## Explicit Outbound Connectivity

The Sakai VM requires outbound Internet connectivity during setup for operations such as:

```text
apt/package installation
GitHub access
git clone/fetch
Maven dependency downloads
certificate issuance/renewal
software updates
```

For Azure networking APIs after March 31, 2026, new VNet subnets are private by default with respect to implicit outbound access. Do not assume that an unconfigured VM will automatically have Internet egress.

Because this sandbox's Sakai VM also needs a public web endpoint, explicitly associating a public IP with the VM/NIC provides a valid explicit outbound path for this simple sandbox.

Codex must verify both:

```text
VM -> public Internet           WORKS
VM -> private Azure MySQL       WORKS
```

before attempting the large Sakai build.

Do not add a NAT Gateway merely because outbound connectivity was not first understood; diagnose the actual network configuration.

## Private DNS Is Part of the Database Architecture

Sakai must connect to Azure MySQL using the server's **FQDN**, not a hardcoded private IP address.

Conceptually:

```text
Sakai VM
   |
   | DNS query
   v
Azure Private DNS
   |
   v
private MySQL address
   |
   v
Azure MySQL
```

The MySQL private DNS zone/VNet link is therefore a required dependency and should be represented in the infrastructure definition where applicable.

Deleting or mis-linking private DNS can break database connectivity even when both the VM and database are healthy.

## Naming and Tagging Contract

Choose deterministic names before provisioning.

Example:

```text
Resource group:       rg-sakai-mcp-dev
VNet:                 vnet-sakai-dev
Application subnet:   snet-sakai-app-dev
MySQL subnet:         snet-sakai-mysql-dev
VM NSG:               nsg-sakai-app-dev
VM:                   vm-sakai-dev
NIC:                  nic-sakai-dev
Public IP:            pip-sakai-dev
MySQL:                mysql-sakai-dev-<required-unique-suffix>
```

Apply consistent tags where supported:

```text
project     = sakai-mcp
environment = dev
purpose     = lms-sandbox
owner       = burhan
managed-by  = bicep
```

Do not respond to a name collision by producing arbitrary names such as `test-new2-final-4837`.

If a globally unique suffix is required, generate it deliberately and record it.

## Cost and Architecture Guardrails

A budget/alert is useful but should not be treated as a guaranteed hard spending cap.

Codex must not silently:

- switch to a materially more expensive VM or database SKU;
- enable MySQL high availability;
- deploy extra load balancers, NAT Gateways, gateways, firewalls, AKS, or similar infrastructure;
- move to another Azure region;
- make MySQL public;
- expose Tomcat directly;
- create additional production-style redundancy;
- create unrelated resources elsewhere in the subscription.

If the agreed low-cost architecture cannot be deployed, Codex should stop that part of the deployment, preserve diagnostics, and clearly report the blocker and the proposed architectural change.

## Automation Must Be Idempotent

Infrastructure automation should converge on the intended environment.

Running the deployment again should update/reuse the same named resources where appropriate rather than create:

```text
vm-sakai-dev
vm-sakai-dev-2
vm-sakai-new

vnet-sakai-dev
vnet-sakai-test2
```

Prefer declarative Bicep for Azure infrastructure.

Use scripts for guest configuration and application deployment.

Conceptually:

```text
Bicep
  -> Azure resources/networking

configure-vm.sh
  -> operating-system configuration

configure-tomcat.sh
  -> Tomcat

configure-sakai.sh
  -> Sakai settings

deploy-sakai.sh
  -> Sakai build/deployment
```

A failed deployment should be safely repeatable after the underlying problem is corrected.

## RBAC Principle

For the initial personal sandbox, Codex may operate through the already authenticated Azure CLI identity.

However, do not broaden permissions unnecessarily.

Azure permissions should be granted at the smallest practical scope.

A future dedicated deployment identity should ideally be scoped to:

```text
rg-sakai-mcp-dev
```

rather than the whole subscription.

## Resource Locks

Do not add a resource-group-wide deletion lock by default during the first disposable sandbox build, because the project intentionally needs a reliable `destroy-dev` workflow.

A `CanNotDelete` lock may be considered later for particularly valuable state, such as a manually curated database, but only when its effect on cleanup and automation is understood.

## Sandbox Data Only

This environment is for development.

Use:

```text
fake users
fake courses
synthetic assignments
synthetic grades
test resources
```

Do not place real student data, production credentials, or confidential university information into this sandbox.

---

# Codex Deployment Checklist

## 1. Verify the Azure Environment

Before provisioning anything, Codex should inventory the Azure context rather than assume the subscription is empty.

Verify:

- Azure CLI is installed and working;
- the authenticated identity with `az account show`;
- the intended Azure subscription is selected explicitly;
- the subscription name and subscription ID are recorded in the deployment notes;
- existing resource groups are inspected;
- existing VNets and their address spaces are inspected;
- the selected Azure region supports the intended VM and MySQL SKUs;
- sufficient quota exists;
- the selected region is kept consistent for the VNet, VM, and VNet-integrated MySQL server;
- deterministic project names and tags are established before resource creation.

Useful inventory commands may include:

```bash
az account show
az group list -o table
az network vnet list -o table
```

Codex should also inspect VNet address spaces before choosing the Sakai CIDR.

Example project identity:

```text
Resource group: rg-sakai-mcp-dev
Environment:    dev
Project tag:    sakai-mcp
VNet:           vnet-sakai-dev
```

Codex must stop rather than silently deploy into the wrong subscription.

Codex must also stop and report the issue rather than silently switching Azure regions or changing the architecture because a desired SKU/quota is unavailable.

---

## 2. Create the Dedicated Resource Group and Cost Controls

Create one dedicated Azure resource group for the entire Sakai sandbox:

```text
rg-sakai-mcp-dev
```

The group should contain the resources whose lifecycle belongs to this project.

Do not reuse an unrelated coursework/project resource group.

Apply project/environment tags consistently, for example:

```text
project     = sakai-mcp
environment = dev
purpose     = lms-sandbox
owner       = burhan
managed-by  = bicep
```

Configure:

- an Azure budget and spending alerts at an appropriate scope;
- inexpensive development SKUs;
- no high availability for this sandbox;
- minimal practical storage and backup retention.

Remember that Azure budgets/alerts are primarily monitoring and notification controls, not a guarantee that spending physically stops at the threshold.

Keep everything easy to:

```text
identify
inspect
stop
recreate
delete
attribute in Cost Analysis
```

Do not add a resource-group-wide deletion lock during the initial disposable build unless there is a deliberate reason.

Before continuing, verify that the resource group contains only intended Sakai project resources.

---

## 3. Create the Dedicated Azure Network

Create one dedicated VNet for the Sakai project.

Before choosing its CIDR:

1. inspect existing Azure VNets/address spaces in the subscription;
2. avoid overlaps with existing networks;
3. leave room for future Sakai/MCP infrastructure.

A recommended layout, **only if the range is confirmed unused**, is:

```text
vnet-sakai-dev
10.42.0.0/16
│
├── snet-sakai-app-dev
│   10.42.1.0/24
│   Sakai VM
│
├── snet-sakai-mysql-dev
│   10.42.2.0/24
│   delegated to Microsoft.DBforMySQL/flexibleServers
│
├── 10.42.3.0/24
│   reserved in the address plan for future MCP/Container Apps networking
│
└── 10.42.4.0/24
    reserved in the address plan for possible future private services/endpoints
```

The reserved ranges do not need to be created as subnets yet.

Azure reserves addresses inside each subnet, so do not size subnets as if every address is usable.

### MySQL Subnet

Create a separate subnet delegated to:

```text
Microsoft.DBforMySQL/flexibleServers
```

This subnet is exclusively for Azure Database for MySQL Flexible Server.

Do not deploy the Sakai VM or unrelated resources into it.

### Application Subnet

Place the Sakai VM/NIC in the application subnet.

Create an NSG for the application side.

Intended inbound exposure:

```text
443/tcp   Internet -> Sakai reverse proxy
80/tcp    Internet -> optional redirect/certificate flow
22/tcp    administrator source IP/range -> SSH
```

Do not permit:

```text
Internet -> 8080/tcp
Internet -> 3306/tcp
Internet -> Tomcat management interfaces
```

When practical, restrict SSH to the administrator's current public IP rather than `0.0.0.0/0`.

### Explicit Outbound Connectivity

Do not assume implicit Azure outbound Internet access.

For new VNet API behavior after March 31, 2026, private subnets require an explicit outbound method.

For this small sandbox, the Sakai VM is already intended to have an explicit public IP for its public HTTPS endpoint. That public IP can also provide the VM's explicit outbound path.

Before attempting to install/build Sakai, verify from the VM that:

```text
DNS resolution                    PASS
public Internet HTTPS access     PASS
GitHub/package access            PASS
private MySQL DNS resolution     PASS
private MySQL network path       PASS
```

Do not introduce a NAT Gateway merely as an unexplained workaround.

### Private DNS for MySQL

Create or configure the Azure Private DNS zone required for MySQL VNet integration and link it to the Sakai VNet as required.

Sakai must later use the MySQL **FQDN**, not a hardcoded private IP.

The Sakai VM and MySQL server should communicate privately through the VNet.

---

## 4. Provision Azure Database for MySQL Flexible Server

Create an **Azure Database for MySQL Flexible Server running MySQL 8.0**.

Use a low-cost development configuration:

- Burstable compute where practical;
- no HA;
- minimal practical storage;
- private VNet access;
- TLS for database connections.

Network requirements:

- place the server in the dedicated MySQL subnet;
- delegate that subnet to `Microsoft.DBforMySQL/flexibleServers`;
- keep public database access disabled;
- ensure the private DNS zone is correctly linked;
- use the MySQL server FQDN in application configuration.

Do **not** hardcode the MySQL private IP address because it is not the stable application contract.

Create:

- the Sakai database;
- a dedicated Sakai database account;
- a strong generated password.

Ensure the database uses the character encoding Sakai expects, using `utf8mb4` where applicable.

Verify database connectivity **from the Sakai VM** before attempting to build/start Sakai.

Verification should include:

```text
FQDN resolves to the expected private path
TCP connection succeeds privately
TLS connection succeeds as intended
Sakai database account authenticates
database can be selected/accessed
```

If private connectivity fails, diagnose:

```text
VNet/subnet placement
subnet delegation
private DNS
NSG/routing
credentials
TLS/database configuration
```

Do **not** enable public MySQL access merely to make deployment progress.

Do not continue until a MySQL client on the VM can successfully reach the database through the intended private path.

---

## 5. Provision the Sakai Linux VM

Create a Linux VM for Sakai.

Prefer a conservative Ubuntu LTS image.

The VM needs enough memory for Tomcat/Sakai. The official Sakai example JVM configuration uses a multi-gigabyte heap, so Codex should select a VM with enough RAM rather than choosing the absolute smallest VM and causing repeated out-of-memory failures.

Configure:

- SSH-key authentication;
- persistent OS disk;
- an explicit public IP for the sandbox's public Sakai endpoint and VM outbound connectivity;
- a stable hostname/FQDN where practical;
- placement in `snet-sakai-app-dev`;
- the VM NSG;
- appropriate DNS/FQDN if being used.

After provisioning, verify that the VM's NIC is attached to the intended application subnet and that no accidental secondary NIC/network path was created.

Before building Sakai, verify the VM can:

```text
reach package repositories
reach GitHub
resolve DNS
download Maven dependencies
resolve/reach MySQL privately
```

---

## 6. Prepare and Secure the VM

On the VM, Codex should:

- update system packages;
- create/use an appropriate non-root administrative account;
- verify filesystem space and memory;
- install basic tools required for troubleshooting;
- ensure installation directories have correct ownership and permissions.

Secrets must not be committed into Git.

Any local Sakai configuration file containing the database password should be readable only by the account/service that needs it.

---

## 7. Install Sakai Prerequisites

Install and verify:

- **Java JDK 17**
- **Git**
- **Maven 3.9 or later**
- **MySQL client tools**
- a supported MySQL JDBC connector
- **Apache Tomcat 9**

Codex should verify versions explicitly:

```bash
java -version
mvn --version
git --version
```

For Tomcat, follow Sakai's guidance:

> Install a fresh upstream Tomcat 9 distribution rather than Ubuntu's packaged/system Tomcat.

A conventional location is:

```text
/opt/tomcat
```

---

## 8. Configure Tomcat Correctly for Sakai

Configure Tomcat before deploying Sakai.

This includes:

- `CATALINA_HOME`;
- appropriate Java/JVM options in `setenv.sh`;
- sufficient JVM heap;
- UTF-8 file/runtime settings;
- `URIEncoding="UTF-8"` on the Tomcat connector;
- correct ownership and permissions;
- Sakai home/configuration directory;
- log locations.

Codex should also create a **systemd service** for Tomcat/Sakai so that:

```text
systemctl start tomcat
systemctl stop tomcat
systemctl restart tomcat
systemctl status tomcat
```

work reliably and the application can return after a VM reboot.

Do not expose Tomcat's raw management interfaces publicly.

---

## 9. Download the Correct Sakai Source

Clone the official Sakai repository and check out the exact stable release tag:

```text
25.2
```

Codex must verify the checked-out tag/commit rather than accidentally deploying `master` or an arbitrary development branch.

Keep the source on the VM or in the deployment workspace so it can later be inspected or rebuilt.

---

## 10. Configure Sakai

Create the Sakai configuration directory and the appropriate `sakai.properties` / `local.properties`.

Configure at least:

- database vendor;
- MySQL JDBC driver;
- MySQL 8 Hibernate dialect;
- database hostname;
- database name;
- database username/password;
- Unicode connection settings;
- transaction isolation;
- Sakai server hostname;
- canonical `serverUrl`;
- `serverName`;
- a sensible `serverId`;
- institution/service display name;
- timezone;
- filesystem paths where required.

The JDBC connection must point to the **Azure MySQL private hostname**, not `localhost`.

Codex should consult the `default.sakai.properties` shipped with the exact Sakai 25.2 source instead of blindly copying configuration from older Sakai releases.


### Verify Content Storage and Upload Configuration

The sandbox should support normal LMS resources such as:

- PDF lecture notes;
- PowerPoint files (`.pptx`);
- Word documents;
- images;
- ZIP archives;
- assignment attachments.

Do not assume that successful database connectivity alone proves that file/resource uploads are configured correctly.

Codex must inspect the exact **Sakai 25.2** configuration defaults and determine how `ContentHostingService` stores binary file content.

Inspect at least:

```text
bodyPath@org.sakaiproject.content.api.ContentHostingService
bodyVolumes@org.sakaiproject.content.api.ContentHostingService
```

For this sandbox, prefer Sakai's normal database-backed content storage and do **not** introduce filesystem-backed or external object storage unless there is a concrete reason to do so.

If the exact Sakai 25.2 defaults confirm that leaving `bodyPath` unset keeps content database-backed, retain that behavior.

Codex must record the selected storage mode in the final deployment report:

```text
Content storage backend: Database BLOB / Filesystem / Other
```

Codex must also inspect the exact Sakai 25.2 upload/resource limits, including where present:

```text
content.upload.max
content.upload.ceiling
content.quota
content.dropbox.quota
content.zip.enabled
content.zip.expand.enabled
content.zip.expand.maxfiles
```

For this sandbox, the normal Sakai upload limit is sufficient if it is approximately **20 MB**. Do not increase the limit merely for development convenience unless a real test case requires it.

The goal is to understand and verify the effective Sakai configuration, not to blindly copy values from another release.

---

## 11. Build and Deploy Sakai

Follow Sakai's source-build process.

First install the Sakai master project, then build/deploy the application to Tomcat.

Conceptually:

```bash
cd sakai/master
mvn clean install

cd ..
mvn clean install sakai:deploy \
  -Dmaven.tomcat.home=/opt/tomcat \
  -Dsakai.home=/opt/tomcat/sakai
```

Codex should:

- capture the Maven output;
- resolve dependency/build failures;
- verify the expected Sakai WAR/JAR/components are deployed;
- verify Tomcat can read the deployed files.

A successful Maven command alone is **not** sufficient proof that Sakai works.

---

## 12. Perform the First Startup With Sakai Demo Data

For the **first startup against the empty Sakai database**, add:

```text
-Dsakai.demo=true
```

Then start Tomcat and allow Sakai to initialize its schema and built-in demo data.

Codex must inspect the logs for:

- database authentication failures;
- schema creation failures;
- missing JDBC drivers;
- Tomcat deployment failures;
- Java exceptions that prevent major Sakai components from starting.

After demo initialization succeeds:

1. stop Tomcat;
2. remove `-Dsakai.demo=true`;
3. restart Tomcat normally;
4. verify that the demo data remains present.

This flag is intentionally temporary. Sakai documentation states that it is intended for the initial population of an empty database.

---

## 13. Run Sakai's Built-In Test-Site/Data Generator — Required

This step is **mandatory**, not optional.

After the normal restart, use Sakai's built-in Quartz/job-scheduler functionality to run the test-data generation job described by Sakai documentation.

Depending on the Sakai UI/version wording, this is referred to as:

```text
Create Test Sites
```

or:

```text
Create sites, users and content for testing
```

The purpose is to create additional realistic sample sites, users, and content inside Sakai using Sakai's own supported testing facilities.

Codex should:

- authenticate as the Sakai administrator;
- locate the Job Scheduler / Quartz administration functionality;
- run the built-in test-site generation job;
- wait for it to finish;
- inspect job/application logs for failures;
- verify that additional sites/users/content were actually created.

If the job can only conveniently be initiated through the Sakai web UI, Codex may automate that one-time action with browser automation. It should **not replace the Sakai job with a custom database seeder**.

The final sandbox should contain enough built-in data to explore Sakai manually and later exercise read-oriented MCP tools against real LMS structures.

---

## 14. Configure a Stable Web Endpoint and HTTPS

Sakai should have a stable URL rather than being treated as an application reached through a changing raw port.

Configure:

- a stable Azure hostname or project domain;
- a lightweight reverse proxy such as Nginx/Caddy where appropriate;
- HTTPS/TLS;
- forwarding to the local Tomcat connector;
- Sakai's `serverUrl`/`serverName` to match the externally visible address.

Externally expose normal HTTPS rather than public Tomcat port `8080`.


### Verify Reverse-Proxy Upload Limits

The reverse proxy must not impose a smaller request-body limit than Sakai itself.

If **Nginx** is used, explicitly configure an appropriate value such as:

```nginx
client_max_body_size 25M;
```

or another value safely above Sakai's intended upload limit.

Do **not** leave Nginx at a smaller default limit that would reject normal Sakai uploads before the request reaches Tomcat/Sakai.

For example, if Sakai permits approximately 20 MB uploads:

```text
Reverse proxy allows:  >20 MB
Sakai allows:          ~20 MB
Effective user limit:  ~20 MB
```

If Caddy or another reverse proxy is used instead, Codex must inspect and verify its request-body behavior so it does not become the accidental upload bottleneck.

After configuring HTTPS and the proxy, test at least one multi-megabyte upload through the **public HTTPS URL**, not only through `localhost` or direct Tomcat access.

After the URL is finalized, restart Sakai and verify redirects, login, cookies, static assets, navigation, and file upload handling.

---

## 15. Secure the Default Administrator Account

Sakai historically provides the default administrator account:

```text
username: admin
password: admin
```

As soon as the deployment is proven alive, change the administrator password to a strong generated password.

Store credentials securely and do not place them in the repository or deployment logs.

Keep any generated student/instructor test credentials documented privately for later manual and MCP testing.

---

## 16. Perform Functional LMS Verification

Do not declare the deployment finished merely because `/portal` returns HTTP 200.

Codex should verify the application at the LMS level.

At minimum confirm:

### Administrator

- admin login works;
- Administration Workspace loads;
- users can be viewed;
- generated sites are visible;
- Job Scheduler/test-data job completed.

### Instructor/Test User

- instructor-style login works;
- course/site membership exists;
- sample site content can be opened;
- relevant teaching tools load.

### Student/Test User

- student-style login works;
- enrolled sites/courses appear;
- sample content can be opened.

### LMS Data

Verify the built-in generated environment contains a useful selection of:

- users;
- course/sites;
- rosters or memberships;
- assignments/content where generated;
- announcements/content where generated;
- resources;
- gradebook/tool data where generated;
- other test content produced by Sakai's test-site job.

The requirement is not that every Sakai feature contain data. The requirement is that the built-in demo/test mechanisms have produced a sufficiently populated LMS that can be meaningfully explored and tested.


### Functional File/Resource Upload Verification

Do not stop at confirming that a Resources tool exists.

Using an instructor/test account and the public HTTPS Sakai URL, upload a small representative set of normal LMS files, for example:

```text
lecture-notes.pdf
lecture-slides.pptx
assignment-files.zip
test-image.png
```

Keep every test file comfortably below Sakai's configured upload limit.

For each file, verify:

```text
UPLOAD        PASS
LIST/VISIBLE  PASS
DOWNLOAD      PASS
CONTENT OPENS PASS
```

For the ZIP file, test Sakai's ZIP handling/expansion functionality if the exact Sakai 25.2 deployment exposes and enables it.

The purpose of this test is to prove the full path:

```text
Browser
   |
   | HTTPS upload
   v
Reverse Proxy
   |
   v
Tomcat / Sakai
   |
   v
Configured Sakai Content Storage
```

A deployment where Sakai loads correctly but normal LMS resource uploads fail is **not** considered fully functional.

---

## 17. Test Persistence and Recovery

Perform controlled restart tests.

At minimum:

1. restart Tomcat;
2. verify Sakai returns;
3. verify the previously uploaded PDF/PPTX/ZIP/image resources are still visible and downloadable;
4. reboot the VM;
5. verify the Tomcat systemd service starts;
6. verify Sakai reconnects to MySQL;
7. verify generated users/sites/content are still present;
8. verify the previously uploaded binary resources are still visible, downloadable, and open correctly after the reboot.

If database-backed content storage is being used, Codex should also verify that these resources are not accidentally depending on an unplanned local VM content directory for persistence.

Also verify that stopping/deallocating the VM does not destroy the database or required configuration.

A system that works only immediately after installation is not considered finished.

---

## 18. Leave the Deployment Reproducible

Codex should not leave behind only terminal history.

Store the deployment logic in the project, for example:

```text
deployment/
├── infra/
│   └── main.bicep
├── configure-vm.sh
├── configure-tomcat.sh
├── configure-sakai.sh
├── deploy-sakai.sh
├── start-sakai.sh
├── stop-sakai.sh
├── status-sakai.sh
├── destroy-dev.sh
└── README.md
```

Exact filenames are flexible.

The important requirement is that another Codex session should be able to inspect the repository and understand how the Azure/Sakai environment was created.

### Infrastructure Must Be Idempotent

Prefer Bicep for Azure infrastructure so repeated deployment converges on the intended resources rather than creating duplicates.

A second deployment must not casually produce:

```text
vm-sakai-dev-2
vnet-sakai-new
mysql-sakai-final2
```

because the first attempt partially failed.

Where practical:

```text
deployment/infra/
├── main.bicep
├── parameters/dev.bicepparam
└── README.md
```

should describe the Azure layer, while VM/application scripts handle Linux, Tomcat, and Sakai.

If deployment fails part way through:

1. preserve the failure output/logs;
2. inspect the actual Azure state;
3. correct the underlying issue;
4. rerun safely;
5. reuse/update the intended resources where appropriate.

Do not paper over a failed state by creating a parallel second environment unless that is an explicit decision.

Secrets must remain outside source control.

---

## 19. Configure Development Cost Controls and Environment Lifecycle

Because this is a sandbox:

- configure VM auto-shutdown if useful;
- document how to deallocate/start the VM;
- document how to stop/start Azure MySQL;
- keep HA disabled;
- keep storage modest;
- keep everything inside the dedicated project boundary;
- periodically inspect actual spending rather than relying only on alerts.

Codex should provide simple commands/scripts for:

```text
START ENVIRONMENT
STOP ENVIRONMENT
CHECK STATUS
DESTROY ENVIRONMENT
```

### Stop Order

A reasonable controlled stop sequence is:

```text
1. stop Tomcat/Sakai cleanly
2. deallocate the Sakai VM
3. stop Azure MySQL Flexible Server
4. verify final Azure states
```

### Start Order

A reasonable start sequence is:

```text
1. start Azure MySQL Flexible Server
2. wait until the database reports Available/ready
3. start the Sakai VM
4. verify systemd starts Tomcat/Sakai
5. run Sakai health/login checks
```

### Important MySQL 30-Day Behavior

Azure Database for MySQL Flexible Server cannot remain stopped indefinitely.

If it remains stopped continuously for **30 days**, Azure automatically starts it and compute billing resumes.

Therefore, if the sandbox will be unused for a long period:

```text
export/dump any data worth keeping
verify deployment reproducibility
consider destroying the development resource group/environment
recreate it later when needed
```

rather than assuming a stopped MySQL server will remain free forever.

### Destruction Safety

`destroy-dev` must target only the intended Sakai development resource group/resources.

Before destructive actions, scripts should:

- print the subscription ID/name;
- print the target resource group;
- verify the expected project/environment tags where practical;
- require an explicit destructive confirmation or clear command intent.

Resource-group deletion is irreversible, so cleanup automation must not infer the target from an ambiguous default subscription.

This lifecycle approach preserves Azure student credits while keeping the project reproducible.

---

## 20. Produce a Final Deployment Report

Codex should finish by producing a compact report such as:

```text
Subscription:               ...
Region:                     ...
Resource group:             rg-sakai-mcp-dev
Project tags:               VERIFIED

VNet:                       ...
VNet CIDR:                  ...
Application subnet:         ...
MySQL subnet:               ...
MySQL subnet delegation:    Microsoft.DBforMySQL/flexibleServers
Future MCP range reserved:  ...
VM public IP/outbound:      VERIFIED
SSH restriction:            VERIFIED
Public Tomcat 8080:         BLOCKED
Public MySQL 3306:          BLOCKED
MySQL private DNS:          VERIFIED

Sakai version:              25.2
Java:                       17
Tomcat:                     9.x
Database:                   Azure MySQL Flexible Server 8.0
Database access:            Private VNet
Sakai URL:                  https://...
HTTPS:                      Working

Sakai startup:              PASS
Demo initialization:       PASS
Demo flag removed:         PASS
Built-in test-site job:    PASS
Generated sites/data:      VERIFIED

Content storage backend:   Database BLOB / Filesystem / Other
Sakai upload limit:        ...
Proxy upload limit:        ...
PDF/PPTX/ZIP/image upload: PASS
Post-restart download:     PASS

Admin login:               PASS
Instructor/test login:     PASS
Student/test login:        PASS
VM reboot test:            PASS
Persistence test:          PASS

Infrastructure reproducible: PASS
Repeated deploy/idempotence: VERIFIED
Start/stop scripts:          VERIFIED
Destroy target isolation:    VERIFIED

Deployment files/scripts:    ...
Known warnings/issues:       ...
Architectural deviations:    NONE / documented explicitly
```

The deployment is complete only when these verification steps pass.

---

# Definition of Done

The Sakai sandbox is considered ready when:

> A browser can open the Azure-hosted Sakai 25.2 instance over its stable URL; all Sakai-specific Azure resources are clearly isolated inside the intended project management/network boundaries; the VNet/subnet plan is documented and non-overlapping with the inspected subscription networks; MySQL remains private and reachable through the intended delegated subnet/private DNS path; public exposure is limited to the intended web/administrative entry points; the application uses Azure MySQL 8.0 successfully; Sakai's demo initialization and built-in test-site generation job have populated the LMS; multiple user types can log in and interact with generated sites/content; normal LMS resources such as PDFs, PowerPoint files, ZIP archives, and images can be uploaded and downloaded through the public HTTPS endpoint; those uploaded resources survive Tomcat restarts and VM reboots; the rest of the LMS data survives restarts; start/stop/destroy procedures are documented and scoped safely; and the infrastructure/deployment is reproducible from the saved project files without silently changing the agreed security or cost architecture.

At this point, **stop**. Do not begin MCP development yet.

The next phase should be learning/exploring the deployed Sakai system and its APIs.

---

# Official Sources Checked

This runbook was re-checked against the following official/current sources:

1. **Sakai Release Date List** — confirms Sakai 25.2 as the active 25.x release (released 2 June 2026).
   https://sakaiproject.atlassian.net/wiki/spaces/DOC/pages/17281679656/Sakai+Release+Date+list

2. **Official Sakai GitHub repository** — lists Sakai 25.2 as a community-supported version.
   https://github.com/sakaiproject/sakai

3. **Sakai 25 Install Guide (Source)** — Java 17, Maven 3.9+, Tomcat 9, source checkout/build process, MySQL configuration, UTF-8 configuration, `-Dsakai.demo=true`, and the built-in `Create Test Sites` Quartz job.
   https://sakaiproject.atlassian.net/wiki/spaces/DOC/pages/33232421161/Sakai+25+Install+Guide+Source

4. **Azure Database for MySQL version support policy** — confirms MySQL 8.0 remains supported by Azure Database for MySQL.
   https://learn.microsoft.com/en-us/azure/mysql/concepts-version-policy

5. **Azure Database for MySQL private VNet networking documentation** — delegated subnet, VNet integration, and private DNS requirements.
   https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-networking-vnet

6. **Azure CLI: MySQL Flexible Server** — current CLI provisioning options for Flexible Server and private networking.
   https://learn.microsoft.com/en-us/cli/azure/mysql/flexible-server

7. **Sakai default configuration properties** — source of truth to inspect for `ContentHostingService`, upload limits, quotas, and ZIP/resource settings. Codex must use the file from the exact checked-out Sakai 25.2 source when deploying.
   https://github.com/sakaiproject/sakai/blob/master/config/configuration/bundles/src/bundle/org/sakaiproject/config/bundle/default.sakai.properties

8. **Nginx `client_max_body_size` documentation** — request-body limit that must be configured so the reverse proxy does not reject valid Sakai uploads before they reach Tomcat/Sakai.
   https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size

9. **Azure Resource Groups** — recommends grouping resources that share the same lifecycle so they can be deployed, updated, and deleted together.
   https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/manage-resource-groups-cli

10. **Azure IP Address Planning** — guidance for non-overlapping CIDRs, reserving address space, and accounting for Azure-reserved subnet addresses.
    https://learn.microsoft.com/en-us/azure/networking/design-guide/ip-planning

11. **Azure Default Outbound Access** — documents the 2026 move toward private subnets/default outbound access disabled for new VNet API behavior and the need for explicit outbound connectivity.
    https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/default-outbound-access

12. **Azure Container Apps VNet Integration** — documents dedicated/delegated Container Apps networking and current subnet sizing guidance for workload-profiles environments.
    https://learn.microsoft.com/en-us/azure/container-apps/workload-profiles-manage-cli

13. **Azure MySQL Stop/Start** — documents automatic restart after 30 continuous days stopped.
    https://learn.microsoft.com/en-us/azure/mysql/flexible-server/how-to-stop-start-server-portal

14. **Azure RBAC Role Assignment Scope** — recommends using the smallest scope required for access.
    https://learn.microsoft.com/en-us/Azure/role-based-access-control/role-assignments

15. **Azure Resource Locks** — documents `CanNotDelete`/`ReadOnly` locks and their inheritance/operational implications.
    https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/lock-resources

16. **Azure Resource Group Deletion** — documents deletion behavior, irreversibility, and the effect of locks/dependencies.
    https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/delete-resource-group
