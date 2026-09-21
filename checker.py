# -*- coding: utf-8 -*-
import os
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import config
from delta_client import DeltaClient
from notifier import send_telegram_message, send_consecutive_alerts

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.bot_state.json')

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Checker] Notice: Failed to read state file: {e}")
    return {}

def save_state(state: dict):
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Checker] Notice: Failed to write state file: {e}")

def get_interval_text(minutes: int) -> str:
    if minutes == 1:
        return "دقيقة واحدة"
    elif minutes == 2:
        return "دقيقتين"
    elif 3 <= minutes <= 10:
        return f"{minutes} دقائق"
    elif minutes == 30:
        return "نصف ساعة"
    else:
        return f"{minutes} دقيقة"

def run_check(force_report: bool = False):
    if not getattr(config, 'BOT_ENABLED', False):
        print('[Checker] Bot is completely disabled (BOT_ENABLED=False). Aborting check.')
        return

    # Egypt / Cairo Timezone
    cairo_tz = ZoneInfo("Africa/Cairo")
    now_cairo = datetime.now(cairo_tz)
    now_ts = time.time()
    
    check_interval_mins = getattr(config, 'CHECK_INTERVAL_MINUTES', 2)
    report_interval_mins = getattr(config, 'REPORT_INTERVAL_MINUTES', 30)

    check_interval_text = get_interval_text(check_interval_mins)
    report_interval_text = get_interval_text(report_interval_mins)

    next_check = now_cairo + timedelta(minutes=check_interval_mins)
    now_str = now_cairo.strftime('%I:%M %p - %d/%m/%Y')
    next_check_str = next_check.strftime('%I:%M %p')

    state = load_state()
    last_report_ts = state.get('last_report_time', 0)
    last_open_courses = set(state.get('last_open_courses', []))
    last_login_failed = state.get('last_login_failed', False)

    elapsed_since_report = now_ts - last_report_ts
    is_periodic_report_due = (elapsed_since_report >= report_interval_mins * 60)
    is_initial_run = (last_report_ts == 0)

    print(f'=== Starting Delta LMS Check at {now_str} (Check every {check_interval_mins}m | Report every {report_interval_mins}m) ===')
    client = DeltaClient()

    if not client.login():
        state['last_login_failed'] = True
        save_state(state)
        if force_report or is_initial_run or is_periodic_report_due or not last_login_failed:
            err_msg = (
                '❌ <b>تنبيه من بوت تسجيل المواد:</b>\n'
                'فشل تسجيل الدخول إلى بوابة جامعة الدلتا.\n'
                f'<b>السبب:</b> {client.last_error}\n\n'
                f'⏱️ <b>المحاولة القادمة:</b> في تمام <b>{next_check_str}</b> (بعد {check_interval_text})\n'
                f'📢 <i>الفحص مستمر كل {check_interval_text} تلقائياً.</i>'
            )
            send_telegram_message(err_msg)
            state['last_report_time'] = now_ts
            save_state(state)
        else:
            remaining_mins = max(0, (report_interval_mins * 60 - elapsed_since_report) / 60)
            print(f'[Checker] Login failed. Next check in {check_interval_mins}m. Next Telegram report in {remaining_mins:.1f}m. (Silent)')
        return

    state['last_login_failed'] = False

    reg_info = client.get_registration_info()
    allowed_hours = reg_info.get('AcademicAllowedHours', 0)
    paid_hours = reg_info.get('PaidHours', 0)
    registered_hours = reg_info.get('RegisteredHours', 0)
    remaining_days = reg_info.get('RegRemainingDays', 0)

    courses = client.get_available_courses()

    if not courses:
        if force_report or is_initial_run or is_periodic_report_due:
            msg = (
                '📊 <b>تقرير فحص مواد جامعة الدلتا</b>\n'
                f'🕒 {now_str}\n\n'
                f'👤 الساعات المسموحة: <b>{allowed_hours}</b> | المدفوعة: <b>{paid_hours}</b> | المسجلة: <b>{registered_hours}</b>\n'
                f'⏳ الأيام المتبقية للتسجيل: <b>{remaining_days} يوم</b>\n\n'
                'ℹ️ <i>لا توجد أي مواد متاحة للتسجيل حالياً في صفحتك.</i>\n\n'
                f'⏱️ <b>الفحص القادم:</b> في تمام <b>{next_check_str}</b> (فحص مستمر كل {check_interval_text})\n'
                f'📢 <b>التقرير القادم:</b> بعد {report_interval_text} تقريباً'
            )
            send_telegram_message(msg)
            state['last_report_time'] = now_ts
            state['last_open_courses'] = []
            save_state(state)
        else:
            remaining_mins = max(0, (report_interval_mins * 60 - elapsed_since_report) / 60)
            print(f'[Checker] No available courses found. Next check in {check_interval_mins}m. Next report in {remaining_mins:.1f}m. (Silent)')
        return

    has_urgent_open_seat = False
    courses_blocks = []
    urgent_courses = []
    current_open_courses = []

    for c in courses:
        c_id = c.get('CourseId')
        c_code = c.get('Code', '').strip()
        c_name = c.get('Name', '').strip()
        c_hours = c.get('CreditHours', 0)
        c_code_norm = config.normalize_code(c_code)

        # 1. Skip excluded courses (e.g. SEC411, SEC412, GEN403)
        if c_code_norm in config.EXCLUDED_COURSES:
            print(f'[Checker] Skipping excluded course: [{c_code}] {c_name}')
            continue

        schedules = client.get_course_schedule(c_id)

        # 2. Filter by target groups if specified for this course (e.g. AI414 -> B4_Cyber)
        if c_code_norm in config.TARGET_GROUPS:
            target_list = [g.strip().lower() for g in config.TARGET_GROUPS[c_code_norm]]
            schedules = [s for s in schedules if s.get('group_name', '').strip().lower() in target_list]

        # Check if course is general requirements (GEN)
        is_gen = c_code.upper().startswith('GEN')
        open_groups = [s for s in schedules if s.get('is_open')]

        if is_gen:
            # General courses (GEN): Simplified display without numbers, no urgent alert
            block = f'📚 <b>[{c_code}] {c_name}</b> ({c_hours} ساعات)\n'
            if open_groups:
                open_grp_names = ", ".join([f"Group {s['group_name']}" for s in open_groups])
                block += f'  🟢 <b>مفتوحة للتسجيل</b> ({open_grp_names})\n'
                for s in open_groups:
                    current_open_courses.append(f"{c_code_norm}:{s['group_name']}")
            else:
                block += '  🔴 مغلقة حالياً\n'
        else:
            # Major / Specialty courses: Detailed groups, seats count, and triggers urgent alert
            block = f'📚 <b>[{c_code}] {c_name}</b> ({c_hours} ساعات)\n'
            if not schedules:
                if c_code_norm in config.TARGET_GROUPS:
                    block += '  ⚠️ المجموعات المحددة غير معلنة أو غير متاحة حالياً.\n'
                else:
                    block += '  ⚠️ لا توجد مواعيد أو مجموعات معلنة بعد.\n'
            else:
                for s in schedules:
                    grp = s['group_name']
                    cap = s['capacity']
                    reg = s['registered']
                    avail = s['available_seats']
                    blocked = s['is_blocked']
                    is_open = s['is_open']

                    raw_type = s.get('raw_type', '')
                    type_en = (s.get('type') or '').lower()
                    if type_en == 'lecture' or raw_type == 'Group':
                        type_label = 'محاضرة'
                    elif type_en == 'practical' or raw_type == 'SubGroup':
                        type_label = 'سكشن'
                    else:
                        type_label = ''
                    type_suffix = f" ({type_label})" if type_label else ""

                    if is_open:
                        has_urgent_open_seat = True
                        current_open_courses.append(f"{c_code_norm}:{grp}")
                        icon = '🟢'
                        status = f'<b>مفتوح للتسجيل! (متبقي {avail} مقعد)</b>'
                        urgent_courses.append({
                            'code': c_code,
                            'name': c_name,
                            'group': f"{grp}{type_suffix}",
                            'avail': avail,
                            'time': f"{s.get('day', '')} {s.get('time', '')} ({s.get('room', '')})".strip()
                        })
                    elif blocked:
                        icon = '🔴'
                        status = f'مغلق / Blocked ({reg}/{cap})'
                    elif avail == 0:
                        icon = '🔴'
                        status = f'مكتمل ({reg}/{cap})'
                    else:
                        icon = '🟡'
                        status = f'متبقي {avail} مقعد'

                    block += f'  {icon} Group <b>{grp}</b>{type_suffix}: {status}\n'
                    if s.get('day') and s.get('time'):
                        block += f"     ⏰ {s['day']} {s['time']}\n"

        courses_blocks.append(block)

    current_open_set = set(current_open_courses)
    new_open_seats = current_open_set - last_open_courses
    found_something_new = len(new_open_seats) > 0

    should_send = force_report or is_initial_run or is_periodic_report_due or found_something_new

    if not should_send:
        # Silent check
        state['last_open_courses'] = list(current_open_set)
        save_state(state)
        remaining_mins = max(0, (report_interval_mins * 60 - elapsed_since_report) / 60)
        print(f'[Checker] Monitored courses checked. No new open seats. Next check in {check_interval_mins}m. Next periodic report in {remaining_mins:.1f}m. (Silent)')
        return

    # Header only becomes URGENT if a major/specialty course (non-GEN) has open seats
    if has_urgent_open_seat:
        header = '🚨 <b>تنبيه عاجل: توجد مقاعد شاغرة للتسجيل الآن!</b>\n'
    elif found_something_new:
        header = '🟢 <b>تنبيه: تم فتح مقاعد شاغرة للتسجيل!</b>\n'
    else:
        header = f'📊 <b>تقرير فحص مواد جامعة الدلتا (كل {report_interval_text})</b>\n'

    header += f'🕒 {now_str}\n\n'
    header += f'👤 الساعات المسموحة: <b>{allowed_hours}</b> | المدفوعة: <b>{paid_hours}</b> | المسجلة: <b>{registered_hours}</b>\n'
    header += f'⏳ الأيام المتبقية للتسجيل: <b>{remaining_days} يوم</b>\n\n'

    footer = (
        f'\n⏱️ <b>الفحص القادم:</b> في تمام الساعة <b>{next_check_str}</b> (فحص مستمر كل {check_interval_text})\n'
        f'📢 <b>التقرير القادم:</b> بعد {report_interval_text} تقريباً (أو فور توفر مقاعد شاغرة)'
    )

    full_message = header + '\n'.join(courses_blocks) + footer
    print('[Checker] Sending report to Telegram...')
    send_telegram_message(full_message)

    state['last_report_time'] = now_ts
    state['last_open_courses'] = list(current_open_set)
    save_state(state)

    # If any non-GEN courses have open seats, send consecutive alarm barrage with stop button
    if urgent_courses and found_something_new:
        print(f'[Checker] Triggering consecutive alerts for {len(urgent_courses)} newly opened group(s)...')
        send_consecutive_alerts(urgent_courses)

if __name__ == '__main__':
    run_check(force_report=True)

