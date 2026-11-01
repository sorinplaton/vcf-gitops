#!/usr/bin/env bash
# Rebuild the management-domain Supervisor (cluster-mgmt-01a, vc-mgmt-a) with NSX VPC networking.
#
#   ./rebuild.sh status    # Supervisor state (config_status / kubernetes_status)
#   ./rebuild.sh disable   # DESTRUCTIVE: removes the current Supervisor (vSphere-network, no LB, no services)
#   ./rebuild.sh enable    # enable from enable-spec.json (NSX VPC, Supervisor Services, 1 x SMALL)
#   ./rebuild.sh wait      # poll until RUNNING / READY
#
# Why: the Supervisor created on 2026-10-21 used vSphere networking with no load balancer and
# Supervisor Services off. Argo CD as a VCF Service, VKS clusters and LoadBalancer services need
# NSX VPC networking plus vSphere Pods, and VCF Automation only registers NSX VPC Supervisors as regions.
# Password: $VC_PASSWORD, or the vc-mgmt-a administrator entry of ~/passwords-holodeck.json.
set -euo pipefail
cd "$(dirname "$0")"
VC=https://vc-mgmt-a.site-a.vcf.lab
CLUSTER=domain-c9

pw() {
  if [ -n "${VC_PASSWORD:-}" ]; then echo "$VC_PASSWORD"; return; fi
  python3 -c "
import json; d=json.load(open('$HOME/passwords-holodeck.json'))
c=[x for x in d['components'] if x['FQDN'].startswith('vc-mgmt-a')][0]
print([k for k in c['credentials'] if k['user']=='administrator@vsphere.local'][0]['password'])"
}
TOKEN=$(curl -sk -m 30 -u "administrator@vsphere.local:$(pw)" -X POST "$VC/api/session" | tr -d '"')
[ -n "$TOKEN" ] && [ "${#TOKEN}" -lt 100 ] || { echo "vCenter login failed"; exit 1; }
vc() { curl -sk -m 120 -H "vmware-api-session-id: $TOKEN" -H 'Content-Type: application/json' "$@"; }

status() {
  vc "$VC/api/vcenter/namespace-management/clusters/$CLUSTER" | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: print("no Supervisor on the cluster"); sys.exit()
if "messages" in d and "config_status" not in d: print(d); sys.exit()
print("config:", d.get("config_status"), " kubernetes:", d.get("kubernetes_status"), " network:", d.get("network_provider"),
      " api:", d.get("api_server_cluster_endpoint"), " services:", d.get("supervisor_services_enabled"), " pods:", d.get("vsphere_pods_enabled"))
for m in d.get("messages", [])[:5]: print("  ", m.get("severity"), m.get("details", {}).get("default_message"))'
}

disable() {
  echo "Disabling the Supervisor on $CLUSTER (vc-mgmt-a) at $(date '+%F %T')"
  code=$(vc -o /dev/null -w '%{http_code}' -X POST "$VC/api/vcenter/namespace-management/clusters/$CLUSTER?action=disable")
  echo "HTTP $code"; [ "$code" = 204 ] || [ "$code" = 202 ]
  for _ in $(seq 90); do   # ~45 min
    sleep 30
    if ! vc "$VC/api/vcenter/namespace-management/clusters/$CLUSTER" | grep -q config_status; then echo "$(date '+%T') Supervisor removed"; return 0; fi
    printf '%s %s\n' "$(date '+%T')" "$(status | head -1)"
  done
  echo "still removing after 45 min"; return 1
}

enable() {
  echo "Enabling Supervisor from enable-spec.json at $(date '+%F %T')"
  code=$(vc -o /tmp/enable.$$ -w '%{http_code}' -X POST "$VC/api/vcenter/namespace-management/supervisors/$CLUSTER?action=enable_on_compute_cluster" -d @enable-spec.json)
  echo "HTTP $code"; cat /tmp/enable.$$; echo; rm -f /tmp/enable.$$
  [ "$code" = 200 ] || [ "$code" = 204 ]
}

wait_ready() {
  for _ in $(seq 120); do   # ~60 min
    s=$(status | head -1); printf '%s %s\n' "$(date '+%T')" "$s"
    echo "$s" | grep -q 'config: RUNNING .*kubernetes: READY' && return 0
    sleep 30
  done
  return 1
}

case "${1:-status}" in
  status) status ;;
  disable) disable ;;
  enable) enable ;;
  wait) wait_ready ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
