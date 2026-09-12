import requests
import config

def send_telegram_message(text: str, parse_mode: str = 'HTML') -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print('[Notifier] Error: Bot token or chat ID is missing.')
        return False

    url = f'https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': config.TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        res_json = response.json()
        if res_json.get('ok'):
            print('[Notifier] Message sent successfully to Telegram.')
            return True
        else:
            desc = res_json.get('description', '')
            print(f'[Notifier] Telegram error: {desc}')
            if res_json.get('error_code') == 400 and 'chat not found' in desc:
                print('[Notifier] HINT: Please open your bot in Telegram and click /start first!')
            return False
    except Exception as e:
        print(f'[Notifier] Failed to send message: {e}')
        return False
