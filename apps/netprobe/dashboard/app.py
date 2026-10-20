"""netprobe dashboard agent: one page that compares how two networks treat the same traffic.

GET /           dashboard page (index.html)
GET /api/info   who answered (pod, node, IPs), the client address this pod sees, and the
                egress address an outside observer sees when this pod calls out
GET /config     peer list for the page (config.json)
Standard library only; runs in the stock python:3.12-alpine image.
"""
import json, os, socket, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
ENV = {k: os.environ.get(k, "") for k in ("POD_NAME", "POD_IP", "NODE_NAME", "HOST_IP")}


def cluster_of(node):
    """Node names look like <cluster>-<hash>-... or <cluster>-np-1-...; match the configured clusters."""
    for c in CFG["clusters"]:
        if node.startswith(c["id"] + "-"):
            return c
    return {"id": node, "label": "unknown cluster"}


def egress():
    """Ask the echo observers which source address they see for this pod (first one that answers)."""
    for url in CFG.get("echo", []):
        try:
            t0 = time.time()
            with urllib.request.urlopen(url, timeout=2) as r:
                ip = json.loads(r.read()).get("ip")
            return {"observer": url, "ip": ip, "ms": round((time.time() - t0) * 1000, 1)}
        except Exception as e:  # unreachable observer: try the next one
            last = str(e)[:80]
    return {"observer": None, "ip": None, "error": last if CFG.get("echo") else "no observer configured"}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")      # the page calls both clusters
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._send(200, open(os.path.join(HERE, "index.html"), "rb").read(), "text/html; charset=utf-8")
        if p == "/config":
            return self._send(200, json.dumps(CFG), "application/json")
        if p == "/api/info":
            c = cluster_of(ENV["NODE_NAME"])
            return self._send(200, json.dumps({
                "cluster": c["id"], "network": c.get("label"),
                "pod": ENV["POD_NAME"], "podIP": ENV["POD_IP"],
                "node": ENV["NODE_NAME"], "nodeIP": ENV["HOST_IP"],
                "client": self.client_address[0],
                "forwardedFor": self.headers.get("X-Forwarded-For"),
                "egress": egress(), "time": time.time(),
            }), "application/json")
        if p == "/healthz":
            return self._send(200, "ok", "text/plain")
        self._send(404, "not found", "text/plain")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
