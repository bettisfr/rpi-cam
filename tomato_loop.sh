#!/bin/bash
# Tomato cam loop: 07:00..20:00 inclusive, every 2 minutes

PYTHON="/home/fra/pyenv/bin/python"
CLIENT="/home/fra/rpi-cam/client.py"
FLOCK="/usr/bin/flock"
LOCK="/tmp/tomato-cam.lock"

while true; do
    HOUR=$(date +%H)
    MIN=$(date +%M)

    # Run only between 07:00 and 20:00, at multiples of 2 minutes (:00, :02, :04, ...)
    if [[ $HOUR -ge 7 && $HOUR -le 20 && $((10#$MIN % 2)) -eq 0 ]]; then
        $FLOCK -n "$LOCK" "$PYTHON" "$CLIENT" photo
        sleep 60   # avoid multiple runs within the same minute
    else
        sleep 20
    fi
done
