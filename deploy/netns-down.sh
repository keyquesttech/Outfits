#!/bin/bash
# Tear down the Outfits namespace. Leaves the host's networking untouched.
set -uo pipefail

CONF=${OUTFITS_CONF:-/etc/default/outfits}
[ -r "$CONF" ] && . "$CONF"

NS=${OUTFITS_NS:-outfits}
LINK=${OUTFITS_LINK:-outfits0}

# Deleting the namespace also destroys the macvlan that lives inside it.
ip netns del "$NS" 2>/dev/null || true
ip link del "$LINK" 2>/dev/null || true
echo "namespace $NS removed"
