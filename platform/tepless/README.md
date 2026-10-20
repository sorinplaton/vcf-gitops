# TEP-less demo: VKS on a VLAN-backed VPC (VCF 9.1.1)

The workload domain `tepless-wkld` uses VLAN-backed VPCs: no NSX tunnel endpoints (TEPs) on
the ESX hosts, no overlay MTU requirement. These manifests build the tenant side through
VCF Automation (organization `tepless`, region `tepless`). They were applied in this order
on 2026-10-20 as `admin-tepless@tepless`.

| File | Object | Result | Time |
|---|---|---|---|
| `01-vpc.yaml` | VPC (no private ranges) | `vpc-tepless-demo-p5gsf`, Realized | 11:26:28 |
| `02-vpc-attach-lb.yaml` | VPC attachment to the transit gateway + NSX load balancer | both Realized | +22 s |
| `03-namespace.yaml` | Supervisor namespace, class `small`, zone-11 | `tepless-demo-4tvk7`, Created | +70 s |
| `04-subnetset-public.yaml` | SubnetSet `public`, access mode Public, 32 addresses | Ready | +22 s |

Two VKS clusters use this namespace: `tepless-demo`, built in the VCF Automation UI (Custom
Configuration, custom primary network = `public`), and `tepless-demo2`, applied from Git:
`clusters/tepless-demo2/cluster.yaml`. VCF Automation generated the same `networks` variable as that file.

## Apply tepless-demo2 from Git

```bash
RAW=https://raw.githubusercontent.com/sorinplaton/vcf-gitops/main/clusters/tepless-demo2/cluster.yaml
kubectl apply -f $RAW          # with a kubectl context on the namespace tepless-demo-4tvk7
kubectl -n tepless-demo-4tvk7 get cluster,machines -w
```

## Networks: Day-0 and Day-1

| | Day-0 (SDDC Manager) | Day-1 (VCF Automation) |
|---|---|---|
| VLAN / range | 202, 10.202.202.0/24 | 203, 10.203.203.0/24 |
| Used by | the Supervisor and its system VPCs | organization VPCs, VKS nodes, public subnets, LB addresses |
| NSX objects | "Day0 Distributed Vlan Connection / External Ip Block - tepless-wkld" | `d-tepless-203`, `:tepless-203` |

VCF Automation creates its own external IP block in NSX and cannot overlap the Day-0 block,
so the region needs its own VLAN. The gateway for VLAN 203 is on the holorouter:
`lab/holodeck/holo-vlan203.sh`.

## Gotchas found while building
- VCF Automation must refresh the workload vCenter inventory before it accepts a new Supervisor
  ("zones ... do not have a network stack configured").
- A namespace created through the API needs its zone (with CPU/memory limit and reservation)
  and storage class set when the namespace class does not define them.
- The namespace reports `DefaultVmNetworkMissing` and `DefaultPodNetworkMissing`: a VLAN-backed
  VPC has no private default network, so VKS needs the Public SubnetSet and Custom Configuration.
- The Public SubnetSet is created lazily: NSX carves the 10.203.203.x subnet when the first node attaches.
