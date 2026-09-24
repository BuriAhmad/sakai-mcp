# VM access from a Mac

## The simple rule

Use:

```bash
./sakai shell
```

The command performs three separate checks:

1. **Azure identity:** Azure CLI must be signed in to the expected subscription. This authorizes changing the VM and its firewall rule.
2. **Network access:** the NSG allows TCP port 22 only from the current public IPv4 address (`x.x.x.x/32`). The script refreshes this value whenever the ISP, Wi-Fi, hotspot, or VPN changes it.
3. **VM identity:** SSH accepts only the matching private key. Password authentication is disabled.

Both the firewall rule and SSH key matter. Azure CLI login alone is not an SSH tunnel, and possession of the key alone does not bypass the firewall.

## Initial setup

Requirements:

- macOS `ssh` (included with macOS);
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli-macos);
- the private key at `~/.ssh/buriPersonal` that matches the public key installed on the VM.

Then run:

```bash
./sakai login
./sakai shell
```

To use a key stored elsewhere:

```bash
SAKAI_SSH_KEY="$HOME/.ssh/another-key" ./sakai shell
```

Changing the path does not install a new public key on the VM. The corresponding public key must already be in `/home/sakaiadmin/.ssh/authorized_keys`.

## What the script changes

The script updates only this existing NSG rule:

| Setting | Value |
| --- | --- |
| Resource group | `rg-sakai-mcp-dev` |
| NSG | `nsg-sakai-app-dev` |
| Rule | `allow-ssh-admin-only` |
| Destination | TCP 22 |
| Source | This network's current public IPv4 `/32` |

It does not use `0.0.0.0/0`, change HTTPS access, alter the VM account, or copy a private key to Azure.

The rule can remain in place: it permits only that one network address, and the SSH key is still required. Running `./sakai shell` from another network safely replaces the old address.

## Other Azure access mechanisms

- **Run Command** executes bounded recovery or diagnostic commands through the Azure VM agent. It is not the normal interactive development shell.
- **Azure Bastion Developer** is free for this development environment in Korea Central and supplies a browser terminal through the Azure portal. It is a useful recovery path if direct SSH cannot be repaired. The free tier does not provide native Mac CLI tunneling.
- **Bastion Standard/Premium** supports native CLI tunneling but incurs a continuous hourly charge while deployed. It is not enabled for this cost-sensitive sandbox.
- **Defender for Cloud JIT access** automates temporary firewall openings, but it requires Defender for Servers Plan 2. The local script supplies the same narrow-IP behavior without that subscription cost.

For a production environment, remove the VM's public management path and use Bastion, a point-to-site VPN, or another centrally managed private-access solution.

## Troubleshooting

`Azure CLI is not logged in`

```bash
./sakai login
```

`SSH private key not found`

Restore the existing key securely, or install a new public key through an authorized recovery procedure. Never commit a private key to this repository.

`Permission denied (publickey)`

The network path works, but the selected private key does not match a public key on the VM. Check `SAKAI_SSH_KEY` and the key path.

Connection timeout

Run `./sakai open-ssh`, confirm any VPN did not change the public address, and retry. `./sakai shell` also starts a deallocated VM automatically.
