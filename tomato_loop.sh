#!/bin/bash
PYTHON=/home/fra/pyenv/bin/python
CLIENT=/home/fra/rpi-cam/client.py

while true; do
    HOUR=$(date +%H)
    MIN=$(date +%M)

    # Run only between 07:00 and 20:00, every 10 minutes
    if [[ $HOUR -ge 7 && $HOUR -le 20 && $((10#$MIN % 10)) -eq 0 ]]; then
        /usr/bin/flock -n /tmp/cam.lock $PYTHON $CLIENT photo
        sleep 60   # avoid multiple triggers in the same minute
    else
        sleep 30
    fi
done
