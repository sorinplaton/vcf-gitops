#!/usr/bin/env python3
# Holorouter echo observer for netprobe: answers {"ip": "<source address of the caller>"} on the
# VLAN 200 and VLAN 203 gateways (port 18080), so a pod can learn which address it leaves with.
# Installed as /usr/local/bin/holo-echo.py, run by holo-echo.service. Standard library only.
import json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b = json.dumps({"ip": self.client_address[0]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a):
        pass

servers = [ThreadingHTTPServer((ip, 18080), H) for ip in ("10.200.200.1", "10.203.203.1")]
for s in servers[1:]:
    threading.Thread(target=s.serve_forever, daemon=True).start()
servers[0].serve_forever()
