import os
import datetime
from peewee import SqliteDatabase, Model, CharField, BooleanField, DateField,IntegerField
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.types import ParseMode
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import pandas as pd
import io
import xlsxwriter
import sqlite3
from aiogram.dispatcher.filters import Text
import config
import logging
from aiogram.types.message import ContentType
import aiocron

# Определяем токен бота и chat_id суперпользователя
BOT_TOKEN = '2099288144:AAGXadtWRI9BNf5nt87TA4eLFoVtVz50DyE'
SUPERUSER_CHAT_ID = -1001806118480

# log
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Определяем базу данных
db_path = os.path.join(os.path.dirname(__file__), 'users.db')
db = SqliteDatabase(db_path)


# Определяем модель пользователя
class User(Model):
    telegram_chat_id = CharField(unique=True)
    organization_name = CharField(null=True)
    contact_info = CharField(null=True)
    approved = BooleanField(default=False)
    is_subscribed = BooleanField(default=False)
    subscription_end_date = DateField(null=True)
    subscription_count = IntegerField(default=0)

    class Meta:
        database = db


# Создаем таблицу пользователей в базе данных, если ее нет
with db:
    db.create_tables([User])


# prices
PRICE = types.LabeledPrice(label="Подписка на 1 месяц", amount=500 * 100)  # в копейках (руб)


# buy
@dp.message_handler(commands=['buy'])
async def buy(message: types.Message):
    user = User.get_or_none(telegram_chat_id=str(message.chat.id), approved=True)
    if user:
        # Получаем всех пользователей из базы данных, кроме суперпользователя
        users = User.select().where(User.approved == True, User.organization_name != "Superuser")
        if config.PAYMENTS_TOKEN.split(':')[1] == 'TEST':
            await bot.send_message(message.chat.id, "Тестовый платеж!!!")

        await bot.send_invoice(message.chat.id,
                               title="Подписка на бота",
                               description="Активация подписки на бота на 1 месяц",
                               provider_token=config.PAYMENTS_TOKEN,
                               currency="rub",
                               photo_url="https://www.ozerco.by/img/logo.png",
                               photo_width=416,
                               photo_height=234,
                               photo_size=416,
                               is_flexible=False,
                               prices=[PRICE],
                               start_parameter="one-month-subscription",
                               payload="test-invoice-payload")
    else:
        await message.answer("Вы не являетесь зарегистрированным пользователем или не прошли модерацию.")


# pre checkout  (must be answered in 10 seconds)
@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


# successful payment
@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    print("SUCCESSFUL PAYMENT:")
    payment_info = message.successful_payment.to_python()
    for k, v in payment_info.items():
        print(f"{k} = {v}")

    await bot.send_message(message.chat.id,
                           f"Платёж на сумму {message.successful_payment.total_amount // 100} {message.successful_payment.currency} прошел успешно!!!")
    user = User.get_or_none(telegram_chat_id=str(message.chat.id), approved=True)
    if user:
        user.is_subscribed = True
        if user.subscription_end_date and user.subscription_end_date >= datetime.date.today():
            # Если у пользователя уже есть активная подписка, то добавляем 30 дней к существующей дате окончания подписки
            user.subscription_end_date += datetime.timedelta(days=30)
        else:
            # Иначе добавляем 30 дней к текущей дате
            user.subscription_end_date = datetime.date.today() + datetime.timedelta(days=30)
        user.subscription_count += 1
        user.save()
        await bot.send_message(message.chat.id,
                               f"Спасибо, что подписались!!! Ваша подписка действительна до {user.subscription_end_date}")
    else:
        await bot.send_message(message.chat.id,
                               "Вы не являетесь зарегистрированным пользователем или не прошли модерацию.")


# Функция для отправки сообщения о необходимости продления подписки
async def send_subscription_reminder(user_id):
    user = User.get_or_none(telegram_chat_id=str(user_id), approved=True)
    if user and user.is_subscribed and user.subscription_end_date:
        days_left = (user.subscription_end_date - datetime.date.today()).days
        if days_left == 1:
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("Да", callback_data="subscribe"),
                       types.InlineKeyboardButton("Нет", callback_data="cancel"))
            await bot.send_message(user.telegram_chat_id, "У вас остался 1 день подписки. Хотите продлить подписку?",
                                   reply_markup=markup)


# Запускаем планировщик задач
@aiocron.crontab('36 23 * * *')
async def check_subscriptions():
    # Выбираем всех пользователей
    users = User.select().where(User.approved == True)
    for user in users:
        # Отправляем напоминание о продлении подписки
        await send_subscription_reminder(user.telegram_chat_id)


