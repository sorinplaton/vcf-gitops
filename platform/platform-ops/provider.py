#!/usr/bin/env python3
"""Provider-side setup of org platform-ops / region mgmt-a in VCF Automation 9.1.1 (admin@System).

  provider.py status    # what exists
  provider.py region    # region mgmt-a from supervisor-mgmt-a (nsx-mgmt-a, cluster-mgmt-01a vSAN policy)
  provider.py network   # IP space platform-204 (10.204.204.0/24) + distributed VLAN connection d-platform-204 (VLAN 204)
  provider.py org       # org platform-ops (networking tenancy on) + local Organization Administrator platform-admin
  provider.py quota     # region quota platform-ops_mgmt-a: 40 GHz / 96 GB, vSAN policy 500 GB, VM classes
  provider.py rns       # regional networking settings: org <-> VLAN 204 connection + VNA cluster vna-cluster-mgmt-a
  provider.py all       # all of the above, in order, idempotent (looks everything up by name first)

API: /cloudapi/v1/... with Accept version 9.1.1 (the 9.0 paths /cloudapi/vcf/... still answer for reads).
Password: $VCFA_PASSWORD, or the vc-mgmt-a administrator entry of ~/passwords-holodeck.json; the new
platform-admin gets the same lab password unless $PLATFORM_ADMIN_PASSWORD is set.
"""
import base64, json, os, ssl, sys, time, urllib.error, urllib.request

V = "https://auto-a.site-a.vcf.lab"
A = "application/json;version=9.1.1"
CTX = ssl._create_unverified_context()

REGION, ORG, USER = "mgmt-a", "platform-ops", "platform-admin"
SUPERVISOR, NSX = "supervisor-mgmt-a", "nsx-mgmt-a.site-a.vcf.lab"
STORAGE_POLICY = "cluster-mgmt-01a vSAN Storage Policy"
IPSPACE, CIDR = "platform-204", "10.204.204.0/24"
DVLAN, VLAN, GATEWAY = "d-platform-204", 204, "10.204.204.1/24"
VNA = "vna-cluster-mgmt-a"
QUOTA = {"memoryLimitMiB": 98304, "memoryReservationMiB": 0, "cpuLimitMHz": 40000, "cpuReservationMHz": 0}
STORAGE_LIMIT_MIB = 512000
VM_CLASSES = ["best-effort-xsmall", "best-effort-small", "best-effort-medium", "best-effort-large"]


def lab_password():
    if os.environ.get("VCFA_PASSWORD"):
        return os.environ["VCFA_PASSWORD"]
    d = json.load(open(os.path.expanduser("~/passwords-holodeck.json")))
    c = [x for x in d["components"] if x["FQDN"].startswith("vc-mgmt-a")][0]
    return [k for k in c["credentials"] if k["user"] == "administrator@vsphere.local"][0]["password"]


