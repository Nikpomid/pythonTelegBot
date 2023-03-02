import telebot
import pandas as pd
import sqlite3

# подключаемся к базе данных и создаем таблицу
conn = sqlite3.connect('users.db')
c = conn.cursor()

# создаем бота
bot = telebot.TeleBot('2099288144:AAGXadtWRI9BNf5nt87TA4eLFoVtVz50DyE')


# функция для обработки команды /excel
@bot.message_handler(commands=['excel'])
def send_excel_table(message):
    # получаем данные пользователя из базы данных
    user_id = message.from_user.id
    c.execute('SELECT organization_name, approved FROM users WHERE user_id = ?', (user_id,))
    user_data = c.fetchone()

    # проверяем, что пользователь существует и имеет доступ к таблице
    if user_data and user_data[1]:
        # извлекаем данные из базы данных
        c.execute('SELECT * FROM data WHERE recipient = ?', (user_data[0],))
        table_data = c.fetchall()

        # создаем DataFrame и Excel-таблицу
        df = pd.DataFrame(table_data, columns=['id', 'number', 'brief_number', 'date', 'transport', 'recipient', 'notice_number', 'registration_number', 'permission', 'previous_certificate', 'mdp_book', 'inv', 'cmr'])
        excel_table = pd.ExcelWriter('table.xlsx', engine='xlsxwriter')
        df.to_excel(excel_table, sheet_name='Sheet1', index=False)
        excel_table.save()

        # отправляем таблицу пользователю в чат
        with open('table.xlsx', 'rb') as file:
            bot.send_document(message.chat.id, file)

    else:
        bot.reply_to(message, 'У вас нет доступа к таблице.')

# функция для отправки кнопки Excel
def send_excel_button(message):
    # получаем данные пользователя из базы данных
    user_id = message.from_user.id
    c.execute('SELECT approved FROM users WHERE user_id = ?', (user_id,))
    user_data = c.fetchone()

    # если пользователь имеет доступ к таблице, отправляем кнопку Excel
    if user_data and user_data[0]:
        keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        button = telebot.types.KeyboardButton(text="Excel")
        keyboard.add(button)
        bot.send_message(message.chat.id, "Нажмите кнопку, чтобы получить таблицу в формате Excel:", reply_markup=keyboard)

# функция для обработки сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    send_excel_button(message) # отправляем кнопку Excel

# запускаем бота
bot.polling()