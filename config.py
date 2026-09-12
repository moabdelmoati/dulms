import os
from dotenv import load_dotenv

load_dotenv()

STUDENT_ID = os.getenv('STUDENT_ID', '4231119')
STUDENT_PASS = os.getenv('STUDENT_PASS', '30310238801099$')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8936232926:AAFruC1HgFWHPkXTf38R_GJ4V4uPQ_83xN8')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '1234175126')

DELTA_BASE_URL = os.getenv('DELTA_BASE_URL', 'https://dulms.deltauniv.edu.eg')
DELTA_LOGIN_URL = f'{DELTA_BASE_URL}/login.aspx'

CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '30'))
