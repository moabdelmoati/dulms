import os
from dotenv import load_dotenv

load_dotenv()

STUDENT_ID = os.getenv('STUDENT_ID')
STUDENT_PASS = os.getenv('STUDENT_PASS')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

DELTA_BASE_URL = os.getenv('DELTA_BASE_URL', 'https://dulms.deltauniv.edu.eg')
DELTA_LOGIN_URL = f'{DELTA_BASE_URL}/login.aspx'

CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '30'))
