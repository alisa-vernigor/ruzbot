import os
import threading

import arrow
from flask import Flask
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

from config import TOKEN, TZ, proxy_url, proxy_user, proxy_pass
from data_catcher import get_nearest_lesson, print_nearest_lesson, get_names
from collections import defaultdict

request_kwargs = {
    'proxy_url': proxy_url,
    'urllib3_proxy_kwargs': {
        'username': proxy_user,
        'password': proxy_pass,
    }
}

updater = Updater(token=TOKEN, request_kwargs=request_kwargs, use_context=True)
dispatcher = updater.dispatcher

chat_ids = defaultdict(lambda: {'GroupId': [], 'StudentId': []})
tmp = {}


def subscribe(id_type, ruz_id, chat_id):
    global tmp
    if not (ruz_id, tmp[ruz_id]) in chat_ids[int(chat_id)][id_type]:
        chat_ids[int(chat_id)][id_type].append((ruz_id, tmp[ruz_id]))
    tmp = {}


def unsubscribe(id_type, chat_id, ruz_id, query):
    for i in range(len(chat_ids[int(chat_id)][id_type])):
        if chat_ids[int(chat_id)][id_type][i][0] == ruz_id:
            del chat_ids[int(chat_id)][id_type][i]
            break
    query.edit_message_text(text='Вы отписались')


def get_next(update, context):
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text='Расписание группы',
                               callback_data=f'GetGroup {update.effective_user.id}')],
         [InlineKeyboardButton(text='Индивидуальное расписание',
                               callback_data=f'GetStudent {update.effective_user.id}')]]
    )
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text='Какое расписание Вы хотите получить?',
        reply_markup=markup)
    return SUBQUESTION


def start_help(update, context):
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text='Здравствуйте! Я - рузбот, напомню о парах и скину расписание.\n'
        'Доступные команды:\n'
        '/help - помощь\n'
        '/subscribe - подписать чат на уведомления о приближающихся парах для группы или студента\n'
        '/unsubscribe - отписать чат от уведомлений\n'
        '/getnext - получить информацию о ближайшей паре для группы или студента, на которых подписан чат\n'
        'По всем вопросам обращаться к @sphericalpotatoinvacuum, @allisyonok или @grenlayk'
    )


def unsubscribe_chat(update, context):
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text='Расписание группы',
                               callback_data=f'UnSubGroup {update.effective_user.id}')],
         [InlineKeyboardButton(text='Индивидуальное расписание',
                               callback_data=f'UnSubStudent {update.effective_user.id}')]]
    )
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text="От чего вы хотите отписаться?",
        reply_markup=markup)
    return UNSUB


def subscribe_chat(update, context):
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text='Расписание группы',
                               callback_data=f'SubGroup {update.effective_user.id}')],
         [InlineKeyboardButton(text='Индивидуальное расписание',
                               callback_data=f'SubStudent {update.effective_user.id}')]]
    )
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text="Получать индивидуальное расписание или расписание группы?",
        reply_markup=markup)
    return SUBQUESTION


def button(update, context):
    query = update.callback_query
    data = query.data.split()

    if data[0] == 'SubGroup':
        if int(data[1]) == update.effective_user.id:
            query.edit_message_text(
                text='Введите номер группы в формате БПМИ195')
            return SUBGROUP
    elif data[0] == 'SubStudent':
        if int(data[1]) == update.effective_user.id:
            query.edit_message_text(text='Введите ФИО')
            return SUBSTUDENT
    elif data[0] == 'StudentId' or data[0] == 'GroupId':
        if data[1] != '0':
            if int(data[3]) == update.effective_user.id:
                subscribe(data[0], data[1], data[2])
                query.edit_message_text(text='Вы успешно подписались!')
        else:
            if int(data[3]) == update.effective_user.id:
                query.edit_message_text(
                    text='Попробуйте уточнить правильность написания. '
                    'Если не поможет, то Вас нет в базе данных РУЗа'
                )
                return ConversationHandler.END
    elif data[0] == 'UnSubGroup' or data[0] == 'UnSubStudent':
        print(data[1], update.effective_user.id)
        if int(data[1]) == update.effective_user.id:
            if data[0] == 'UnSubGroup':
                id_type = 'GroupId'
                text = 'От какой группы Вы хотите отписаться?'
                chosen_type = 'GroupChosen'
            else:
                id_type = 'StudentId'
                text = 'От какого студента Вы хотите отписаться?'
                chosen_type = 'StudentChosen'
            markup = []
            for (ruz_id, ruz_name) in chat_ids[update.effective_chat.id][id_type]:
                markup.append([InlineKeyboardButton(
                    text=f'{ruz_name}',
                    callback_data=f'{chosen_type} {ruz_id} '
                    f'{update.effective_chat.id} {update.effective_user.id}'
                )])
            if not markup:
                query.edit_message_text(
                    text='Вы ещё ни на кого не подписались. '
                    'Подписаться вы можете командой /subscribe'
                )
                return ConversationHandler.END
            query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(markup))
            return UNSUB
    elif data[0] == 'StudentChosen' or data[0] == 'GroupChosen':
        if int(data[3]) == update.effective_user.id:
            if data[0] == 'StudentChosen':
                id_type = 'StudentId'
            else:
                id_type = 'GroupId'
            unsubscribe(id_type, data[2], data[1], query)
            return ConversationHandler.END
    elif data[0] == 'GetGroup' or data[0] == 'GetStudent':
        if int(data[1]) == update.effective_user.id:
            if data[0] == 'GetStudent':
                id_type = 'StudentId'
                send_type = 'PrintStudent'
                message_text = 'Для кого вы хотите получить расписание?'
            else:
                id_type = 'GroupId'
                send_type = 'PrintGroup'
                message_text = 'Для какой группы вы хотите получить расписание?'
            chat_id = update.effective_chat.id

            if not chat_ids[chat_id][id_type]:
                query.edit_message_text(
                    text='Вы ещё ни на кого не подписались. '
                    'Подписатьсяs вы можете командой /subscribe'
                )
                return ConversationHandler.END

            if len(chat_ids[chat_id][id_type]) == 1:
                for (user_id, user_name) in chat_ids[chat_id][id_type]:
                    query.edit_message_text(
                        text=f'Расписание для: {user_name}\n{print_nearest_lesson(id_type, user_id)}'
                    )
                return ConversationHandler.END

            markup = []
            for (user_id, user_name) in chat_ids[chat_id][id_type]:
                markup.append([InlineKeyboardButton(
                    text=f'{user_name}',
                    callback_data=f'{send_type} {user_id}')])
            query.edit_message_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(markup))
            return PRINTNEXT
    elif data[0] == 'PrintGroup' or data[0] == 'PrintStudent':
        chat_id = update.effective_chat.id
        if data[0] == 'PrintStudent':
            id_type = 'StudentId'
        else:
            id_type = 'GroupId'
        for (user_id, user_name) in chat_ids[chat_id][id_type]:
            if int(user_id) == int(data[1]):
                query.edit_message_text(
                    text=f'Расписание для: {user_name}\n{print_nearest_lesson(id_type, user_id)}')
        return ConversationHandler.END


