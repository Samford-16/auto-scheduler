# A-Schedule

A web app that builds weekly shift schedules for small businesses. A manager enters their workers, each worker's availability, roles, and weekly hour limit, then lists the shifts they need covered. A-Schedule assigns workers automatically, flags any slot it could not fill, and lets the manager adjust the result by hand.

Built as my Information Systems capstone project at the College of Staten Island (CUNY).

## Features

- **Automatic scheduling.** Fills each shift with workers who are available that day, hold the required role, and have hours left in their weekly limit.
- **Unfilled slot tracking.** Slots that cannot be covered stay on the schedule marked "Unassigned" so the gap is visible instead of silently dropped.
- **Manual adjustments.** Edit any shift's worker, time, or role, swap a worker for an eligible replacement, or remove a shift.
- **Conflict warnings.** The dashboard flags workers scheduled past their hour limit or on days they are not available.
- **Templates and refresh.** Save a set of shift requirements as a template, or rerun the last schedule after the team changes.
- **Schedule history.** Every time a schedule is replaced, the previous one is archived.
- **Audit log.** Records every add, edit, delete, and schedule run for the account.
- **Calendar view.** Day, week, and month views of the weekly schedule.
- **Export.** Download the schedule as CSV or print it to PDF.
- **Multi-company accounts.** Each business signs up separately and can only see its own data.
- **Theming.** Light and dark mode with an adjustable accent color.

## Tech stack

| Layer    | Technology                                   |
|----------|----------------------------------------------|
| Backend  | Python, Flask (REST API)                     |
| Database | SQLite                                       |
| Frontend | HTML, CSS, vanilla JavaScript (no framework) |
| Auth     | Salted password hashing (Werkzeug), bearer tokens |

## How the scheduler works

Scheduling is done in `build_schedule()` in `backend/app.py`. It is a greedy algorithm that works through the shift requirements in the order they were entered:

1. Find every worker who is available on the shift's day and holds the shift's role.
2. Skip anyone already assigned a shift that day (one shift per worker per day).
3. Skip anyone the shift would push past their weekly max hours, unless they are marked as overtime eligible.
4. Assign workers until the shift has as many as it needs.
5. Any remaining openings are saved as unassigned slots for the manager to fill manually.

Before a new schedule is written, the current one is copied into the history tables.

## Running it locally

Requires Python 3.9 or newer.

```bash
git clone https://github.com/Samford-16/auto-scheduler.git
cd auto-scheduler
pip install -r requirements.txt
python backend/app.py
```

Then open http://127.0.0.1:5000 and create an account. The SQLite database (`backend/workers.db`) is created automatically on first run.

Optional environment variables:

| Variable            | Default              | Purpose                          |
|---------------------|----------------------|----------------------------------|
| `HOST`              | `127.0.0.1`          | Address the server listens on    |
| `PORT`              | `5000`               | Port the server listens on       |
| `AUTO_SCHEDULER_DB` | `backend/workers.db` | Path to the SQLite database file |
| `FRONTEND_DIR`      | `frontend/`          | Folder the pages are served from |

## Project structure

```
auto-scheduler/
├── backend/
│   ├── app.py          # Flask routes, auth, scheduling algorithm
│   └── database.py     # SQLite connection and table setup
├── frontend/
│   ├── css/style.css   # Shared styles and theme system
│   ├── js/auth.js      # Shared session, API, and sidebar helpers
│   └── *.html          # One page per screen
└── requirements.txt
```

## Database design

| Table                     | Holds                                                |
|---------------------------|------------------------------------------------------|
| `companies`               | Accounts, hashed passwords, business hours           |
| `workers`                 | Name, weekly max hours, overtime flag, notes         |
| `roles`                   | Positions defined by each company                    |
| `worker_roles`            | Which workers can fill which roles (many to many)    |
| `availability`            | Days each worker can work                            |
| `schedule`                | The current week's shifts                            |
| `schedule_history`, `schedule_history_shifts` | Archived schedules            |
| `schedule_templates`, `template_shifts`       | Saved shift requirement sets  |
| `last_shift_requirements` | Inputs from the last run, used by Refresh            |
| `audit_log`               | Record of actions per company                        |

## Limitations

This was built as a class project, not a production service.

- The schedule is a repeating weekly template. Shifts are stored by weekday, not by calendar date.
- The greedy algorithm fills shifts in order, so it does not balance hours evenly across workers and can leave a later shift unfilled that a different assignment order would have covered.
- There is no email service, so there is no "forgot password" flow. Users can change their password if they know the current one.
- Session tokens do not expire on the server side, and there is no rate limiting on login.
- It runs on Flask's development server. A real deployment would need a WSGI server (such as Gunicorn) behind HTTPS.

## License

[MIT](LICENSE)
