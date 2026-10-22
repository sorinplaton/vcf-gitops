# Argo CD as a VCF Service (VCF 9.1.1 tech preview)

Replaces the Supervisor-mode instance `argocd-1` in `argocd-demo-xxms8` (deleted 2026-10-21;
backup on the jump host in `~/argocd-backup-20261021/`). Org `holo-east`, region `east-1`.

| File | What | Applied through |
|---|---|---|
| 01-vpc.yaml | VPC `vpc-argocd-gitops` | VCF Automation CCI API |
| 02-vpc-attach-lb.yaml | transit-gateway attachment + NSX load balancer | VCF Automation CCI API |
| 03-namespace.yaml | Supervisor namespace `argocd-gitops-<suffix>` (class medium; generateName, created once) | VCF Automation CCI API |
| 04-argocd-instance.yaml | the `ArgoCD` instance `argocd-gitops` | the namespace endpoint (`status.namespaceEndpointURL`) |
| later/05-argocd-securitypolicy.yaml | DFW allow + default-deny, copied from the old namespace | Supervisor API, only after SSO works |

Order: `./apply.sh network`, install the Argo CD VCF Service in the VCF Automation Provider UI
(Service Management > VCF Services), `./apply.sh instance`, then give
`status.serviceAccounts.platform` the ArgoCD Instance role and log in with
`vcf argocd login <externalIP> --sso`.

Notes from the lab:
- VCF Automation's CCI API created the VPC, attachment and load balancer on `kubectl apply --dry-run=server`
  (2026-10-21); SupervisorNamespace rejects dry runs outright. Don't rely on dry runs there.
- The firewall policy is held back because the old load-balancer source range (100.64.32.0/24) belongs to the
  old VPC and the SSO path to VCF Automation is not in it yet.
