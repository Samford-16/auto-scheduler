import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("AUTO_SCHEDULER_DB", os.path.join(BASE_DIR, "workers.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL, open_time TEXT DEFAULT '09:00',
        close_time TEXT DEFAULT '17:00', token TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL, name TEXT NOT NULL,
        FOREIGN KEY(company_id) REFERENCES companies(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL, name TEXT NOT NULL,
        max_hours INTEGER NOT NULL, overtime TEXT NOT NULL,
        notes TEXT DEFAULT '',
        FOREIGN KEY(company_id) REFERENCES companies(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS worker_roles (
        worker_id INTEGER, role_id INTEGER,
        FOREIGN KEY(worker_id) REFERENCES workers(id),
        FOREIGN KEY(role_id) REFERENCES roles(id),
        PRIMARY KEY(worker_id, role_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS availability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER, day TEXT,
        FOREIGN KEY(worker_id) REFERENCES workers(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL, worker_id INTEGER,
        day TEXT, start_time TEXT, end_time TEXT, role_id INTEGER,
        FOREIGN KEY(company_id) REFERENCES companies(id),
        FOREIGN KEY(worker_id) REFERENCES workers(id),
        FOREIGN KEY(role_id) REFERENCES roles(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL, action TEXT NOT NULL,
        detail TEXT, timestamp TEXT NOT NULL,
        FOREIGN KEY(company_id) REFERENCES companies(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS schedule_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL, label TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(company_id) REFERENCES companies(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS schedule_history_shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        history_id INTEGER NOT NULL, worker_id INTEGER,
        day TEXT, start_time TEXT, end_time TEXT, role_id INTEGER,
        FOREIGN KEY(history_id) REFERENCES schedule_history(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS schedule_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL, name TEXT NOT NULL,
        FOREIGN KEY(company_id) REFERENCES companies(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS template_shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL, day TEXT,
        start_time TEXT, end_time TEXT, role_id INTEGER,
        workers_needed INTEGER DEFAULT 1,
        FOREIGN KEY(template_id) REFERENCES schedule_templates(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS last_shift_requirements (
        company_id INTEGER PRIMARY KEY,
        shifts_json TEXT NOT NULL,
        FOREIGN KEY(company_id) REFERENCES companies(id))""")
    conn.commit()
    conn.close()
