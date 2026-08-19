#!/bin/bash
# Remove Outfits completely. Your data in data/ is left alone.
set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

for unit in outfits outfits-mdns outfits-netns; do
  systemctl disable --now "${unit}.service" 2>/dev/null
  rm -f "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload

CONF=/etc/default/outfits
[ -r "$CONF" ] && . "$CONF"
NS=${OUTFITS_NS:-outfits}
ip netns del "$NS" 2>/dev/null
rm -rf "/etc/netns/$NS"

echo "Outfits removed. data/ was left untouched."
echo "Config still at /etc/default/outfits — delete it by hand if you want it gone."