class Api:
    def __init__(self):
        r = urllib.request.Request(V + "/cloudapi/1.0.0/sessions/provider", method="POST", headers={
            "Accept": A, "Authorization": "Basic " + base64.b64encode(f"admin@System:{lab_password()}".encode()).decode()})
        self.tok = urllib.request.urlopen(r, context=CTX, timeout=60).headers["x-vmware-vcloud-access-token"]

    def call(self, method, path, body=None, org=None, wait=True):
        h = {"Accept": A, "Authorization": "Bearer " + self.tok, "Content-Type": "application/json"}
        if org:
            h["X-VMWARE-VCLOUD-TENANT-CONTEXT"] = org.split(":")[-1]
        r = urllib.request.Request(V + path, method=method, headers=h, data=json.dumps(body).encode() if body is not None else None)
        try:
            resp = urllib.request.urlopen(r, context=CTX, timeout=120)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {e.read().decode()[:400]}")
        data = resp.read().decode()
        if resp.status == 202 and wait:            # async: follow the task in the Location header
            t = self.wait_task(resp.headers.get("Location"))
            owner = t.get("owner") or {}              # the object the task created/modified
            return {"id": owner.get("id"), "name": owner.get("name"), "task": t} if owner.get("id") else {"task": t}
        return json.loads(data) if data.strip().startswith(("{", "[")) else data

    def wait_task(self, url, tries=120):
        # 202 answers point at the legacy task API (/api/task/<id>), which wants the legacy Accept header
        path = url.replace(V, "")
        for _ in range(tries):
            r = urllib.request.Request(V + path, headers={"Accept": "application/*+json;version=40.0", "Authorization": "Bearer " + self.tok})
            t = json.loads(urllib.request.urlopen(r, context=CTX, timeout=60).read())
            if t.get("status") == "success":
                return t
            if t.get("status") in ("error", "aborted"):
                raise RuntimeError(f"task failed: {t.get('details') or t.get('error')}")
            print(f"  task {t.get('operationName') or t.get('operation')} {t.get('status')} {t.get('progress', '')}%", flush=True)
            time.sleep(10)
        raise RuntimeError("task timeout")

    def get(self, path, org=None):
        return self.call("GET", path, org=org)

    def find(self, path, name, key="name", org=None):
        d = self.get(path + ("&" if "?" in path else "?") + "pageSize=100", org=org)
        return next((v for v in d.get("values", []) if v.get(key) == name), None)

    def wait_status(self, path, ok=("READY", "REALIZED"), tries=120, label=""):
        for _ in range(tries):
            d = self.get(path)
            s = d.get("status") or d.get("creationStatus")
            if s in ok:
                return d
            if s and ("FAIL" in s or "ERROR" in s):
                raise RuntimeError(f"{label} status {s}: {json.dumps(d)[:300]}")
            print(f"  {label} status {s} ...", flush=True); time.sleep(10)
        raise RuntimeError(f"{label} not ready")


api = Api()


def region():
    r = api.find("/cloudapi/v1/regions", REGION)
    if not r:
        sup = api.find("/cloudapi/v1/supervisors", SUPERVISOR)
        nsx = api.find("/cloudapi/v1/nsxManagers", NSX)
        if sup.get("region"):
            raise RuntimeError(f"{SUPERVISOR} already belongs to region {sup['region']['name']}")
        print(f"== creating region {REGION} from {SUPERVISOR} ({sup['supervisorId']}) on {NSX}")
        r = api.call("POST", "/cloudapi/v1/regions", {"name": REGION, "description": "management domain (platform-ops)",
                     "nsxManager": {"id": nsx["id"]}, "supervisors": [{"id": sup["supervisorId"]}], "storagePolicies": [STORAGE_POLICY]})
        if "id" not in r:
            r = api.find("/cloudapi/v1/regions", REGION)
    r = api.wait_status(f"/cloudapi/v1/regions/{r['id']}", label="region")
    print(f"  region {REGION} {r['status']} id {r['id']}  cpu {r.get('cpuCapacityMHz')} MHz  mem {r.get('memoryCapacityMiB')} MiB")
    return r


def network():
    r = api.find("/cloudapi/v1/regions", REGION)
    ips = api.find("/cloudapi/v1/ipSpaces", IPSPACE)
    if not ips:
        print(f"== creating IP space {IPSPACE} {CIDR}")
        ips = api.call("POST", "/cloudapi/v1/ipSpaces", {"name": IPSPACE, "description": "platform-ops tenant block (VLAN 204)",
                       "internalScopeCidrBlocks": [{"cidr": CIDR}], "regionRef": {"id": r["id"]}, "subnetExclusive": False,
                       "providerVisibilityOnly": False})
        if "id" not in ips:
            ips = api.find("/cloudapi/v1/ipSpaces", IPSPACE)
    ips = api.wait_status(f"/cloudapi/v1/ipSpaces/{ips['id']}", label="ip space")
    print(f"  ip space {IPSPACE} {ips['status']} {ips['id']}")
    dv = api.find("/cloudapi/v1/distributedVlanConnections", DVLAN)
    if not dv:
        print(f"== creating distributed VLAN connection {DVLAN} (VLAN {VLAN}, {GATEWAY})")
        dv = api.call("POST", "/cloudapi/v1/distributedVlanConnections", {"name": DVLAN, "description": "platform-ops org network",
                      "vlanId": VLAN, "gatewayCidr": GATEWAY, "regionRef": {"id": r["id"]}, "ipSpaceRef": {"id": ips["id"]},
                      "subnetExclusive": False})
        if "id" not in dv:
            dv = api.find("/cloudapi/v1/distributedVlanConnections", DVLAN)
    dv = api.wait_status(f"/cloudapi/v1/distributedVlanConnections/{dv['id']}", label="vlan connection")
    print(f"  vlan connection {DVLAN} {dv['status']} {dv['id']}")
    return ips, dv


