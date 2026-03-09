CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
);

CREATE TABLE workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    max_hours INTEGER,
    overtime_allowed TEXT
);

CREATE TABLE availability (
    availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER,
    day TEXT,
    FOREIGN KEY(worker_id) REFERENCES workers(worker_id)
);

CREATE TABLE schedule (
    shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER,
    day TEXT,
    start_time TEXT,
    end_time TEXT
);

