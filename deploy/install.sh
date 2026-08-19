#!/bin/bash
# Install Outfits as three systemd units.
#
# Explicitly does NOT touch: FlatBrain's code, port, service file, or avahi
# record; the host's /etc/resolv.conf; avahi-daemon.conf; any existing listener
# on port 80. Everything added here is additive and removable with uninstall.sh.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

echo "==> Checking prerequisites"
command -v avahi-publish >/dev/null || { echo "avahi-utils is not installed" >&2; exit 1; }
[ -x "$ROOT/.venv/bin/uvicorn" ] || { echo "Python venv missing. Run setup.sh first." >&2; exit 1; }
[ -f "$ROOT/frontend/dist/index.html" ] || echo "  ! frontend/dist is missing; the API will run but the UI will not."

echo "==> Installing config to /etc/default/outfits"
if [ -f /etc/default/outfits ]; then
  echo "  keeping existing /etc/default/outfits (edit it by hand to change the IP)"
else
  install -m 0644 deploy/outfits.conf /etc/default/outfits
fi
. /etc/default/outfits

echo "==> Verifying ${OUTFITS_IP} is free"
if ping -c1 -W1 "$OUTFITS_IP" >/dev/null 2>&1; then
  echo "  ! ${OUTFITS_IP} answers to ping — something already uses it." >&2
  echo "  ! Edit OUTFITS_IP in /etc/default/outfits and run this again." >&2
  exit 1
fi

echo "==> Recording what is on port 80 before we start"
BEFORE=$(ss -tlnp 2>/dev/null | grep -c ':80 ' || true)

chmod +x deploy/netns-up.sh deploy/netns-down.sh deploy/backup.sh 2>/dev/null || true

echo "==> Installing systemd units"
for unit in outfits-netns outfits-mdns outfits; do
  install -m 0644 "deploy/${unit}.service" "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload

echo "==> Starting"
systemctl enable --now outfits-netns.service
systemctl enable --now outfits-mdns.service
systemctl enable --now outfits.service

sleep 4

echo
echo "==> Verifying"
ok=0
check() {
  if eval "$2" >/dev/null 2>&1; then echo "  PASS  $1"; else echo "  FAIL  $1"; ok=1; fi
}
check "outfits.service is running"      "systemctl is-active --quiet outfits"
check "namespace has the address"       "ip netns exec ${OUTFITS_NS} ip addr show | grep -qw ${OUTFITS_IP}"
# Tested from inside the namespace: macvlan deliberately isolates a child from
# its parent, so the Pi itself cannot reach ${OUTFITS_IP}. Other devices can.
check "Outfits answers on ${OUTFITS_IP}" \
  "ip netns exec ${OUTFITS_NS} curl -fsS -m 8 -o /dev/null http://${OUTFITS_IP}/api/health"
check "namespace reaches the internet"  \
  "ip netns exec ${OUTFITS_NS} curl -fsS -m 12 -o /dev/null https://api.open-meteo.com/v1/forecast?latitude=51.5\&longitude=-0.12\&current=temperature_2m"
check "${OUTFITS_HOSTNAME} resolves"    "getent hosts ${OUTFITS_HOSTNAME}"
check "host port 80 untouched"          "[ \"\$(ss -tlnp 2>/dev/null | grep -c ':80 ')\" = \"${BEFORE}\" ]"
if command -v getent >/dev/null && getent hosts flatbrain.local >/dev/null 2>&1; then
  check "flatbrain.local still serves"  "curl -fsS -m 8 -o /dev/null http://flatbrain.local/"
fi

echo
if [ "$ok" = 0 ]; then
  echo "Outfits is live at  http://${OUTFITS_HOSTNAME}/   (or http://${OUTFITS_IP}/)"
  echo
  echo "Open it from your phone or laptop. The Pi itself cannot reach that address"
  echo "— macvlan isolates a child interface from its parent — so from here use:"
  echo "  sudo ip netns exec ${OUTFITS_NS} curl http://localhost/api/health"
else
  echo "Some checks failed. Logs:  journalctl -u outfits -n 50 --no-pager"
  exit 1
fi
