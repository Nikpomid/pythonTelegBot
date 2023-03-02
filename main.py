import requests
import time
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime

# подключаемся к базе данных и создаем таблицы
conn = sqlite3.connect('data.db')
c = conn.cursor()
c.execute(
    'CREATE TABLE IF NOT EXISTS data (id INTEGER PRIMARY KEY AUTOINCREMENT, '
    'number TEXT, brief_number TEXT, date TEXT, transport TEXT, recipient TEXT, notice_number TEXT, '
    'registration_number TEXT, permission TEXT, previous_certificate TEXT, mdp_book TEXT, inv TEXT, cmr TEXT)')
c.execute(
    'CREATE TABLE IF NOT EXISTS data_old (id INTEGER PRIMARY KEY AUTOINCREMENT, '
    'number TEXT, brief_number TEXT, date TEXT, transport TEXT, recipient TEXT, notice_number TEXT, '
    'registration_number TEXT, permission TEXT, previous_certificate TEXT, mdp_book TEXT, inv TEXT, cmr TEXT, '
    'timestamp TEXT)')

while True:
    # получаем HTML-код страницы
    url = "https://ozerco.by/js/prif.html"
    response = requests.get(url, verify=False)
    html = response.content

    # парсим HTML-код с помощью Beautiful Soup
    soup = BeautifulSoup(html, "html.parser")
    # находим таблицу на странице
    table = soup.find("table")

    c.execute('DELETE FROM data')
    # извлекаем данные из каждой строки таблицы, пропуская первую строку (заголовки)
    rows = table.find_all("tr")[1:]
    # создаем список для хранения записей, которые будут перемещены в data_old
    for row in rows:
        data = row.find_all("td")
        # извлекаем нужные данные из каждой ячейки
        number = data[0].text
        brief_number = data[1].text
        date = data[2].text
        transport = data[3].text
        recipient = data[4].text
        notice_number = data[5].text
        registration_number = data[6].text
        permission = data[7].text
        previous_certificate = data[8].text
        mdp_book = data[9].text
        inv = data[10].text
        cmr = data[11].text
        c.execute(
            'INSERT INTO data (number, brief_number, date, transport, recipient, notice_number, registration_number, permission, previous_certificate, mdp_book, inv, cmr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (number, brief_number, date, transport, recipient, notice_number, registration_number, permission,
             previous_certificate, mdp_book, inv, cmr))
        conn.commit()
        # Извлекаем данные из таблицы data, проверяем существуют ли они в data_old
        c.execute('SELECT * FROM data')
        fetched_rows = c.fetchall()
        prom_data = []
        for row in fetched_rows:
            id, number, brief_number, date, transport, recipient, notice_number, registration_number,\
                permission, previous_certificate, mdp_book, inv, cmr = row
            # Проверяем, есть ли запись с такими данными в таблице data_old
            c.execute(
                'SELECT COUNT(*) FROM data_old WHERE number = ? AND brief_number = ? AND date = ? AND transport = ? AND recipient = ? AND notice_number = ? AND registration_number = ? AND permission = ? AND previous_certificate = ? AND mdp_book = ? AND inv = ? AND cmr = ?',
                (number, brief_number, date, transport, recipient, notice_number, registration_number, permission,
                 previous_certificate, mdp_book, inv, cmr))
            count = c.fetchone()[0]
            if count > 0:
                # Если запись уже существует в data_old, пропускаем ее
                continue
            # Извлекаем время добавления записи
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Добавляем запись в список для перемещения в data_old
            prom_data.append(
                (number, brief_number, date, transport, recipient, notice_number, registration_number, permission,
                 previous_certificate, mdp_book, inv, cmr, timestamp))
        # Перемещаем записи из списка prom_data в таблицу data_old
        c.executemany(
            'INSERT INTO data_old (number, brief_number, date, transport, recipient, notice_number, registration_number, '
            'permission, previous_certificate, mdp_book, inv, cmr, timestamp) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', prom_data)

        # Удаляем записи из таблицы data_old, которые находятся там более 5 дней
        c.execute("DELETE FROM data_old WHERE timestamp <= datetime('now', '-5 days')")

        # Сохраняем изменения в базе данных
        conn.commit()

        # Очищаем список prom_data
        prom_data.clear()

        # Ждем 10 минут перед повторным выполнением цикла
    time.sleep(30)

conn.close()