def org():
    o = api.find("/cloudapi/1.0.0/orgs", ORG)
    if not o:
        print(f"== creating org {ORG}")
        o = api.call("POST", "/cloudapi/1.0.0/orgs", {"name": ORG, "displayName": ORG, "isEnabled": True, "canManageOrgs": False,
                     "description": "Platform operations: Argo CD (VCF Service, tech preview) and monitoring"})
        if "id" not in o:
            o = api.find("/cloudapi/1.0.0/orgs", ORG)
    ns = api.get(f"/cloudapi/1.0.0/orgs/{o['id']}/networkingSettings")
    if not ns.get("networkingTenancyEnabled"):
        print("== enabling networking tenancy")
        ns["networkingTenancyEnabled"] = True
        api.call("PUT", f"/cloudapi/1.0.0/orgs/{o['id']}/networkingSettings", ns)
    print(f"  org {ORG} {o['id']} networking tenancy on")
    u = api.find("/cloudapi/1.0.0/users", USER, key="username", org=o["id"])
    if not u:
        role = api.find("/cloudapi/1.0.0/roles", "Organization Administrator", org=o["id"])
        print(f"== creating user {USER} (Organization Administrator)")
        u = api.call("POST", "/cloudapi/1.0.0/users", {"username": USER, "password": os.environ.get("PLATFORM_ADMIN_PASSWORD") or lab_password(),
                     "fullName": "Platform admin", "roleEntityRefs": [{"id": role["id"]}], "orgEntityRef": {"id": o["id"]},
                     "providerType": "LOCAL", "enabled": True}, org=o["id"])
    print(f"  user {USER}@{ORG} {u.get('id')}")
    return o


def quota():
    r = api.find("/cloudapi/v1/regions", REGION); o = api.find("/cloudapi/1.0.0/orgs", ORG)
    sup = api.find("/cloudapi/v1/supervisors", SUPERVISOR)
    zone = next(z for z in api.get("/cloudapi/v1/zones?pageSize=100")["values"] if z["region"]["id"] == r["id"])
    name = f"{ORG}_{REGION}"
    vdc = api.find("/cloudapi/v1/virtualDatacenters", name)
    if not vdc:
        print(f"== creating region quota {name} in zone {zone['name']}: {QUOTA}")
        vdc = api.call("POST", "/cloudapi/v1/virtualDatacenters", {"name": name, "org": {"id": o["id"]}, "region": {"id": r["id"]},
                       "supervisors": [{"id": sup["supervisorId"]}], "isFullAllocation": False,
                       "zoneResourceAllocation": [{"zone": {"id": zone["id"]}, "resourceAllocation": QUOTA}]})
        if "id" not in vdc:
            vdc = api.find("/cloudapi/v1/virtualDatacenters", name)
    vdc = api.wait_status(f"/cloudapi/v1/virtualDatacenters/{vdc['id']}", label="quota")
    print(f"  quota {name} {vdc['status']} {vdc['id']}")
    rsp = next(p for p in api.get("/cloudapi/v1/regionStoragePolicies?pageSize=100")["values"] if p["region"]["id"] == r["id"] and p["name"] == STORAGE_POLICY)
    sps = [p for p in api.get("/cloudapi/v1/virtualDatacenterStoragePolicies?pageSize=100")["values"] if p["virtualDatacenter"]["id"] == vdc["id"]]
    if not sps:
        print(f"== adding storage policy {STORAGE_POLICY} ({STORAGE_LIMIT_MIB} MiB)")
        api.call("POST", "/cloudapi/v1/virtualDatacenterStoragePolicies", {"values": [{"virtualDatacenter": {"id": vdc["id"]},
                 "regionStoragePolicy": {"id": rsp["id"]}, "storageLimitMiB": STORAGE_LIMIT_MIB}]})
    have = {c["name"] for c in api.get(f"/cloudapi/v1/virtualDatacenters/{vdc['id']}/virtualMachineClasses?pageSize=100")["values"]}
    want = [c for c in api.get(f"/cloudapi/v1/virtualMachineClasses?pageSize=100&filter=(region.id=={r['id']})")["values"] if c["name"] in VM_CLASSES]
    if not set(VM_CLASSES) <= have:
        print(f"== assigning VM classes {VM_CLASSES}")
        body = {"values": [{"id": c["id"], "name": c["name"]} for c in want]}
        try:
            api.call("PUT", f"/cloudapi/v1/virtualDatacenters/{vdc['id']}/virtualMachineClasses", body)
        except RuntimeError as e:
            print(f"  PUT failed ({str(e)[:120]}), trying POST"); api.call("POST", f"/cloudapi/v1/virtualDatacenters/{vdc['id']}/virtualMachineClasses", body)
    print("  storage policies:", [(p["name"], p["storageLimitMiB"]) for p in api.get("/cloudapi/v1/virtualDatacenterStoragePolicies?pageSize=100")["values"] if p["virtualDatacenter"]["id"] == vdc["id"]])
    print("  vm classes:", sorted(c["name"] for c in api.get(f"/cloudapi/v1/virtualDatacenters/{vdc['id']}/virtualMachineClasses?pageSize=100")["values"]))
    return vdc


