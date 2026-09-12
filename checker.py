# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from delta_client import DeltaClient
from notifier import send_telegram_message

def run_check():
    # Egypt / Cairo Timezone
    cairo_tz = ZoneInfo("Africa/Cairo")
    now_cairo = datetime.now(cairo_tz)
    next_check = now_cairo + timedelta(minutes=15)
    
    now_str = now_cairo.strftime('%I:%M %p - %d/%m/%Y')
    next_str = next_check.strftime('%I:%M %p')

    print(f'=== Starting Delta LMS Check at {now_str} ===')
    client = DeltaClient()

    if not client.login():
        err_msg = (
            '❌ <b>تنبيه من بوت تسجيل المواد:</b>\n'
            'فشل تسجيل الدخول إلى بوابة جامعة الدلتا.\n'
            f'<b>السبب:</b> {client.last_error}\n\n'
            f'⏱️ <b>المحاولة القادمة:</b> في تمام <b>{next_str}</b> (بعد 15 دقيقة)'
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
            f'⏱️ <b>الفحص القادم:</b> في تمام <b>{next_str}</b> (بعد 15 دقيقة تقريباً)'
        )
        send_telegram_message(msg)
        return

    has_open_seat = False
    courses_blocks = []

    for c in courses:
        c_id = c.get('CourseId')
        c_code = c.get('Code', '')
        c_name = c.get('Name', '')
        c_hours = c.get('CreditHours', 0)

        schedules = client.get_course_schedule(c_id)
        block = f'📚 <b>[{c_code}] {c_name}</b> ({c_hours} ساعات)\n'

        if not schedules:
            block += '  ⚠️ لا توجد مواعيد أو مجموعات معلنة بعد.\n'
        else:
            for s in schedules:
                grp = s['group_name']
                cap = s['capacity']
                reg = s['registered']
                avail = s['available_seats']
                blocked = s['is_blocked']
                is_open = s['is_open']

                if is_open:
                    has_open_seat = True
                    icon = '🟢'
                    status = f'<b>مفتوح للتسجيل! (متبقي {avail} مقعد)</b>'
                elif blocked:
                    icon = '🔴'
                    status = f'مغلق / Blocked ({reg}/{cap})'
                elif avail == 0:
                    icon = '🔴'
                    status = f'مكتمل ({reg}/{cap})'
                else:
                    icon = '🟡'
                    status = f'متبقي {avail} مقعد'

                block += f'  {icon} Group <b>{grp}</b>: {status}\n'
                if is_open and s.get('day'):
                    block += f"     ⏰ {s['day']} {s['time']} ({s['room']})\n"

        courses_blocks.append(block)

    if has_open_seat:
        header = '🚨 <b>تنبيه عاجل: توجد مقاعد شاغرة للتسجيل الآن!</b>\n'
    else:
        header = '📊 <b>تقرير فحص مواد جامعة الدلتا (كل 15 دقيقة)</b>\n'

    header += f'🕒 {now_str}\n\n'
    header += f'👤 الساعات المسموحة: <b>{allowed_hours}</b> | المدفوعة: <b>{paid_hours}</b> | المسجلة: <b>{registered_hours}</b>\n'
    header += f'⏳ الأيام المتبقية للتسجيل: <b>{remaining_days} يوم</b>\n\n'

    footer = f'\n⏱️ <b>الفحص القادم:</b> في تمام الساعة <b>{next_str}</b> (بعد 15 دقيقة تقريباً)'
    full_message = header + '\n'.join(courses_blocks) + footer
    print('[Checker] Sending report to Telegram...')
    send_telegram_message(full_message)

if __name__ == '__main__':
    run_check()
