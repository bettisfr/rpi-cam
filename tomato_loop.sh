#!/bin/bash
# Tomato cam loop: 07:00..20:00 inclusive, configurable interval

PYTHON="/home/fra/pyenv/bin/python"
CLIENT="/home/fra/rpi-cam/client.py"
FLOCK="/usr/bin/flock"
LOCK="/tmp/tomato-cam.lock"

FREQ=2   # interval in minutes (e.g., 2, 5, 10)

while true; do
    HOUR=$(date +%H)
    MIN=$(date +%M)

    # Run only between 07:00 and 20:00 at multiples of $FREQ minutes
    if [[ $HOUR -ge 7 && $HOUR -le 20 && $((10#$MIN % FREQ)) -eq 0 ]]; then
        $FLOCK -n "$LOCK" "$PYTHON" "$CLIENT" photo
        sleep 60   # avoid multiple runs within the same minute
    else
        sleep 20
    fi
done
