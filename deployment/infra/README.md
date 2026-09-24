# Azure infrastructure

`main.bicep` is the declarative source of truth for the isolated Sakai development environment:

- `10.42.0.0/16` VNet with an application subnet and a delegated MySQL subnet;
- NSG allowing only HTTPS, HTTP redirect, and SSH from the supplied administrator CIDR;
- private MySQL DNS zone and VNet link;
- private Azure MySQL Flexible Server 8.0 (`Standard_B1ms`, no HA, 20 GB storage);
- Ubuntu 24.04 low-cost 8 GiB burstable Sakai VM (currently `Standard_B2ms`; an equivalent B-series choice may be substituted only for regional capacity) with Standard SSD OS disk and static public IP;
- daily VM auto-shutdown at 19:00 Pakistan Standard Time.

It intentionally does not create a NAT gateway, load balancer, public database endpoint, or public Tomcat rule.

Run `scripts/deploy-infra.sh` rather than invoking the template manually. It gets sensitive parameters from `deployment/.env`, which is ignored by Git.

Run `scripts/configure-budget.sh` to create the resource-group-scoped USD 20 monthly budget with 80% actual-cost and 100% forecast alerts.
