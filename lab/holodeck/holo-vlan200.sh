# Transcribed from the blog; replace with the copy from the router.
# Holorouter (10.0.6.33): VLAN 200 gateway for the holo-east external block 10.200.200.0/24.
# Installed as /usr/local/bin/holo-vlan200.sh and run at boot by holo-vlan200.service.
ip link add link eth1 name eth1.200 type vlan id 200
ip link set eth1.200 mtu 8000 up
ip addr add 10.200.200.1/24 dev eth1.200
arping -U -c 3 -I eth1.200 10.200.200.1    # tell the VNA the gateway MAC changed
# The DNAT line below is not from the blog text: it comes from the Claude Code session of
# 2026-10-01, where VKS nodes got no UDP answer from 10.1.1.1 (see dns-dnat.txt).
iptables -t nat -I PREROUTING -i eth1.200 -d 10.1.1.1/32 -p udp --dport 53 \
  -j DNAT --to-destination 10.200.200.1:53   # DNS redirect for VKS nodes
