#!/usr/bin/env bash
# Argo CD as a VCF Service (VCF 9.1.1 tech preview) for org holo-east, region east-1.
#
#   ./apply.sh network    # 01-03: VPC, attachment + load balancer, namespace argocd-gitops
#   ./apply.sh instance   # 04: the ArgoCD instance (needs the VCF Service installed in VCF Automation)
#   ./apply.sh status     # what exists so far
#
# Logs in to VCF Automation as holo-east-admin@holo-east. Password: $VCFA_PASSWORD, or the
# vc-mgmt-a administrator entry of ~/passwords-holodeck.json (the shared lab password).
set -euo pipefail
cd "$(dirname "$0")"

VCFA=https://auto-a.site-a.vcf.lab
USER_ORG=holo-east-admin@holo-east
NS=argocd-gitops
VPC=vpc-argocd-gitops

pw() {
  if [ -n "${VCFA_PASSWORD:-}" ]; then echo "$VCFA_PASSWORD"; return; fi
  python3 -c "
import json; d=json.load(open('$HOME/passwords-holodeck.json'))
c=[x for x in d['components'] if x['FQDN'].startswith('vc-mgmt-a')][0]
print([k for k in c['credentials'] if k['user']=='administrator@vsphere.local'][0]['password'])"
}

TOKEN=$(curl -sk -m 30 -D - -o /dev/null -u "$USER_ORG:$(pw)" -X POST \
  -H 'Accept: application/json;version=40.0' "$VCFA/cloudapi/1.0.0/sessions" |
  awk -F': ' 'tolower($1)=="x-vmware-vcloud-access-token"{print $2}' | tr -d '\r')
[ -n "$TOKEN" ] || { echo "VCF Automation login failed"; exit 1; }
cci() { kubectl --server "$VCFA/cci/kubernetes" --insecure-skip-tls-verify --token "$TOKEN" --request-timeout=60s -n default-project "$@"; }

wait_for() {  # wait_for <description> <command that prints something non-empty when done> [tries]
  local what=$1 cmd=$2 tries=${3:-60}
  for _ in $(seq "$tries"); do
    if [ -n "$(eval "$cmd" 2>/dev/null)" ]; then echo "  ok: $what"; return 0; fi
    sleep 10
  done
  echo "  TIMEOUT waiting for: $what"; return 1
}

network() {
  echo "== 01 VPC $VPC"
  cci apply -f 01-vpc.yaml
  wait_for "VPC realized" "cci get vpc $VPC --no-headers | grep -w Realized"
  echo "== 02 attachment + load balancer"
  cci apply -f 02-vpc-attach-lb.yaml
  wait_for "attachment realized" "cci get vpcattachment $VPC:default --no-headers | grep -w Realized"
  wait_for "load balancer realized" "cci get loadbalancer $VPC:default --no-headers | grep -w Realized"
  echo "== 03 namespace $NS"
  cci apply -f 03-namespace.yaml
  wait_for "namespace Created" "cci get supervisornamespace $NS --no-headers | grep -w Created" 90
}

instance() {
  local ep
  ep=$(cci get supervisornamespace "$NS" -o jsonpath='{.status.namespaceEndpointURL}')
  [ -n "$ep" ] || { echo "namespace $NS not ready; run ./apply.sh network first"; exit 1; }
  nsk() { kubectl --server "$ep" --insecure-skip-tls-verify --token "$TOKEN" --request-timeout=60s -n "$NS" "$@"; }
  echo "== supported Argo CD versions"
  nsk get argocdversion argocd-supported-versions -o jsonpath='{.spec}' 2>/dev/null || \
    echo "  (ArgoCDVersion not visible yet: is the VCF Service installed in VCF Automation?)"
  echo; echo "== 04 ArgoCD instance"
  nsk apply -f 04-argocd-instance.yaml
  wait_for "instance Ready" "nsk get argocd argocd-gitops -o jsonpath='{.status.phase}' | grep -x Ready" 90 || true
  nsk get argocd argocd-gitops -o jsonpath='{"phase: "}{.status.phase}{"\nexternal IP: "}{.status.externalIP}{"\nservice accounts: "}{.status.serviceAccounts}{"\n"}'
  echo "Next: give the 'platform' service account above the ArgoCD Instance role in the VCF Automation Provider UI."
}

status() {
  cci get vpc,vpcattachment,loadbalancer --no-headers 2>/dev/null | grep "$VPC" || echo "no VPC yet"
  cci get supervisornamespace "$NS" 2>/dev/null || echo "no namespace yet"
}

case "${1:-status}" in
  network) network ;;
  instance) instance ;;
  status) status ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
