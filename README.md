# vcf-gitops

Git source of truth for the lab behind the blog "Six VMs from one commit": one commit
creates a VKS cluster of six virtual machines on VMware Cloud Foundation through Argo CD,
and a second Argo CD target deploys an application inside that cluster.

Blog: <link to come>

## Folder map

| Folder | What it holds | Live or example |
|---|---|---|
| `clusters/` | VKS cluster definitions (Cluster API `Cluster` objects). `clusters/demo-vks-cluster/cluster.yaml` is the six-VM cluster (3 control plane, 3 workers). | **Live.** Watched by Argo CD. |
| `apps/` | Workloads deployed inside the VKS cluster. `apps/podinfo/podinfo.yaml` is the podinfo Deployment and LoadBalancer Service. | **Live.** Watched by Argo CD. |
| `argocd-apps/` | The Argo CD `Application` objects themselves, exported from the lab ("app of apps"). `root.yaml` is the parent application. | The three child files match what is live. `root.yaml` is **not applied** (see its header). |
| `platform/argocd/` | The `ArgoCD` object and the two config maps of the Argo CD instance, exported from the lab. | Copy of what is live. Reference only. |
| `examples/` | The recommendations from Part 2 of the blog: RBAC policy, AppProjects, cluster protection. | **Examples. Not applied in the lab.** |
| `lab/` | Lab plumbing outside Kubernetes: holorouter VLAN 200/203/204 and DNS redirect, VyOS route, jump host note. | Transcribed, not copied from the devices (see the first line of each file). |
| `tools/capture/` | The headed-browser screenshot tools used for the blog captures. | Tooling. |
| `platform/mgmt-supervisor/` | Rebuild of the management-domain Supervisor with NSX VPC networking (enable spec + script). | Applied by hand, 2026-11-01. |
| `platform/platform-ops/` | Argo CD as a VCF Service (9.1.1 tech preview) for the `platform-ops` org, region `mgmt-a`: VPC, namespace, instance, ManagedEntities, `apply.sh`. | Applied through the VCF Automation API. |
| `clusters/mon-mgmt/` | The monitoring VKS cluster in the management domain (1 control plane + 2 workers). | **Live.** Watched by the platform-ops Argo CD. |
| `apps/monitoring/` | vCenter + iDRAC exporters, ServiceMonitors and the lab Grafana dashboards (Kustomize). Secrets only as `secrets.example/`. | **Live.** Watched by the platform-ops Argo CD. |
| `argocd-apps-mgmt/` | The three `Application` objects of the platform-ops instance: `mon-mgmt-cluster`, `monitoring-stack` (kube-prometheus-stack Helm chart), `monitoring-exporters`. | Match what is live. |

## What Argo CD watches

Argo CD (instance `argocd-1`, namespace `argocd-demo-wqfbg`) reads two paths on `main`:

| Application | Path | Target | Sync |
|---|---|---|---|
| `demo-vks-cluster` | `clusters/demo-vks-cluster` | Supervisor namespace `podinfo-demo-vkjhr` | manual |
| `podinfo-vks` | `apps/podinfo` | VKS cluster `https://10.200.200.7:6443`, namespace `podinfo` | automated, self-heal, prune |

A third application, `podinfo`, deploys the podinfo Helm chart (`6.*`, from
`https://stefanprodan.github.io/podinfo`) as vSphere Pods into the Supervisor namespace;
its source is the Helm repository, not this repository.

Nothing else in this repository is read by Argo CD. A change under `clusters/` or
`apps/` on `main` changes the lab; a change anywhere else does not.

### platform-ops instance (management domain, 9.1.1 tech preview)

The second instance, `argocd-platform` (org `platform-ops`, region `mgmt-a`, namespace
`platform-ops-<suffix>`), reads three sources; see `platform/platform-ops/README.md` for how it was built.

| Application | Source | Target | Sync |
|---|---|---|---|
| `mon-mgmt-cluster` | `clusters/mon-mgmt` | Supervisor namespace `platform-ops-<suffix>` (ManagedEntity `platform-ops`) | manual, no prune |
| `monitoring-stack` | Helm chart `kube-prometheus-stack` 92.17.0 from prometheus-community | VKS cluster `mon-mgmt`, namespace `monitoring` | automated, self-heal, prune |
| `monitoring-exporters` | `apps/monitoring` | VKS cluster `mon-mgmt`, namespace `monitoring` | automated, self-heal, prune |

## Applying the app of apps

`argocd-apps/root.yaml` is committed but not applied: the hosting namespace is not a
registered Argo CD target in the lab, and the instance runs with
`cluster.inClusterEnabled=false`. Its header lists what has to be true first. Keep its
sync policy manual with no prune: pruning a child `Application` deletes what that
application created, and for `demo-vks-cluster` that is the six VMs.
