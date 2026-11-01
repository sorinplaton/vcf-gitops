# Management-domain Supervisor rebuild (NSX VPC)

The Supervisor on `cluster-mgmt-01a` (vc-mgmt-a) created on 2026-10-21 was a minimal one:
vSphere networking, one SMALL control plane, no load balancer, vSphere Pods and Supervisor
Services switched off, no VCF Automation region. Argo CD as a VCF Service, VKS clusters and
`LoadBalancer` services all need NSX VPC networking and vSphere Pods, and VCF Automation only
turns NSX VPC Supervisors into regions. It held no namespaces, so it was rebuilt.

| File | What |
|---|---|
| `enable-spec.json` | body for `POST /api/vcenter/namespace-management/supervisors/domain-c9?action=enable_on_compute_cluster` |
| `rebuild.sh` | `status`, `disable` (destructive), `enable`, `wait` |

What the spec says (ids looked up on 2026-11-01):

| Setting | Value |
|---|---|
| Zone | `zone-mgmt-a` |
| Control plane | 1 x SMALL on `vmmgmt-vds01-mgmt-01a` (dvportgroup-25), static 10.1.1.85–.89, gw 10.1.1.1, DNS/NTP 10.1.1.1 |
| Storage policy | `cluster-mgmt-01a vSAN Storage Policy` (890c69a1…) for control plane, ephemeral and image storage |
| Workload network | NSX VPC, project `/orgs/default/projects/default`, connectivity profile `default` (external block `dtgw-01a` 10.1.7.128/25 on VLAN 22), default private CIDR 172.16.202.0/24 |
| Services CIDR | 10.96.0.0/23 |
| Kubernetes content library | `VKS-mgmt` (subscribed, on demand, https://wp-content.broadcom.com/v2/latest/lib.json), id 22cfea10-7f27-4b02-9613-eeb70f553cf3 |

Prerequisites that already existed in the management NSX (nsx-mgmt-a): VNA cluster
`vna-cluster-mgmt-a` with vna-mgmt-01a/02a, default transit gateway attached to the
distributed VLAN connection `distributed-gw-mgmt-a` (VLAN 22, 10.1.7.129/25).

Order: `./rebuild.sh disable` (about 45 min) → `./rebuild.sh enable` → `./rebuild.sh wait`
(about 35 min). Then in VCF Automation (provider): Infrastructure → Regions → add the new
Supervisor as region `mgmt-a`; see `../platform-ops/README.md` for the org and the tenant network.
