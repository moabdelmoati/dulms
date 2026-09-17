import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

def normalize_code(code: str) -> str:
    """Normalizes course code by stripping non-alphanumeric chars and converting to uppercase."""
    if not code:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', str(code)).upper()

STUDENT_ID = os.getenv('STUDENT_ID')
STUDENT_PASS = os.getenv('STUDENT_PASS')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

DELTA_BASE_URL = os.getenv('DELTA_BASE_URL', 'https://dulms.deltauniv.edu.eg')
DELTA_LOGIN_URL = f'{DELTA_BASE_URL}/login.aspx'

CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '2'))
ALERT_REPEAT_COUNT = int(os.getenv('ALERT_REPEAT_COUNT', '20'))
ALERT_INTERVAL_SECONDS = int(os.getenv('ALERT_INTERVAL_SECONDS', '3'))

# Courses to completely exclude from checking and alerting
raw_excluded = os.getenv('EXCLUDED_COURSES', 'SEC411,SEC412,GEN403')
EXCLUDED_COURSES = [normalize_code(c) for c in raw_excluded.split(',') if c.strip()]

# Specific target groups to monitor per course (normalized code -> list of group names)
# If a course is in TARGET_GROUPS, ONLY these groups are monitored/alerted.
# Other non-excluded courses will monitor all groups as usual.
DEFAULT_TARGET_GROUPS = {
    'AI414': ['B4_Cyber'],
    'SEC413': ['A', 'B4'],
    'SECE43': ['B', 'B3'],
    'SEC415': ['B1'],
}

raw_targets = os.getenv('TARGET_GROUPS')
if raw_targets:
    try:
        parsed_targets = json.loads(raw_targets)
        TARGET_GROUPS = {normalize_code(k): [str(g).strip() for g in v] for k, v in parsed_targets.items()}
    except Exception as e:
        print(f"[Config] Error parsing TARGET_GROUPS env: {e}. Using defaults.")
        TARGET_GROUPS = DEFAULT_TARGET_GROUPS
else:
    TARGET_GROUPS = DEFAULT_TARGET_GROUPS

