#!/usr/bin/env bash
# Stops study runners cleanly if the laptop battery gets low while discharging.
# Completed runs are kept; in-progress run directories are moved to */interrupted_lowbattery/
# so the same runner commands can resume later (completed runs are skipped).
LIMIT=${1:-25}
E=/home/stanley/Github/Unity_Ship_Formation_Study/Experiments/KalmanStudy/robust_evaluation
while true; do
    cap=$(cat /sys/class/power_supply/BAT1/capacity)
    st=$(cat /sys/class/power_supply/BAT1/status)
    echo "$(date +%H:%M:%S) battery=$cap% $st"
    if [ "$st" = "Discharging" ] && [ "$cap" -lt "$LIMIT" ]; then
        echo "LOW BATTERY: stopping runners"
        for p in $(pgrep -f '^python3 Tools/kalman_study/run_(laps|d04|candidate|parallel_batch).py'); do
            kids=$(pgrep -P "$p")
            kill -TERM "$p"
            sleep 1
            for k in $kids; do kill -TERM "$k" 2>/dev/null; done
        done
        sleep 5
        for b in "$E"/*/; do
            [ -d "$b/runs" ] || continue
            for d in "$b"/runs/*; do
                if [ ! -f "$d/bridge.complete" ] || [ ! -f "$d/unity.complete" ]; then
                    mkdir -p "$b/interrupted_lowbattery" && mv "$d" "$b/interrupted_lowbattery/" && echo "preserved partial $d"
                fi
            done
        done
        exit 0
    fi
    sleep 30
done
