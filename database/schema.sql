CREATE TABLE workers (
    worker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
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

