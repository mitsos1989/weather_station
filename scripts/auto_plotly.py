#!/usr/bin/env python3
import subprocess
import time
import sys

# Path to your main script
SCRIPT = "timeseries_plotly_optimised.py"
# Delay before restarting (seconds)
RESTART_DELAY = 2

def run_forever():
    while True:
        print(f"[Launcher] Starting {SCRIPT} ...")
        proc = subprocess.Popen([sys.executable, SCRIPT])
        proc.wait()
        exit_code = proc.returncode
        print(f"[Launcher] {SCRIPT} exited with code {exit_code}. Restarting in {RESTART_DELAY}s...")
        time.sleep(RESTART_DELAY)

if __name__ == "__main__":
    try:
        run_forever()
    except KeyboardInterrupt:
        print("\n[Launcher] Received Ctrl+C; exiting.")
        sys.exit(0)
