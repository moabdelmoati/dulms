# -*- coding: utf-8 -*-
import os
import time
import config
from checker import run_check

def main():
    if not getattr(config, 'BOT_ENABLED', False):
        print("[Runner] Bot is completely disabled (BOT_ENABLED=False). Exiting.")
        return

    interval = getattr(config, 'CHECK_INTERVAL_MINUTES', 2)
    report_interval = getattr(config, 'REPORT_INTERVAL_MINUTES', 30)
    print("🚀 Starting Delta Course Checker Continuous Loop...")
    print(f"Check interval: every {interval} minutes.")
    print(f"Report interval: every {report_interval} minutes (or immediately on open seats).")
    
    max_hours = float(os.getenv('RUN_MAX_HOURS', '0'))
    start_time = time.time()
    iteration = 0

    while True:
        iteration += 1
        elapsed = (time.time() - start_time) / 3600
        print(f"\n--- Running Check #{iteration} (Elapsed: {elapsed:.2f}h) ---")
        try:
            # Force report on the first iteration so the user immediately knows the bot is active
            run_check(force_report=(iteration == 1))
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
