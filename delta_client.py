import requests
from bs4 import BeautifulSoup
import urllib3
import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DeltaClient:
    def __init__(self, username=None, password=None):
        self.username = username or config.STUDENT_ID
        self.password = password or config.STUDENT_PASS
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
        })
        self.is_logged_in = False

    def login(self) -> bool:
        try:
            get_resp = self.session.get(config.DELTA_LOGIN_URL, verify=False, timeout=20)
            if get_resp.status_code != 200:
                print(f'[DeltaClient] Failed to load login page. Status: {get_resp.status_code}')
                return False

            soup = BeautifulSoup(get_resp.text, 'html.parser')
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})
            viewstategen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
            eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})

            if not viewstate:
                print('[DeltaClient] Could not find ASP.NET ViewState inputs.')
                return False

            payload = {
                '__VIEWSTATE': viewstate['value'],
                '__VIEWSTATEGENERATOR': viewstategen['value'] if viewstategen else 'C2EE9ABB',
                '__EVENTVALIDATION': eventvalidation['value'] if eventvalidation else '',
                'txtname': self.username,
                'type': '1',  # 1 = Student
                'txtPass': self.password,
                'Button1': 'Login'
            }

            headers = {
                'Origin': config.DELTA_BASE_URL,
                'Referer': config.DELTA_LOGIN_URL
            }

            post_resp = self.session.post(
                config.DELTA_LOGIN_URL,
                data=payload,
                headers=headers,
                verify=False,
                allow_redirects=False,
                timeout=20
            )

            # Delta portal redirects (302) to /Profile/StudentProfile on successful login
            if post_resp.status_code == 302 and 'StudentProfile' in post_resp.headers.get('Location', ''):
                self.is_logged_in = True
                print('[DeltaClient] Successfully logged in!')
                return True
            elif '.ASPXAUTH' in self.session.cookies:
                self.is_logged_in = True
                print('[DeltaClient] Successfully logged in (Auth cookie present)!')
                return True
            else:
                print('[DeltaClient] Login failed. Invalid credentials or portal error.')
                return False

        except Exception as e:
            print(f'[DeltaClient] Login exception: {e}')
            return False

    def get_registration_info(self) -> dict:
        if not self.is_logged_in:
            if not self.login():
                return {}
        try:
            url = f'{config.DELTA_BASE_URL}/Registered/GetStudentResiterationInfo'
            headers = {
                'Referer': f'{config.DELTA_BASE_URL}/Registered/CoursesRegisteration',
                'X-Requested-With': 'XMLHttpRequest'
            }
            resp = self.session.get(url, headers=headers, verify=False, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list):
                    return data[0]
            return {}
        except Exception as e:
            print(f'[DeltaClient] Error fetching registration info: {e}')
            return {}

    def get_available_courses(self) -> list:
        if not self.is_logged_in:
            if not self.login():
                return []
        try:
            url = f'{config.DELTA_BASE_URL}/Registered/GetStudentResiterationCourses'
            headers = {
                'Referer': f'{config.DELTA_BASE_URL}/Registered/CoursesRegisteration',
                'X-Requested-With': 'XMLHttpRequest'
            }
            params = {
                'GradeStatusIds': '0,1,2,3,4,5,',
                'GroupsIds': '-1',
                'IsVirtualRegisteration': 'false'
            }
            resp = self.session.get(url, params=params, headers=headers, verify=False, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
            return []
        except Exception as e:
            print(f'[DeltaClient] Error fetching courses: {e}')
            return []

    def get_course_schedule(self, course_id: int) -> list:
        if not self.is_logged_in:
            if not self.login():
                return []
        try:
            url = f'{config.DELTA_BASE_URL}/Registered/GetCourseSchedual'
            headers = {
                'Referer': f'{config.DELTA_BASE_URL}/Registered/CoursesRegisteration',
                'X-Requested-With': 'XMLHttpRequest'
            }
            resp = self.session.get(url, params={'CourseId': course_id}, headers=headers, verify=False, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    schedules = []
                    for item in data:
                        cap = item.get('StudentsCount', 0)
                        reg = item.get('RegisteredCount', 0)
                        avail = max(0, cap - reg)
                        blocked = item.get('IsBlocked', False)
                        schedules.append({
                            'group_name': item.get('GroupName', 'Unknown'),
                            'day': item.get('DayWeekName', ''),
                            'time': item.get('Time', ''),
                            'room': item.get('ClassRoomName', ''),
                            'type': item.get('NameEn', ''),
                            'staff': item.get('Staff', '').strip(),
                            'capacity': cap,
                            'registered': reg,
                            'available_seats': avail,
                            'is_blocked': blocked,
                            'is_open': (avail > 0) and (not blocked)
                        })
                    return schedules
            return []
        except Exception as e:
            print(f'[DeltaClient] Error fetching schedule for course {course_id}: {e}')
            return []