def rns():
    r = api.find("/cloudapi/v1/regions", REGION); o = api.find("/cloudapi/1.0.0/orgs", ORG)
    dv = api.find("/cloudapi/v1/distributedVlanConnections", DVLAN)
    vna = next(v for v in api.get("/cloudapi/v1/virtualNetworkApplianceClusters?pageSize=100")["values"] if v["regionRef"]["id"] == r["id"])
    name = f"{ORG}-{REGION}"
    s = next((x for x in api.get("/cloudapi/v1/regionalNetworkingSettings?pageSize=100")["values"] if x["orgRef"]["id"] == o["id"] and x["regionRef"]["id"] == r["id"]), None)
    if not s:
        print(f"== creating regional networking settings {name}: {DVLAN} + {vna['name']}")
        s = api.call("POST", "/cloudapi/v1/regionalNetworkingSettings", {"name": name, "regionRef": {"id": r["id"]}, "orgRef": {"id": o["id"]},
                     "distributedVlanConnectionRef": {"id": dv["id"]}, "virtualNetworkApplianceClusterRef": {"id": vna["id"]}})
        if "id" not in s:
            s = next(x for x in api.get("/cloudapi/v1/regionalNetworkingSettings?pageSize=100")["values"] if x["orgRef"]["id"] == o["id"] and x["regionRef"]["id"] == r["id"])
    s = api.wait_status(f"/cloudapi/v1/regionalNetworkingSettings/{s['id']}", label="regional networking")
    print(f"  regional networking {s['name']} {s['status']}")
    tg = [t for t in api.get("/cloudapi/v1/transitGateways?pageSize=100").get("values", []) if t.get("orgRef", {}).get("id") == o["id"]]
    print("  transit gateways:", [(t["name"], t["status"]) for t in tg])
    return s


def status():
    for path, key in [("/cloudapi/v1/regions", "name"), ("/cloudapi/v1/supervisors", "name"), ("/cloudapi/v1/zones", "name"),
                      ("/cloudapi/v1/ipSpaces", "name"), ("/cloudapi/v1/distributedVlanConnections", "name"),
                      ("/cloudapi/1.0.0/orgs", "name"), ("/cloudapi/v1/virtualDatacenters", "name"),
                      ("/cloudapi/v1/regionalNetworkingSettings", "name"), ("/cloudapi/v1/transitGateways", "name"),
                      ("/cloudapi/v1/virtualNetworkApplianceClusters", "name")]:
        vals = api.get(path + "?pageSize=100").get("values", [])
        print(f"{path.split('/')[-1]:32s}", [(v.get(key), v.get("status") or v.get("creationStatus") or (v.get("region") or {}).get("name")) for v in vals])


if __name__ == "__main__":
    steps = {"status": status, "region": region, "network": network, "org": org, "quota": quota, "rns": rns}
    arg = sys.argv[1] if len(sys.argv) > 1 else "status"
    if arg == "all":
        for f in (region, network, org, quota, rns):
            f()
    elif arg in steps:
        steps[arg]()
    else:
        print(__doc__); sys.exit(1)
