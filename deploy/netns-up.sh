#!/bin/bash
# Create the Outfits network namespace and its macvlan interface.
# Idempotent: safe to run when some or all of it already exists.
set -euo pipefail

CONF=${OUTFITS_CONF:-/etc/default/outfits}
[ -r "$CONF" ] && . "$CONF"

NS=${OUTFITS_NS:-outfits}
LINK=${OUTFITS_LINK:-outfits0}
PARENT=${OUTFITS_PARENT:-eth0}
IP_ADDR=${OUTFITS_IP:?OUTFITS_IP is not set}
CIDR=${OUTFITS_CIDR:-24}
GW=${OUTFITS_GW:?OUTFITS_GW is not set}
DNS=${OUTFITS_DNS:-1.1.1.1}

if ! ip link show "$PARENT" >/dev/null 2>&1; then
  echo "Parent interface $PARENT does not exist" >&2
  exit 1
fi

# Namespace
ip netns list | grep -qw "$NS" || ip netns add "$NS"

# Namespace-private resolver. This never touches the host's /etc/resolv.conf.
mkdir -p "/etc/netns/$NS"
: > "/etc/netns/$NS/resolv.conf"
for server in $DNS; do
  echo "nameserver $server" >> "/etc/netns/$NS/resolv.conf"
done

# macvlan, created on the host then moved inside.
if ! ip netns exec "$NS" ip link show "$LINK" >/dev/null 2>&1; then
  ip link del "$LINK" 2>/dev/null || true
  ip link add "$LINK" link "$PARENT" type macvlan mode bridge
  ip link set "$LINK" netns "$NS"
fi

ip netns exec "$NS" ip link set lo up
ip netns exec "$NS" ip link set "$LINK" up

ip netns exec "$NS" ip addr show dev "$LINK" | grep -qw "$IP_ADDR/$CIDR" ||
  ip netns exec "$NS" ip addr add "$IP_ADDR/$CIDR" dev "$LINK"

ip netns exec "$NS" ip route show | grep -q '^default' ||
  ip netns exec "$NS" ip route add default via "$GW" dev "$LINK"

echo "namespace $NS ready: $IP_ADDR/$CIDR on $LINK (via $PARENT), gateway $GW"
