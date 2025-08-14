#!/bin/bash
# Tomato cam loop: 07:00..20:00 inclusive, every 5 minutes (test mode)

PYTHON="/home/fra/pyenv/bin/python"
CLIENT="/home/fra/rpi-cam/client.py"
FLOCK="/usr/bin/flock"
LOCK="/tmp/tomato-cam.lock"

while true; do
    HOUR=$(date +%H)
    MIN=$(date +%M)

    # Run only between 07:00 and 20:00, at :00, :05, :10, ..., :55
    if [[ $HOUR -ge 7 && $HOUR -le 20 && $((10#$MIN % 5)) -eq 0 ]]; then
        $FLOCK -n "$LOCK" "$PYTHON" "$CLIENT" photo
        sleep 60   # avoid multiple runs within the same minute
    else
        sleep 30
    fi
done
