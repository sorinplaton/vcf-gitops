#!/bin/sh
# Holorouter /usr/local/bin/holo-vlan204.sh — Day-1 network for the platform-ops org (region mgmt-a).
# VLAN 204 gateway 10.204.204.1/24, same pattern as holo-vlan200.sh (holo-east) and holo-vlan203.sh (tepless).
# VCF Automation cannot reuse the Day-0 block (10.1.7.128/25, VLAN 22), so each org gets its own VLAN here;
# the matching objects in nsx-mgmt-a (distributed VLAN connection + external IP block) are created from the
# VCF Automation provider UI. The DNAT line makes UDP DNS to 10.1.1.1 answer from this VLAN's gateway
# (the Technitium DNS replies from the outgoing interface, which the VPC SNAT would otherwise drop).
ip link show eth1.204 >/dev/null 2>&1 || ip link add link eth1 name eth1.204 type vlan id 204
ip link set eth1.204 mtu 8000 up
ip addr show dev eth1.204 | grep -q "10.204.204.1/24" || ip addr add 10.204.204.1/24 dev eth1.204
iptables -t nat -C PREROUTING -i eth1.204 -d 10.1.1.1/32 -p udp --dport 53 -j DNAT --to-destination 10.204.204.1:53 2>/dev/null || \
  iptables -t nat -I PREROUTING -i eth1.204 -d 10.1.1.1/32 -p udp --dport 53 -j DNAT --to-destination 10.204.204.1:53