# Обработчик нажатия кнопки "Да"
@dp.callback_query_handler(lambda c: c.data == 'subscribe')
async def process_callback_subscribe(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    # Отправляем сообщение от имени пользователя
    await bot.send_message(callback_query.from_user.id, "Нажмите на /buy")


# Обработчик нажатия кнопки "Нет"
@dp.callback_query_handler(lambda c: c.data == 'cancel')
async def process_callback_cancel(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.message.chat.id,
                           "Вы всегда можете продлить/купить подписку через команду /buy")


# Определяем хэндлер, который будет реагировать на все текстовые сообщения,
# не являющиеся командами ПРОВЕРИТЬ !!!!!!
@dp.message_handler(Text(equals="", ignore_case=True))
async def handle_text_messages(message: types.Message):
    # Отправляем пользователю заглушку и просим начать с команды /start
    await message.reply("Введите /start, чтобы начать использовать бота")


@dp.message_handler(commands=['excel'])
async def send_excel_table(message: types.Message):
    user = User.get_or_none(telegram_chat_id=str(message.chat.id), approved=True)
    if user:
        # Получаем всех пользователей из базы данных, кроме суперпользователя
        users = User.select().where(User.approved == True, User.organization_name != "Superuser")

        # подключаемся к базе данных
        conn = sqlite3.connect('data.db')

        # получаем данные из базы данных
        df = pd.read_sql_query("SELECT number, "
                               "brief_number, date, transport, recipient, notice_number, "
                               "registration_number, permission, previous_certificate, "
                               "mdp_book, inv, cmr FROM data WHERE recipient = ?", conn, params=(user.organization_name,))
        # закрываем соединение с базой данных
        conn.close()

        if df.empty:
            await message.answer(f"По организации {user.organization_name} ничего не найдено.")
            return

        # создаем объект io.BytesIO для записи таблицы в формате Excel
        excel_file = io.BytesIO()

        # создаем объект xlsxwriter и устанавливаем форматирование
        workbook = xlsxwriter.Workbook(excel_file)
        worksheet = workbook.add_worksheet()
        bold = workbook.add_format({'bold': True})
        worksheet.set_column('A:A', 10)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 20)
        worksheet.set_column('F:F', 20)
        worksheet.set_column('G:G', 25)
        worksheet.set_column('H:H', 20)
        worksheet.set_column('I:I', 25)
        worksheet.set_column('J:J', 25)
        worksheet.set_column('K:K', 20)
        worksheet.set_column('L:L', 20)

        # заполняем таблицу данными из базы данных
        row = 0
        col = 0
        for header in df.columns:
            worksheet.write(row, col, header, bold)
            col += 1
        for index, row_data in df.iterrows():
            row += 1
            col = 0
            for item in row_data:
                worksheet.write(row, col, item)
                col += 1

        # закрываем книгу
        workbook.close()

        # переводим указатель в начало файла
        excel_file.seek(0)

        # отправляем файл пользователю
        excel_file_input = types.InputFile(excel_file, filename='transport_documents.xlsx')
        await bot.send_document(message.chat.id, excel_file_input, caption='Транспортные документы')

        # закрываем файл
        excel_file.close()
    else:
        await message.answer("Вы не являетесь зарегистрированным пользователем или не прошли модерацию.")


# Определяем функцию-обработчик команды /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # Получаем пользователя из базы данных
    user = User.get_or_create(telegram_chat_id=str(message.chat.id))[0]

    if user.approved:
        await message.answer("Вы уже зарегистрированы.")
    else:
        # Отправляем приветственное сообщение при команде /start
        await message.answer("Здравствуйте! Чтобы зарегистрироваться, отправьте следующую информацию:\n"
                             "Название организации. Контактная информация (адрес, телефон, e-mail)")


# Определяем функцию для удаления пользователя
def delete_user(user_id: int):
    User.delete_by_id(user_id)


# Определяем функцию для создания inline кнопки "удалить"
def get_delete_button(user_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton("Удалить", callback_data=f"delete_{user_id}")


# Определяем функцию-обработчик команды /list
@dp.message_handler(commands=['list'])
async def cmd_check(message: types.Message):
    if message.chat.id != SUPERUSER_CHAT_ID:
        await message.answer('Эта команда доступна только суперпользователю.')
        return
    # Выбираем всех пользователей
    users = User.select().where(User.approved == True)
    if not users:
        await message.answer('Зарегестрированных пользователей нет')
    else:
        # Выводим информацию о каждом пользователе
        for user in users:
            info = f'ID: {user.id}\n' \
                   f'Организация: {user.organization_name}\n' \
                   f'Контакты: {user.contact_info}\n' \
                   f'Одобрен: {user.approved}\n' \
                   f'Telegram chat_id: {user.telegram_chat_id}\n\n'

            # Создаем inline keyboard с кнопкой "удалить"
            keyboard = InlineKeyboardMarkup()
            keyboard.add(get_delete_button(user.id))

            await message.answer(info, reply_markup=keyboard)

# Определяем функцию-обработчик нажатия на inline кнопку "удалить"


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('delete_'))
async def process_delete(callback_query: types.CallbackQuery):
    # Получаем id пользователя, которого нужно удалить
    user_id = int(callback_query.data.split('_')[1])

    # Получаем объект пользователя по его id
    user = User.get(User.id == user_id)

    # Получаем название организации пользователя
    organization_name = user.organization_name

    # Удаляем пользователя из базы данных
    delete_user(user_id)
    # Отправляем сообщение о том, что пользователь удален, с указанием названия организации
    await callback_query.message.answer(f"Пользователь из организации '{organization_name}' с id {user_id} удален")

    # Отправляем пользователю сообщение о том, что он удален из авторизованных пользователей
    await bot.send_message(user.telegram_chat_id, "К сожалению, вы были удалены с авторизованных пользователей")

    # Удаляем inline keyboard после удаления пользователя
    await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id,
                                        reply_markup=None)


