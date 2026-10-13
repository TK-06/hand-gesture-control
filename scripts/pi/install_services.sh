#!/usr/bin/env bash
# Start the gesture remote automatically at boot (Raspberry Pi).
#
#   sudo scripts/pi/install_services.sh              install + start both services
#   sudo scripts/pi/install_services.sh --uninstall  stop + remove them
#
# Installs two systemd services that restart by themselves if they ever stop:
#   gesturectl-hid  the Bluetooth remote (keeps the phone connected)
#   gesturectl      the camera + gesture recognition, sends actions to gesturectl-hid
# Logs: journalctl -u gesturectl -f   and   logs/*.log in the project folder.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "run with sudo: sudo $0 $*" >&2
    exit 1
fi

DIR=$(cd "$(dirname "$0")/../.." && pwd)
RUN_AS=${SUDO_USER:-$(stat -c %U "$DIR")}
UNITS=(gesturectl-hid gesturectl)

if [[ "${1:-}" == "--uninstall" ]]; then
    systemctl disable --now "${UNITS[@]/%/.service}" 2>/dev/null || true
    for unit in "${UNITS[@]}"; do rm -f "/etc/systemd/system/$unit.service"; done
    systemctl daemon-reload
    echo "removed: the gesture remote no longer starts at boot"
    exit 0
fi

[[ -x "$DIR/.venv/bin/python" ]] || { echo "no venv at $DIR/.venv (see docs/SETUP.md)" >&2; exit 1; }
[[ -f "$DIR/models/hand_landmarker.task" ]] || { echo "model missing: run python scripts/download_model.py" >&2; exit 1; }

for unit in "${UNITS[@]}"; do
    sed -e "s|__DIR__|$DIR|g" -e "s|__USER__|$RUN_AS|g" "$DIR/scripts/pi/$unit.service" > "/etc/systemd/system/$unit.service"
    echo "installed /etc/systemd/system/$unit.service (runs as $RUN_AS from $DIR)"
done
sudo -u "$RUN_AS" mkdir -p "$DIR/logs"
systemctl daemon-reload
systemctl enable --now "${UNITS[@]/%/.service}"
sleep 3
systemctl --no-pager --lines=0 status "${UNITS[@]/%/.service}" | grep -E "●|Active:"
echo "done: both start at every boot. Live log: journalctl -u gesturectl -u gesturectl-hid -f"
