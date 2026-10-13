#!/usr/bin/env bash
# One-time Bluetooth setup on the Raspberry Pi for the gesture remote.
#
#   sudo scripts/pi/setup_bluetooth.sh          apply
#   sudo scripts/pi/setup_bluetooth.sh --undo   put everything back
#
# What it changes, and why:
#  1. bluetoothd runs without its "input" plugin. That plugin publishes a Classic
#     Bluetooth HID record, and iPhones then try to connect the old (Classic) way
#     instead of as a Bluetooth LE remote.
#  2. The controller runs Bluetooth LE only (ControllerMode = le) for the same reason.
#     The Pi doesn't need Classic Bluetooth for anything in this project.
#  3. JustWorksRepairing = always, so a phone that did "Forget This Device" can pair
#     again (new pairings are still only accepted while the remote's pairing window is
#     open; see `python -m gesturectl.hid pair`).
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "run with sudo: sudo $0 $*" >&2
    exit 1
fi

DROPIN=/etc/systemd/system/bluetooth.service.d/gesturectl.conf
CONF=/etc/bluetooth/main.conf
BACKUP=/etc/bluetooth/main.conf.gesturectl-backup
BLUETOOTHD=/usr/libexec/bluetooth/bluetoothd

restart_bluetooth() {
    systemctl daemon-reload
    systemctl restart bluetooth
    sleep 2
    echo "--- controller now:"
    btmgmt --index 0 info | sed -n '1,5p'
}

if [[ "${1:-}" == "--undo" ]]; then
    rm -f "$DROPIN"
    if [[ -f "$BACKUP" ]]; then
        cp "$BACKUP" "$CONF"
        echo "restored $CONF from $BACKUP"
    fi
    restart_bluetooth
    echo "undone: Bluetooth is back to the Raspberry Pi OS defaults"
    exit 0
fi

[[ -x "$BLUETOOTHD" ]] || { echo "bluetoothd not found at $BLUETOOTHD" >&2; exit 1; }

# 1. bluetoothd without the input plugin (systemd drop-in, survives package updates)
mkdir -p "$(dirname "$DROPIN")"
cat > "$DROPIN" <<EOF
# gesturectl: no Classic HID "input" plugin (see scripts/pi/setup_bluetooth.sh)
[Service]
ExecStart=
ExecStart=$BLUETOOTHD --noplugin=input
EOF
echo "wrote $DROPIN"

# 2 + 3. main.conf settings in [General]; keep the original once
[[ -f "$BACKUP" ]] || cp "$CONF" "$BACKUP"
set_general() {  # set_general KEY VALUE: replace an existing (possibly commented) line, else add under [General]
    local key=$1 value=$2
    if grep -qE "^[#[:space:]]*${key}[[:space:]]*=" "$CONF"; then
        sed -i -E "s|^[#[:space:]]*${key}[[:space:]]*=.*|${key} = ${value}|" "$CONF"
    else
        sed -i -E "/^\[General\]/a ${key} = ${value}" "$CONF"
    fi
    echo "set ${key} = ${value} in $CONF"
}
set_general ControllerMode le
set_general JustWorksRepairing always

restart_bluetooth
if btmgmt --index 0 info | grep -q "current settings:.*br/edr"; then
    echo "WARNING: Classic Bluetooth (br/edr) is still on" >&2
    exit 1
fi
echo "done: Bluetooth LE only, input plugin off"