@dp.message_handler(commands=['full_list'])
async def cmd_check(message: types.Message):
    if message.chat.id != SUPERUSER_CHAT_ID:
        await message.answer('Эта команда доступна только суперпользователю.')
        return
    # Выбираем всех пользователей
    users = User.select()
    if not users:
        await message.answer('Зарегестрированных пользователей нет')
    else:
    # Выводим информацию о каждом пользователе
        for user in users:
            info = f'ID: {user.id}\n' \
                   f'Организация: {user.organization_name}\n' \
                   f'Контакты: {user.contact_info}\n' \
                   f'Одобрен: {user.approved}\n' \
                   f'Telegram chat_id: {user.telegram_chat_id}\n\n'

            # Создаем inline keyboard с кнопкой "удалить"
            keyboard = InlineKeyboardMarkup()
            keyboard.add(get_delete_button(user.id))

            await message.answer(info, reply_markup=keyboard)

# Определяем функцию-обработчик нажатия на inline кнопку "удалить"


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('delete_'))
async def process_delete(callback_query: types.CallbackQuery):
    # Получаем id пользователя, которого нужно удалить
    user_id = int(callback_query.data.split('_')[1])

    # Получаем объект пользователя по его id
    user = User.get(User.id == user_id)

    # Получаем название организации пользователя
    organization_name = user.organization_name

    # Удаляем пользователя из базы данных
    delete_user(user_id)
    # Отправляем сообщение о том, что пользователь удален, с указанием названия организации
    await callback_query.message.answer(f"Пользователь из организации '{organization_name}' с id {user_id} удален")

    # Отправляем пользователю сообщение о том, что он удален из авторизованных пользователей
    await bot.send_message(user.telegram_chat_id, "К сожалению, вы были удалены с авторизованных пользователей")

    # Удаляем inline keyboard после удаления пользователя
    await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id,
                                        reply_markup=None)


@dp.message_handler(commands=['check'])
async def cmd_check(message: types.Message):
    # Проверяем, что chat_id отправителя сообщения соответствует chat_id суперпользователя
    if message.chat.id != SUPERUSER_CHAT_ID:
        await message.answer('Эта команда доступна только суперпользователю.')
        return

    # Извлекаем из базы данных все записи пользователей, где approved равен False
    users = User.select().where(
        (User.approved == False) & (User.organization_name != None) & (User.contact_info != None))

    # Если таких записей нет, отправляем сообщение, что запросов на регистрацию нет
    if not users:
        await message.answer('Запросов на регистрацию нет.')
    else:
        # Если такие записи есть, отправляем сообщение со списком запросов на регистрацию
        for user in users:
            keyboard = InlineKeyboardMarkup(row_width=2)
            approve_button = InlineKeyboardButton('Принять', callback_data=f'approve_{user.telegram_chat_id}')
            reject_button = InlineKeyboardButton('Отклонить', callback_data=f'reject_{user.telegram_chat_id}')
            invalid_button = InlineKeyboardButton('Неверный формат',
                                                  callback_data=f'invalid_{user.telegram_chat_id}')
            keyboard.add(approve_button, reject_button, invalid_button)
            # Отформатируем каждую запись
            registration_request = (
                f"Запрос на регистрацию от {user.organization_name}\n"
                f"Контактная информация: {user.contact_info}\n"
                f"Telegram chat_id: {user.telegram_chat_id}\n"
                f"Статус: {'На рассмотрении' if not user.approved else 'Одобрено'}"
            )
            # Отправляем запрос на регистрацию суперпользователю
            if registration_request:
                await bot.send_message(chat_id=SUPERUSER_CHAT_ID, text=registration_request,
                                       parse_mode=ParseMode.HTML, reply_markup=keyboard)


