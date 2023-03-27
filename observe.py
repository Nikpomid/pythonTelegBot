import asyncio
import logging
import sqlite3

import aiosqlite
import telegram
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from aiogram.utils import executor
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# Класс-обработчик событий файловой системы
class DataFileHandler(FileSystemEventHandler):
    def __init__(self, observer, conn, bot, loop):
        super().__init__()
        self.observer = observer
        self.conn = conn
        self.bot = bot
        self.loop = loop

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('data.db'):
            logging.info('Обнаружены изменения в базе данных data.db')

            # Получаем список новых значений
            new_values = []
            with self.conn:
                cursor = self.conn.execute('SELECT chat_id, field, value FROM sub_value WHERE notified = 0')
                new_values = cursor.fetchall()

            # Если есть новые значения, отправляем сообщения пользователям
            if new_values:
                for chat_id, field, value in new_values:
                    logging.info(f'Отправка сообщения для пользователя {chat_id} о появлении новых данных '
                                 f'по полю "{field}" со значением "{value}"')

                    # Получаем данные из таблицы data
                    data_rows = []
                    with self.conn:
                        cursor = self.conn.execute(f'SELECT * FROM data_old WHERE {field} = ?', (value,))
                        data_rows = cursor.fetchall()

                    # Формируем сообщение с данными
                    message_text = f'Новые данные по полю "{field}" со значением "{value}"\n\n'
                    for row in data_rows:
                        message_text += f'Краткий номер уведомления: {row[1]}\n' \
                                        f'Дата: {row[2]}\n' \
                                        f'Транспорт: {row[3]}\n' \
                                        f'Получатель: {row[4]}\n' \
                                        f'Номер уведомления: {row[5]}\n' \
                                        f'Регистрационный номер уведомления: {row[6]}\n' \
                                        f'Разрешение на временное хранение: {row[7]}\n' \
                                        f'Номер предшествующего свидетельства: {row[8]}\n' \
                                        f'Книжка МДП: {row[9]}\n' \
                                        f'INV: {row[10]}\n' \
                                        f'CMR: {row[11]}\n\n'

                    # Отправляем сообщение пользователю
                    asyncio.run(self.send_message(chat_id, message_text))

                    # Обновляем значение notified для записи в таблице sub_value
                    with self.conn:
                        self.conn.execute(
                            'UPDATE sub_value SET notified = 1 WHERE chat_id = ? AND field = ? AND value = ?',
                            (chat_id, field, value))

    async def send_message(self, chat_id, message_text):
        try:
            await self.bot.send_message(chat_id, message_text, parse_mode=ParseMode.HTML)
        except telegram.error.TelegramError as e:
            logging.error(f'Ошибка при отправке сообщения пользователю {chat_id}: {e}')


