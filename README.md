# vcf-gitops

Git source of truth for a VCF lab, reconciled by Argo CD.

- `clusters/` - VKS cluster definitions (Cluster API `Cluster` objects), applied to a Supervisor namespace
- `apps/` - workloads deployed inside those clusters
