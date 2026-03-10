import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "workers.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS company (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        open_time TEXT NOT NULL,
        close_time TEXT NOT NULL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        max_hours INTEGER NOT NULL,
        overtime TEXT NOT NULL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS worker_roles (
        worker_id INTEGER,
        role_id INTEGER,
        FOREIGN KEY(worker_id) REFERENCES workers(id),
        FOREIGN KEY(role_id) REFERENCES roles(id),
        PRIMARY KEY(worker_id, role_id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS availability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        day TEXT,
        FOREIGN KEY(worker_id) REFERENCES workers(id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        day TEXT,
        start_time TEXT,
        end_time TEXT,
        role_id INTEGER,
        FOREIGN KEY(worker_id) REFERENCES workers(id),
        FOREIGN KEY(role_id) REFERENCES roles(id)
    )
    """)

    conn.commit()
    conn.close()