def to_ruz(name_type):
    def search(update, context):
        name = update.message.text

        if name_type == 'student':
            id_type = 'StudentId'
        else:
            id_type = 'GroupId'

        names = get_names(name, name_type)
        markup = []
        for name in names:
            tmp[name["id"]] = name["label"]
            markup.append([InlineKeyboardButton(
                text=f'{name["label"]}, {name["description"]}',
                callback_data=f'{id_type} {name["id"]} {update.message.chat_id} {update.effective_user.id}'
            )])
        markup.append([InlineKeyboardButton(
            text='Меня тут нет!',
            callback_data=f'{id_type} 0 0 {update.effective_user.id}'
        )])
        markup = InlineKeyboardMarkup(markup)

        if name_type == 'student':
            text = 'Следующие студенты удовлетворяют условиям поиска, выберите себя:'
        else:
            text = 'Следующие группы удовлетворяют условиям поиска, выберите свою:'
        update.message.reply_text(
            text=text,
            reply_markup=markup
        )

        return SUBCHOOSE
    return search


def check_timetable():
    timeout = 5

    now = arrow.now(TZ)

    for chat_id in chat_ids:
        for id_type in chat_ids[chat_id]:
            for (user_id, user_name) in chat_ids[chat_id][id_type]:
                nearest_lesson = get_nearest_lesson(id_type, user_id)
                if nearest_lesson == {}:
                    continue
                if now <= arrow.get(
                    f'{nearest_lesson["date"]} {nearest_lesson["beginLesson"]}'
                ).replace(tzinfo=TZ) <= now.shift(minutes=+10):
                    updater.bot.send_message(
                        chat_id=chat_id,
                        text=f'Расписание для: {user_name}\n'
                             f'{print_nearest_lesson(id_type, user_id)}'
                    )
                    timeout = 700

    threading.Timer(timeout, check_timetable).start()


def cancel(update, context):
    update.message.reply_text('Жаль, что не смог Вам помочь.',
                              reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


start_handler = CommandHandler('start', start_help)
help_handler = CommandHandler('help', start_help)
subscribe_handler = CommandHandler('subscribe', subscribe_chat)
unsubscribe_handler = CommandHandler('unsubscribe', unsubscribe_chat)
getnext_handler = CommandHandler('getnext', get_next)
callback_handler = CallbackQueryHandler(button)

SUBQUESTION, SUBGROUP, SUBSTUDENT, SUBCHOOSE, UNSUB, PRINTNEXT = range(6)

sub_conv_handler = ConversationHandler(
    entry_points=[subscribe_handler],
    states={
        SUBQUESTION: [callback_handler],
        SUBGROUP: [MessageHandler(filters=Filters.text, callback=to_ruz('group'))],
        SUBSTUDENT: [MessageHandler(filters=Filters.text, callback=to_ruz('student'))],
        SUBCHOOSE: [callback_handler]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    allow_reentry=True
)

unsub_conv_handler = ConversationHandler(
    entry_points=[unsubscribe_handler],
    states={
        UNSUB: [callback_handler],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    allow_reentry=True
)

next_conv_handler = ConversationHandler(
    entry_points=[getnext_handler],
    states={
        SUBQUESTION: [callback_handler],
        PRINTNEXT: [callback_handler],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    allow_reentry=True
)

dispatcher.add_handler(start_handler)
dispatcher.add_handler(help_handler)
dispatcher.add_handler(sub_conv_handler)
dispatcher.add_handler(unsub_conv_handler)
dispatcher.add_handler(next_conv_handler)
dispatcher.add_handler(callback_handler)

check_timetable()

PORT = int(os.environ.get('PORT', '8443'))
DEV = bool(os.environ.get('DEV', False))

if DEV:
    updater.start_polling()
else:
    updater.start_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN)
    updater.bot.set_webhook('https://ruzbot.herokuapp.com/' + TOKEN)
    updater.idle()


app = Flask(__name__)


@app.route('/')
def basic_func():
    return 'Hello, world!'


if __name__ == '__main__':
    app.run(port=PORT, debug=True)
