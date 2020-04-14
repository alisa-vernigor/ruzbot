import requests
import arrow
from config import ID1, TZ


def get_nearest_lesson(id_type, user_id=ID1):
    now = arrow.now(TZ)
    date_first = now.date()
    date_second = now.shift(days=+1).date()

    if id_type == 'GroupId':
        id_type = 'group'
    else:
        id_type = 'student'

    r = requests.get(f'https://ruz.hse.ru/api/schedule/{id_type}/{user_id}?start={date_first.strftime("%Y.%m.%d")}'
                     f'&finish={date_second.strftime("%Y.%m.%d")}&lng=1')
    classes = r.json()

    for cls in classes:
        beginLesson = arrow.get(
            f'{cls["date"]} {cls["beginLesson"]}').replace(tzinfo=TZ)

        if now <= beginLesson:
            return cls

    return {}


def print_nearest_lesson(id_type, user_id=ID1):
    nearest_lesson = get_nearest_lesson(id_type, user_id)
    if len(nearest_lesson) == 0:
        return 'Сегодня и завтра больше пар нет, можете отдыхать :)'
    return f'Дисциплина: {nearest_lesson["discipline"]}\n' \
           f'Преподаватель: {nearest_lesson["lecturer"]}\n'\
           f'Тип занятия: {nearest_lesson["kindOfWork"]}\n' \
           f'День недели: {nearest_lesson["dayOfWeekString"]}\n' \
           f'Начало: {nearest_lesson["beginLesson"]}\n' \
           f'Ссылка: {nearest_lesson["url1"]}'


def get_names(name, name_type):
    r = requests.get(
        f'https://ruz.hse.ru/api/search?term={name}&type={name_type}'
    )
    names = r.json()
    return names
