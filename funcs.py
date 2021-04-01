import re
import typing as tp
from os import path
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dateutil import tz
from ics import Calendar, Event

from classes import Lesson
from valid_group_ids import valid_ids

request_queue = set()


def is_id_in_queue(group_id: int):
    return group_id in request_queue


def set_up_schedule(group_id: int, subgroup_no: int):
    # download schedule HTML page if not present
    if not path.exists(f"raw_schedule/{group_id}.html"):
        if fetch_schedule(group_id):
            print('Schedule retrieved successfully')
        else:
            request_queue.remove(group_id)
            exit('Error retrieving schedule')
    else:
        print('Schedule already saved. Loading up.')

    # convert HTML schedule to an array of Lesson objects
    try:
        lessons = convert_html_to_lesson(f'{group_id}.html', subgroup_no)
    except Exception as E:
        request_queue.remove(group_id)
        exit(f'Error converting HTML into Lesson objects: {E}')

    if convert_lesson_to_ics(lessons, group_id, subgroup_no):
        request_queue.remove(group_id)
        print('Successful ics conversion, file saved.')
    else:
        request_queue.remove(group_id)
        exit('Failed to convert to ics.')


def convert_html_to_lesson(filename: str, subgroup: int) -> tp.List[Lesson]:
    schedule_html = open(f'raw_schedule/{filename}', 'r')

    # parse schedule
    soup = BeautifulSoup(schedule_html, 'html.parser')
    schedule = soup.find('table', class_='schedule')
    table_rows = schedule.find('tbody').find_all('tr')
    all_lessons = []

    # iterate through the rows of the schedule table
    for row in table_rows:
        # if row contains date, parse it
        dayname = row.find('th', class_='dayname')
        if dayname is not None:
            date: str = dayname.text.split(',')[0]
            dayname = None
            continue

        # if row is not date, assume it is a lesson entry.
        # initialize a Lesson object and fill it's fields with data parsed from the row
        lesson = Lesson()

        # get lesson's start and end times
        timeframe: tp.List[str] = row.find('th').text.split(' — ')
        # get string timestamps
        start_time = f'{date} {timeframe[0]}'
        end_time = f'{date} {timeframe[1]}'
        # convert to datetime objects
        start_time = datetime.strptime(start_time, '%d.%m.%Y %H:%M')
        start_time = start_time.replace(tzinfo=tz.gettz('Europe/Moscow'))
        start_time = start_time.astimezone(tz.tzutc())
        end_time = datetime.strptime(end_time, '%d.%m.%Y %H:%M')
        end_time = end_time.replace(tzinfo=tz.gettz('Europe/Moscow'))
        end_time = end_time.astimezone(tz.tzutc())
        lesson.start_time = start_time
        lesson.end_time = end_time

        # extract lesson type
        lesson_data = row.find_all('td')

        if len(lesson_data) > 1:
            lesson_data = lesson_data[subgroup - 1]
        else:
            if not 1 <= subgroup <= 2:
                raise IndexError
            lesson_data = lesson_data[0]

        try:
            lesson.type = re.findall('\[.*\]', lesson_data.text)[0][1:-1]
        except IndexError:
            lesson.type = ''

        # extract lesson title
        try:
            lesson.title = lesson_data.find("strong").text
        except AttributeError:
            try:
                lesson.title = lesson_data.find("strong").find("a").text
            except AttributeError:
                continue

        # extract lesson's online course link if present
        course_link = lesson_data.find("strong").find("a")
        if course_link is not None:
            lesson.course_link = course_link['href']

        # extract lesson's location
        try:
            lesson.location = re.findall('</a>, .*</td>', str(lesson_data))[-1][6:-5]
        except IndexError:
            lesson.type = ''

        # extract teacher
        try:
            for hl in lesson_data.find_all('a'):
                if 'atlas' in hl['href']:
                    lesson.teacher = hl.text
        except TypeError:
            pass

        # save lesson instance for future use
        all_lessons.append(lesson)

    return all_lessons


def convert_lesson_to_ics(lessons: tp.List[Lesson], group_id: int, subgroup: int = 1) -> bool:
    try:
        # form an ics calendar
        calendar = Calendar()

        # create a calendar event for each lesson
        for lesson in lessons:
            lesson_event = Event()
            
            if lesson.type:
                lesson_event.name = f'{lesson.title} [{lesson.type}]'
            else:
                lesson_event.name = lesson.title
            
            lesson_event.begin = lesson.start_time.strftime('%Y-%m-%d %H:%M:%S')
            lesson_event.end = lesson.end_time.strftime('%Y-%m-%d %H:%M:%S')

            description = []
            if lesson.location:
                description.append(f'Место: {lesson.location}')
                lesson_event.location = lesson.location
            if lesson.course_link:
                description.append(f'Moodle: {lesson.course_link}')
            if lesson.teacher:
                description.append(f'Преподаватель: {lesson.teacher}')
            if description:
                lesson_event.description = '\n'.join(description)

            # add event to the calendar
            calendar.events.add(lesson_event)

        # save the calendar to an ics file
        with open(f'processed_schedule/{group_id}-{subgroup}.ics', 'w') as file:
            file.writelines(calendar)

        return True

    except Exception as E:
        print(f'An error occurred while converting lessons:\n{E}')
        return False


# fetch schedule
def fetch_schedule(group_id: int) -> bool:
    base_url: str = 'https://guide.herzen.spb.ru/static/schedule_dates.php'
    schedule_url: str = f'{base_url}?id_group={group_id}&date1=2021-01-01&date2='
    request = requests.get(schedule_url)

    if not request.ok:
        print(f'Error retrieving schedule. Request code: {request.status_code}.')
        return False
    else:
        with open(f'raw_schedule/{group_id}.html', 'w') as file:
            file.writelines(request.text)
        return True


# validate group id
def is_valid_id(group_id: int) -> bool:
    return group_id in valid_ids
