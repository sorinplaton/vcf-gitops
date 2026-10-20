#!/bin/sh
# Copied from the holorouter (/usr/local/bin/holo-vlan203.sh) on 2026-10-20. Day-1 network for the TEP-less region.
# VLAN 203 gateway 10.203.203.1/24
ip link show eth1.203 >/dev/null 2>&1 || ip link add link eth1 name eth1.203 type vlan id 203
ip link set eth1.203 mtu 8000 up
ip addr show dev eth1.203 | grep -q "10.203.203.1/24" || ip addr add 10.203.203.1/24 dev eth1.203
iptables -t nat -C PREROUTING -i eth1.203 -d 10.1.1.1/32 -p udp --dport 53 -j DNAT --to-destination 10.203.203.1:53 2>/dev/null || \
  iptables -t nat -I PREROUTING -i eth1.203 -d 10.1.1.1/32 -p udp --dport 53 -j DNAT --to-destination 10.203.203.1:53