# В обработчике сообщения с запросом на регистрацию
@dp.message_handler()
async def process_registration(message: types.Message):
    # Проверяем, есть ли у пользователя запись в базе данных
    user = User.get_or_none(telegram_chat_id=str(message.chat.id))
    if user is None:
        # Если запись пользователя не существует,
        # создаем ее
        user = User.create(telegram_chat_id=str(message.chat.id))

    if not user.organization_name or not user.contact_info:
        # Если запись пользователя не существует, или отсутствует информация об организации или контактах,
        # создаем ее или получаем из базы данных
        user = User.get_or_create(telegram_chat_id=str(message.chat.id))[0]

        # Если отсутствует информация об организации или контактах,
        # запрашиваем название организации и контактную информацию
        parts = message.text.split('.')
        if len(parts) >= 2:
            user.organization_name = parts[0].strip()
            user.contact_info = '.'.join(parts[1:]).strip()
            user.save()
            # Отправляем сообщение о том, что запрос на регистрацию отправлен
            await message.reply('Запрос на регистрацию отправлен на рассмотрение Озерцо-логистик')

            keyboard = InlineKeyboardMarkup(row_width=2)
            approve_button = InlineKeyboardButton('Принять', callback_data=f'approve_{user.telegram_chat_id}')
            reject_button = InlineKeyboardButton('Отклонить', callback_data=f'reject_{user.telegram_chat_id}')
            invalid_button = InlineKeyboardButton('Неверный формат', callback_data=f'invalid_{user.telegram_chat_id}')
            keyboard.add(approve_button, reject_button, invalid_button)

            # Формируем запрос на регистрацию
            registration_request = (
                f"Запрос на регистрацию от {user.organization_name}\n"
                f"Контактная информация: {user.contact_info}\n"
                f"Telegram chat_id: {user.telegram_chat_id}"
            )

            # Отправляем запрос на регистрацию суперпользователю
            if registration_request:
                await bot.send_message(chat_id=SUPERUSER_CHAT_ID, text=registration_request,
                                       parse_mode=ParseMode.HTML, reply_markup=keyboard)

        else:
            await message.reply(
                'Неверный формат. Введите контактную информацию и название организации, разделив их точкой')
    elif not user.approved:
        await message.reply('Запрос на регистрацию уже отправлен на рассмотрение Озерцо-логистик')


# Обработчик InlineKeyboardButton "Принять"
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('approve_'))
async def process_approve(callback_query: types.CallbackQuery):
    # Получаем chat_id пользователя из callback_data
    user_chat_id = callback_query.data.split('_')[1]
    # Получаем пользователя из базы данных по chat_id
    user = User.get_or_none(telegram_chat_id=str(user_chat_id))
    if user:
        # Устанавливаем флаг approved=True и сохраняем пользователя в базе данных
        user.approved = True
        user.save()
        # Удаляем InlineKeyboard
        await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id)
        # Отправляем сообщение пользователю о том, что его запрос на регистрацию одобрен
        await bot.send_message(chat_id=user.telegram_chat_id, text='Ваш запрос на регистрацию одобрен')
        # Показываем пользователю клавиатуру с кнопкой "Транспорт в ЗТК"
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton('/excel (Запрос транспорт в ЗТК)'))
        keyboard.add(KeyboardButton('/buy (Оформить подписку)'))
        await bot.send_message(chat_id=user.telegram_chat_id, text='Выберите действие:', reply_markup=keyboard)


# Обработчик InlineKeyboardButton "Отклонить"
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('reject_'))
async def process_reject(callback_query: types.CallbackQuery):
    # Получаем chat_id пользователя из callback_data
    user_chat_id = callback_query.data.split('_')[1]
    # Получаем пользователя из базы данных по chat_id
    user = User.get_or_none(telegram_chat_id=str(user_chat_id))
    if user:
        # Удаляем пользователя из базы данных
        user.delete_instance()
        # Удаляем InlineKeyboard
        await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id)
        # Отправляем сообщение пользователю о том, что его запрос на регистрацию отклонен
        await bot.send_message(chat_id=user_chat_id, text='Ваш запрос на регистрацию отклонен')


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('invalid_'))
async def process_wrong_format(callback_query: types.CallbackQuery):
    # Получаем chat_id пользователя из callback_data
    user_chat_id = callback_query.data.split('_')[1]
    # Получаем пользователя из базы данных по chat_id
    user = User.get_or_none(telegram_chat_id=str(user_chat_id))
    if user:
        # Удаляем пользователя из базы данных
        user.delete_instance()
        # Удаляем InlineKeyboard
        await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id)
        # Отправляем сообщение пользователю о том, что его запрос на регистрацию отклонен
        await bot.send_message(chat_id=user_chat_id, text='В вашем запросе на регистрацию был неверный формат')


dp.register_message_handler(cmd_start, commands=['start'])
dp.register_message_handler(process_registration)

# Запускаем бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
