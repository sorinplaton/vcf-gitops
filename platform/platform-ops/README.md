# platform-ops: Argo CD as a VCF Service on the management domain

Org `platform-ops`, region `mgmt-a` (the rebuilt Supervisor on `cluster-mgmt-01a`, see
`../mgmt-supervisor/`). The org owns the GitOps and monitoring tooling of the lab; the
application tenants (`holo-east`, `tepless`) stay separate.

## Provider steps (VCF Automation UI, once)

Done by the provider admin (`admin@System`); the API path was not used for these.

1. **Tenant network on the holorouter**: `lab/holodeck/holo-vlan204.sh` + `.service`
   (VLAN 204, gateway 10.204.204.1/24, UDP DNS redirect). Jump host and photon-frr need a route
   `10.204.204.0/24 via 10.0.6.33`.
2. **Region** `mgmt-a`: Infrastructure → Regions → create from Supervisor `supervisor-mgmt-a`
   (vc-mgmt-a). Zone `zone-mgmt-a`, storage policy `cluster-mgmt-01a vSAN Storage Policy`,
   VM classes `best-effort-small`, `best-effort-medium` (and xsmall).
3. **External network for the region**: distributed VLAN connection `d-platform-204`
   (VLAN 204, gateway 10.204.204.1/24) and external IP block `platform-204` 10.204.204.0/24 in
   nsx-mgmt-a. VCF Automation cannot reuse the Day-0 block `dtgw-01a` (10.1.7.128/25, VLAN 22):
   "IP Space Block … is not found" (lesson from the tepless region, 2026-10-20).
4. **Org** `platform-ops` with local admin `platform-admin` (lab password), then
   **region quota** in `mgmt-a`: 40 GHz / 96 GB / 500 GB to start, the two VM classes above,
   the vSAN storage policy, and the VLAN 204 external network shared into the org
   (TGW / connectivity profile `default--mgmt-a` with service gateway + SNAT, and a VPC load balancer).
5. **Argo CD VCF Service**: Service Management → VCF Services → Argo CD → Install, target
   region `mgmt-a` (version 1.2.0-25642124 on this build). This is the tech-preview part.

## Tenant steps (this folder, as platform-admin@platform-ops)

| File | What | Applied through |
|---|---|---|
| 01-vpc.yaml | VPC `vpc-platform-ops` | VCF Automation CCI API |
| 02-vpc-attach-lb.yaml | transit-gateway attachment + NSX load balancer | VCF Automation CCI API |
| 03-namespace.yaml | Supervisor namespace `platform-ops-<suffix>` (class medium; generateName, created once) | VCF Automation CCI API |
| 04-argocd-instance.yaml | the `ArgoCD` instance `argocd-platform` | the namespace endpoint (`status.namespaceEndpointURL`) |
| 05-rbac.yaml | RoleBinding `edit` in the hosting namespace for the instance's `argocd-k8s-sa` | Supervisor API |
| 05-managed-entities.yaml | registers the namespace itself (`platform-ops`) and the VKS cluster `mon-mgmt` | Supervisor API (`-n platform-ops-<suffix>`) |

Order: `./apply.sh network` → provider installs the Argo CD VCF Service → `./apply.sh instance`
→ give `status.serviceAccounts.platform` the **ArgoCD Instance** role in the org → `vcf argocd login <externalIP> --sso`
→ `./apply.sh register` → then the Applications in `argocd-apps-mgmt/`.

The VKS cluster `mon-mgmt` (clusters/mon-mgmt) is created **by Argo CD** from
`argocd-apps-mgmt/mon-mgmt-cluster.yaml`; its ManagedEntity becomes Ready once the cluster exists,
so apply `05-managed-entities.yaml` again after the first sync if the `mon-mgmt` entry shows Failed
(a ManagedEntity created before its target does not retry; delete and re-apply it).

Notes carried over from `../argocd-vcfa/README.md`: the CCI API creates objects on
`--dry-run=server`; SupervisorNamespace only accepts generateName; the instance ships with an
empty Argo CD RBAC policy, so `spec.rbac` in 04 maps the VCF Automation user ids to roles.
