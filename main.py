import requests
import time
import sqlite3
from bs4 import BeautifulSoup

# подключаемся к базе данных и создаем таблицу
conn = sqlite3.connect('data.db')
c = conn.cursor()
c.execute(
    'CREATE TABLE IF NOT EXISTS data (id INTEGER PRIMARY KEY AUTOINCREMENT, '
    'number TEXT, brief_number TEXT, date TEXT, transport TEXT, recipient TEXT, notice_number TEXT, registration_number TEXT, permission TEXT, previous_certificate TEXT, mdp_book TEXT, inv TEXT, cmr TEXT)')

while True:
    # получаем HTML-код страницы
    url = "https://ozerco.by/js/prif.html"
    response = requests.get(url, verify=False)
    html = response.content

    # парсим HTML-код с помощью Beautiful Soup
    soup = BeautifulSoup(html, "html.parser")
    # находим таблицу на странице
    table = soup.find("table")

    # извлекаем данные из каждой строки таблицы, пропуская первую строку (заголовки)
    rows = table.find_all("tr")[1:]
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
        # вставляем данные в таблицу базы данных
        c.execute(
            'INSERT INTO data (number, brief_number, date, transport, recipient, notice_number, registration_number, permission, previous_certificate, mdp_book, inv, cmr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (number, brief_number, date, transport, recipient, notice_number, registration_number, permission,
             previous_certificate, mdp_book, inv, cmr))
        conn.commit()

    # ждем 5 минут перед следующим запросом
    time.sleep(300)

# закрываем соединение с базой данных
conn.close()