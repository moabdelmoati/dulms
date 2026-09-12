# -*- coding: utf-8 -*-
import time
import config
from checker import run_check

def main():
    print("🚀 Starting Delta Course Checker Daemon...")
    print(f"Interval: every {config.CHECK_INTERVAL_MINUTES} minutes.")
    while True:
        try:
            run_check()
        except Exception as e:
            print(f"Error during check: {e}")
        
        sleep_seconds = config.CHECK_INTERVAL_MINUTES * 60
        print(f"Waiting {config.CHECK_INTERVAL_MINUTES} minutes until next check...")
        time.sleep(sleep_seconds)

if __name__ == '__main__':
    main()
