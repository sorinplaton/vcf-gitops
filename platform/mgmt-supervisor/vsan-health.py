#!/usr/bin/env python3
"""mgmt vSAN health helper for the Supervisor rebuild (vLCM refuses to install spherelet while
the vSAN overall health is not green: check "Can vSAN cluster receive a host").

  vsan-health.py                      # non-green tests, silenced tests, on-disk format upgrade preflight (read-only)
  vsan-health.py silence <id> [<id>]  # silence tests, e.g. diskspace limit1hf upgradelowerhosts
  vsan-health.py unsilence <id> ...   # remove them again
  vsan-health.py upgrade-format       # perform the on-disk format upgrade (preflight first; no reduced redundancy)

Needs the vSAN SDK copy in ~/storage-latency/pylib (pyVmomi 9.1.1 + vsanmgmtObjects) and the
vc-mgmt-a administrator entry of ~/passwords-holodeck.json.
"""
import os, ssl, sys
sys.path.insert(0, os.path.expanduser("~/storage-latency/pylib")); sys.path.insert(0, os.path.expanduser("~/fanctl"))
import labtime
from pyVim.connect import SmartConnect
import vsanmgmtObjects, vsanapiutils  # noqa: F401

ctx = ssl._create_unverified_context()
u, pw = labtime.creds("vc-mgmt-a", "administrator@vsphere.local")
si = SmartConnect(host="vc-mgmt-a.site-a.vcf.lab", user=u, pwd=pw, sslContext=ctx)
cl = si.content.searchIndex.FindByInventoryPath("dc-mgmt-a/host/cluster-mgmt-01a")
mos = vsanapiutils.GetVsanVcMos(si._stub, context=ctx, version="vsan.version.version23")
hs, ups = mos["vsan-cluster-health-system"], mos["vsan-upgrade-systemex"]


def summary(label):
    r = hs.VsanQueryVcClusterHealthSummary(cluster=cl, perspective="defaultView", fetchFromCache=False, includeObjUuids=False)
    print(f"[{label}] overall {r.overallHealth} | {r.overallHealthDescription}")
    for g in r.groups or []:
        for t in g.groupTests or []:
            if t.testHealth != "green":
                print(f"   {g.groupName} / {t.testName} ({t.testId}): {t.testHealth}")


def formats():
    for h in cl.host:
        for dm in h.configManager.vsanSystem.config.storageInfo.diskMapping or []:
            print(f"  {h.name}: cache v{dm.ssd.vsanDiskInfo.formatVersion}, capacity", [d.vsanDiskInfo.formatVersion for d in dm.nonSsd])


def preflight():
    pf = ups.PerformVsanUpgradePreflightCheckEx(cluster=cl, downgradeFormat=False)
    print("preflight issues:", [getattr(i, "msg", str(i))[:200] for i in (pf.issues or [])] or "none")
    return pf


cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
if cmd == "status":
    summary("now"); print("silenced:", hs.VsanHealthGetVsanClusterSilentChecks(cluster=cl)); formats(); preflight()
elif cmd == "silence":
    print("set:", hs.VsanHealthSetVsanClusterSilentChecks(cluster=cl, addSilentChecks=sys.argv[2:]))
    print("silenced:", hs.VsanHealthGetVsanClusterSilentChecks(cluster=cl)); summary("after")
elif cmd == "unsilence":
    print("set:", hs.VsanHealthSetVsanClusterSilentChecks(cluster=cl, removeSilentChecks=sys.argv[2:]))
    print("silenced:", hs.VsanHealthGetVsanClusterSilentChecks(cluster=cl)); summary("after")
elif cmd == "upgrade-format":
    pf = preflight()
    if pf.issues:
        sys.exit("preflight has issues, not upgrading")
    task = ups.PerformVsanUpgradeEx(cluster=cl, performObjectUpgrade=True, downgradeFormat=False, allowReducedRedundancy=False)
    print("upgrade task started:", task)
else:
    print(__doc__); sys.exit(1)
