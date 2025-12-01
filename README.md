# CAT App Web
This is a Flask-based web application for Computer Assisted Translation, migrated from a Python/Tkinter application.

## Features
- **Project Management**: Create projects by uploading DOCX files.
- **Translation Editor**: Translate segments with a side-by-side view.
- **Translation Memory (TM)**: Supports JSON-based TM. Imports and updates TM automatically.
- **Glossary**: Supports CSV glossary import.
- **Machine Translation**: Integration with DeepL (requires API Key).
- **External Resources**: Links to Bible Gateway and EGW Writings.
- **Search**: Search text within the project.
- **Export**: Export translated documents to DOCX.

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repo_url>
   cd catapp
   ```

2. **Install Dependencies**:
   ```bash
   pip install flask flask-sqlalchemy flask-login python-docx spacy requests psycopg2-binary
   python -m spacy download en_core_web_sm
   python -m spacy download xx_sent_ud_sm
   ```

3. **Database Setup**:
   - The app uses SQLite by default (`catapp.db`).
   - For PostgreSQL, set the `DATABASE_URL` environment variable:
     ```bash
     export DATABASE_URL="postgresql://user:password@localhost/dbname"
     ```

4. **Run the Application**:
   ```bash
   export FLASK_APP=run.py
   flask run
   ```

5. **Initialize Database**:
   Since the schema has changed to support users, you must reset the database:
   ```bash
   python setup_db.py
   ```
   This will create a default user: `test@example.com` / `password`.

6. **Access**:
   Open browser at `http://localhost:5000`.

## User Management (Manual)

Registration is disabled by default. To add users manually, use the `manage_users.py` script:

```bash
# Add a new user
python manage_users.py add user@example.com mypassword

# List users
python manage_users.py list

# Delete a user
python manage_users.py delete user@example.com
```

## Deployment (VPS + Gunicorn + Nginx)

### 1. Pre-Deployment Checklist
- [ ] Set `SECRET_KEY` environment variable (random string).
- [ ] Set `DATABASE_URL` environment variable (e.g., `postgresql://user:pass@localhost/dbname`).
- [ ] Run `python setup_db.py` to initialize the database (Warning: Drops existing tables!). For updates, use migrations (not included) or manual SQL.
- [ ] Create an initial admin/user: `python manage_users.py add me@mysite.com securepass`.

### 2. Install Production Server
```bash
pip install gunicorn
```

### 3. Run
```bash
gunicorn -w 4 -b 0.0.0.0:8000 run:app
```

### 4. Nginx Configuration
Configure Nginx to reverse proxy to port 8000. Ensure you serve static files efficiently if needed, though Flask can handle them for low traffic.

## Configuration
- **DeepL API Key**: Users add this in their browser settings (LocalStorage). Can also be set globally via `DEEPL_API_KEY` env var.
- **Secret Key**: Set `SECRET_KEY` for Flask sessions.
