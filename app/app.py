import os
import time

import pymysql
from flask import Flask, redirect, render_template_string, request

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}
APP_VERSION = os.environ.get("APP_VERSION", "1.0")
STATUSES = {"new": "Новая", "in_progress": "В работе", "done": "Закрыта"}


def get_db():
    return pymysql.connect(**DB_CONFIG)


def init_db(attempts=30):
    """Создаёт таблицу заявок. Ждёт, пока СУБД станет доступна."""
    for _ in range(attempts):
        try:
            with get_db() as conn, conn.cursor() as cur:
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS tickets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        author VARCHAR(100) NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        status ENUM('new','in_progress','done') NOT NULL DEFAULT 'new',
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
            return
        except pymysql.err.OperationalError:
            time.sleep(2)
    raise RuntimeError("База данных недоступна")


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Учёт заявок</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;color:#222}
 table{width:100%;border-collapse:collapse;margin-top:1rem}
 th,td{border-bottom:1px solid #ddd;padding:.5rem;text-align:left}
 form.add{display:flex;gap:.5rem;flex-wrap:wrap}
 input{padding:.4rem}
 .muted{color:#777;font-size:.9em}
</style></head><body>
<h1>Учёт заявок</h1>
<p class="muted">Версия приложения: {{ version }}</p>
<form class="add" method="post" action="/add">
  <input name="author" placeholder="Автор" required maxlength="100">
  <input name="title" placeholder="Суть проблемы" required maxlength="200" size="40">
  <button type="submit">Создать заявку</button>
</form>
<table>
  <tr><th>№</th><th>Автор</th><th>Заявка</th><th>Статус</th><th>Создана</th><th></th></tr>
  {% for t in tickets %}
  <tr>
    <td>{{ t.id }}</td><td>{{ t.author }}</td><td>{{ t.title }}</td>
    <td>{{ statuses[t.status] }}</td><td>{{ t.created_at }}</td>
    <td>
      {% if t.status == 'new' %}
      <form method="post" action="/status/{{ t.id }}"><input type="hidden" name="status" value="in_progress"><button>В работу</button></form>
      {% elif t.status == 'in_progress' %}
      <form method="post" action="/status/{{ t.id }}"><input type="hidden" name="status" value="done"><button>Закрыть</button></form>
      {% endif %}
    </td>
  </tr>
  {% else %}
  <tr><td colspan="6">Заявок пока нет</td></tr>
  {% endfor %}
</table>
</body></html>"""


@app.get("/")
def index():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM tickets ORDER BY id DESC")
        tickets = cur.fetchall()
    return render_template_string(PAGE, tickets=tickets, statuses=STATUSES, version=APP_VERSION)


@app.post("/add")
def add():
    author = request.form.get("author", "").strip()[:100]
    title = request.form.get("title", "").strip()[:200]
    if author and title:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO tickets (author, title) VALUES (%s, %s)", (author, title))
    return redirect("/")


@app.post("/status/<int:ticket_id>")
def change_status(ticket_id):
    status = request.form.get("status")
    if status in STATUSES:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("UPDATE tickets SET status=%s WHERE id=%s", (status, ticket_id))
    return redirect("/")


@app.get("/health")
def health():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
    return {"status": "ok", "version": APP_VERSION}


init_db()
