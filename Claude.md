# Context for Claude

- Use **English** for all code, explanations, and comments.  
- Use **Norwegian** only for UI text visible to end users.  
- Keep current structure: main.py, app/routes, templates, static, database.db.  
- Do not re-architect (no enterprise patterns). Keep it simple and flat.  
- Refactor only for readability, consistency, and cleanup.  
- Database = SQLite (database.db). Use ALTER TABLE migrations, never drop or reset. Preserve all data.  
- Always output full working code blocks, never pseudo code.  
- Before large or destructive changes: stop and ask for confirmation.  

---

# Project Overview

- **Language/Framework**: Python 3.13, Flask  
- **Structure**:  
  - main.py (entry point)  
  - app/routes (calendar, tasks, documents, suppliers, auth, dashboard)  
  - templates/ (HTML Jinja2 templates)  
  - static/ (css, js, logo)  
  - database.db (SQLite)  

- **Auth**: Microsoft Entra ID (via msal)  
- **Database**: SQLite, session storage = flask_session  
- **Modules**:  
  - Dashboard: landing page + quick links  
  - Calendar: events CRUD  
  - Tasks: todo → ongoing → done, archive system  
  - Documents: upload, tags, comments, sorting, permissions  
  - Suppliers: store supplier credentials with copy-to-clipboard  
  - Newsletter: internal news updates via email feed  

- **Hosting plan**: Windows PC (later production server), start via `python3 main.py` or `start.py`.  
