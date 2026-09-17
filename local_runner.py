# -*- coding: utf-8 -*-
import os
import time
import config
from checker import run_check

def main():
    print("🚀 Starting Delta Course Checker Continuous Loop...")
    interval = getattr(config, 'CHECK_INTERVAL_MINUTES', 2)
    print(f"Interval: every {interval} minutes.")
    
    max_hours = float(os.getenv('RUN_MAX_HOURS', '0'))
    start_time = time.time()
    iteration = 0

    while True:
        iteration += 1
        elapsed = (time.time() - start_time) / 3600
        print(f"\n--- Running Check #{iteration} (Elapsed: {elapsed:.2f}h) ---")
        try:
            run_check()
        except Exception as e:
            print(f"Error during check #{iteration}: {e}")

        # If running inside a limited workflow job, stop before hard timeout
        if max_hours > 0 and elapsed >= max_hours:
            print(f"Reached max runtime limit of {max_hours} hours. Exiting cleanly.")
            break

        sleep_seconds = interval * 60
        print(f"Waiting {interval} minutes until next check...")
        time.sleep(sleep_seconds)

if __name__ == '__main__':
    main()
