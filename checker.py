# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import config
from delta_client import DeltaClient
from notifier import send_telegram_message, send_consecutive_alerts

def get_interval_text(minutes: int) -> str:
    if minutes == 1:
        return "دقيقة واحدة"
    elif minutes == 2:
        return "دقيقتين"
    elif 3 <= minutes <= 10:
        return f"{minutes} دقائق"
    else:
        return f"{minutes} دقيقة"

def run_check():
    # Egypt / Cairo Timezone
    cairo_tz = ZoneInfo("Africa/Cairo")
    now_cairo = datetime.now(cairo_tz)
    
    interval_mins = getattr(config, 'CHECK_INTERVAL_MINUTES', 2)
    interval_text = get_interval_text(interval_mins)
    next_check = now_cairo + timedelta(minutes=interval_mins)
    
    now_str = now_cairo.strftime('%I:%M %p - %d/%m/%Y')
    next_str = next_check.strftime('%I:%M %p')

    print(f'=== Starting Delta LMS Check at {now_str} ===')
    client = DeltaClient()

    if not client.login():
        err_msg = (
            '❌ <b>تنبيه من بوت تسجيل المواد:</b>\n'
            'فشل تسجيل الدخول إلى بوابة جامعة الدلتا.\n'
            f'<b>السبب:</b> {client.last_error}\n\n'
            f'⏱️ <b>المحاولة القادمة:</b> في تمام <b>{next_str}</b> (بعد {interval_text})'
        )
        send_telegram_message(err_msg)
        return

    reg_info = client.get_registration_info()
    allowed_hours = reg_info.get('AcademicAllowedHours', 0)
    paid_hours = reg_info.get('PaidHours', 0)
    registered_hours = reg_info.get('RegisteredHours', 0)
    remaining_days = reg_info.get('RegRemainingDays', 0)

    courses = client.get_available_courses()

    if not courses:
        msg = (
            '📊 <b>تقرير فحص مواد جامعة الدلتا</b>\n'
            f'🕒 {now_str}\n\n'
            f'👤 الساعات المسموحة: <b>{allowed_hours}</b> | المدفوعة: <b>{paid_hours}</b> | المسجلة: <b>{registered_hours}</b>\n'
            f'⏳ الأيام المتبقية للتسجيل: <b>{remaining_days} يوم</b>\n\n'
            'ℹ️ <i>لا توجد أي مواد متاحة للتسجيل حالياً في صفحتك.</i>\n\n'
            f'⏱️ <b>الفحص القادم:</b> في تمام <b>{next_str}</b> (بعد {interval_text} تقريباً)'
        )
        send_telegram_message(msg)
        return

    has_urgent_open_seat = False
    courses_blocks = []
    urgent_courses = []

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

        # 2. Filter by target groups if specified for this course (e.g. AI414 -> B_Cyber, B4_Cyber)
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

    # Header only becomes URGENT if a major/specialty course (non-GEN) has open seats
    if has_urgent_open_seat:
        header = '🚨 <b>تنبيه عاجل: توجد مقاعد شاغرة للتسجيل الآن!</b>\n'
    else:
        header = f'📊 <b>تقرير فحص مواد جامعة الدلتا (كل {interval_text})</b>\n'

    header += f'🕒 {now_str}\n\n'
    header += f'👤 الساعات المسموحة: <b>{allowed_hours}</b> | المدفوعة: <b>{paid_hours}</b> | المسجلة: <b>{registered_hours}</b>\n'
    header += f'⏳ الأيام المتبقية للتسجيل: <b>{remaining_days} يوم</b>\n\n'

    footer = f'\n⏱️ <b>الفحص القادم:</b> في تمام الساعة <b>{next_str}</b> (بعد {interval_text} تقريباً)'
    full_message = header + '\n'.join(courses_blocks) + footer
    print('[Checker] Sending report to Telegram...')
    send_telegram_message(full_message)

    # If any non-GEN courses have open seats, send consecutive alarm barrage with stop button
    if urgent_courses:
        print(f'[Checker] Triggering consecutive alerts for {len(urgent_courses)} open group(s)...')
        send_consecutive_alerts(urgent_courses)


if __name__ == '__main__':
    run_check()

