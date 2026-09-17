import time
import requests
import config

def send_telegram_message(text: str, parse_mode: str = 'HTML', reply_markup: dict = None) -> bool:
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
    if reply_markup:
        payload['reply_markup'] = reply_markup

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


def answer_callback_query(callback_query_id: str, text: str = "تم إيقاف التنبيهات ✅") -> bool:
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    url = f'https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/answerCallbackQuery'
    payload = {
        'callback_query_id': callback_query_id,
        'text': text,
        'show_alert': False
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get('ok', False)
    except Exception as e:
        print(f'[Notifier] Failed to answer callback query: {e}')
        return False


def flush_old_updates() -> int:
    """Discards any old unread updates and returns the next update_id to listen from."""
    if not config.TELEGRAM_BOT_TOKEN:
        return 0
    url = f'https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates'
    try:
        # Fetching with offset=-1 gives the very latest update
        res = requests.get(url, params={'offset': -1, 'timeout': 0}, timeout=10).json()
        if res.get('ok') and res.get('result'):
            latest_id = res['result'][-1]['update_id']
            # Confirm / advance offset past the latest update
            requests.get(url, params={'offset': latest_id + 1, 'timeout': 0}, timeout=5)
            return latest_id + 1
    except Exception as e:
        print(f'[Notifier] Notice: could not flush old updates ({e})')
    return 0


def check_stop_signal(offset: int) -> tuple:
    """
    Checks for a stop button press (callback_query with 'stop_alert') or a text stop command (/stop, stop, etc.).
    Returns (is_stopped: bool, next_offset: int).
    """
    if not config.TELEGRAM_BOT_TOKEN:
        return False, offset

    url = f'https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates'
    params = {'offset': offset, 'timeout': 0, 'allowed_updates': ['callback_query', 'message']}
    try:
        resp = requests.get(url, params=params, timeout=5)
        res_json = resp.json()
        if not res_json.get('ok'):
            return False, offset

        updates = res_json.get('result', [])
        for u in updates:
            up_id = u.get('update_id', 0)
            if up_id >= offset:
                offset = up_id + 1

            # 1. Check for Inline Keyboard Button click
            cb = u.get('callback_query')
            if cb:
                cb_data = cb.get('data', '')
                if cb_data == 'stop_alert':
                    answer_callback_query(cb.get('id'), text="تم إيقاف التنبيهات بنجاح ✅")
                    return True, offset

            # 2. Check for Text command (/stop, وقف, stop, etc.)
            msg = u.get('message', {})
            msg_text = (msg.get('text') or '').strip().lower()
            if msg_text in ['/stop', 'stop', 'وقف', 'إيقاف', 'كفاية', 'بس']:
                return True, offset

    except Exception as e:
        print(f'[Notifier] Warning while checking stop signal: {e}')

    return False, offset


def send_consecutive_alerts(urgent_courses: list) -> bool:
    """
    Sends consecutive alarm messages for urgent courses until the user clicks
    the '🛑 إيقاف التنبيهات' button or until ALERT_REPEAT_COUNT is reached.
    """
    if not urgent_courses:
        return False

    repeat_count = getattr(config, 'ALERT_REPEAT_COUNT', 20)
    interval_seconds = getattr(config, 'ALERT_INTERVAL_SECONDS', 3)

    # Format courses summary for the alarm message
    courses_lines = []
    for c in urgent_courses:
        code = c.get('code', '')
        name = c.get('name', '')
        grp = c.get('group', '')
        avail = c.get('avail', 0)
        time_info = c.get('time', '')
        line = f"• <b>[{code}] {name}</b>\n   Group <b>{grp}</b> (متبقي <b>{avail}</b> مقعد شاغر) 🟢"
        if time_info:
            line += f"\n   ⏰ {time_info}"
        courses_lines.append(line)

    courses_text = "\n".join(courses_lines)

    # Inline button markup
    stop_keyboard = {
        'inline_keyboard': [
            [
                {'text': '🛑 إيقاف التنبيهات (Stop)', 'callback_data': 'stop_alert'}
            ]
        ]
    }

    print(f"[Notifier] Starting consecutive alert barrage (up to {repeat_count} messages every {interval_seconds}s)...")
    offset = flush_old_updates()

    stopped_by_user = False

    for i in range(1, repeat_count + 1):
        # Check if user already clicked stop before sending
        stopped, offset = check_stop_signal(offset)
        if stopped:
            stopped_by_user = True
            break

        alert_msg = (
            f"🚨🚨🚨 <b>تنبيه عاجل ({i}/{repeat_count}): مقاعد شاغرة الآن!</b> 🚨🚨🚨\n\n"
            f"<b>المواد المتاحة للتسجيل:</b>\n"
            f"{courses_text}\n\n"
            f"⚡ <b>سارع بالدخول على LMS والتسجيل فوراً!</b>\n"
            f"<i>اضغط على الزر أدناه لإيقاف التنبيهات:</i>"
        )

        send_telegram_message(alert_msg, reply_markup=stop_keyboard)

        # Sleep in increments of 0.5s while actively checking for stop signal
        end_time = time.time() + interval_seconds
        while time.time() < end_time:
            time.sleep(0.5)
            stopped, offset = check_stop_signal(offset)
            if stopped:
                stopped_by_user = True
                break

        if stopped_by_user:
            break

    if stopped_by_user:
        print("[Notifier] Alerts stopped by user.")
        send_telegram_message("🛑 <b>تم إيقاف التنبيهات المتتالية بنجاح.</b>\nبالتوفيق في التسجيل! 🎯")
        return True
    else:
        print(f"[Notifier] Consecutive alerts finished ({repeat_count} messages sent).")
        send_telegram_message(f"ℹ️ <b>اكتمل إرسال التنبيهات ({repeat_count} تنبيه).</b>\nسيستمر الفحص التلقائي في الموعد القادم.")
        return False

