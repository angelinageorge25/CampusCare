# CampusCare — Campus Complaint & Issue Tracker

A beginner-friendly Flask + SQLite + Bootstrap project for a college demo.

## Features
- Demo student and staff logins with role-based page access.
- Students create complaint tickets, choose a category or use rule-based category suggestions, and optionally attach a photo.
- Students see their own tickets, statuses, priority review flag, and staff updates.
- Staff view all tickets, update statuses, set priorities, and explicitly approve priorities.
- Staff insights summarize ticket counts by category and show examples of repeat reports.
- Sample tickets are created automatically on first run.

## Demo credentials
| Role | Username | Password |
|---|---|---|
| Student | `student` | `student123` |
| Staff | `staff` | `staff123` |

## Run locally (Windows / VS Code)
1. Install Python 3.10 or later.
2. Extract this ZIP and open the `campus_complaint_tracker` folder in VS Code.
3. Open **Terminal → New Terminal**.
4. (Recommended) Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
   Activate it on Windows:
   ```bash
   .venv\Scripts\activate
   ```
5. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
6. Start the website:
   ```bash
   python app.py
   ```
7. Open the local URL printed in terminal (usually http://127.0.0.1:5000).

## Suggested demo
1. Sign in as `student / student123`.
2. Submit a complaint and optionally add a photo.
3. Sign out, then sign in as `staff / staff123`.
4. Open the ticket, update status and priority, check the approval checkbox, and save.
5. Visit **Issue insights** to demonstrate recurring-issue summary.

## Project structure
```text
campus_complaint_tracker/
├── app.py
├── requirements.txt
├── README.md
├── campus_tracker.db       # created on first run
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── dashboard.html
│   ├── new_complaint.html
│   ├── ticket_detail.html
│   ├── insights.html
│   └── error.html
└── static/
    ├── style.css
    └── uploads/            # complaint photos saved here
```

## Scope and honest limitations
- Category suggestion is a transparent keyword-rule demo, not a trained AI model.
- Recurring-issue insights are count-based summaries. They are not generative AI.
- Priority is a suggested/default field and must be reviewed/approved by staff.
- This is a classroom prototype. Before public deployment, add CSRF protection, production secret management, stronger upload content validation, audit history, rate limits, privacy notices, and a production WSGI server. The demo accounts/passwords are not for real users.
- Bootstrap and Google Fonts are loaded from CDNs, so the page needs internet access for those assets.
