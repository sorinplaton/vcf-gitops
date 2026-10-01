# Jump host

`/etc/netplan/60-holodeck.yaml` does not exist on the jump host (checked 2026-10-01), so
there is no netplan file here. `/etc/netplan` holds `00-installer-config.yaml`,
`01-network-manager-all.yaml` and `90-NM-febc54dc-e29c-3939-a911-8a11855bd1c8.yaml`;
all three are readable by root only and were not copied.
