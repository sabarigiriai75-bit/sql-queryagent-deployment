# 🤖 SQL QueryAgent

An AI-powered web app that lets anyone query a database in plain English. The user types a question, the backend turns it into a safe SQL query, runs it, and shows the results in a table. No SQL knowledge needed. ✨

🚀 **Live Demo:** https://sabari-sql-agent-frontend-copy.onrender.com/

📘 **API Docs (Swagger):** https://sql-queryagent-backend.onrender.com/docs

👨‍💻 **Developer:** [sabarigiriai75-bit](https://github.com/sabarigiriai75-bit)
💼 LinkedIn: Sabari Giri



---

## 📌 1. Project Overview

- 💬 Users ask questions like "Show top 3 students by cgpa in CSE department".
- 🗂️ The backend reads the real database schema (tables and columns).
- ⚙️ A schema-aware rule engine generates the SQL. If the question is too complex, an LLM (Claude) writes the SQL as a fallback.
- 🛡️ Every query is validated before it runs. Only safe, read-only queries are executed.
- 📊 Results are returned as JSON and shown in a clean table, along with the SQL that ran.

---

## ✨ 2. Features

### 🎯 Core features
- 🗣️ Natural language to SQL for any connected database
- 🔍 Automatic schema discovery (tables, columns, data types)
- 👀 Generated SQL is shown to the user with every result
- 📋 Results displayed in a table with row count and column names

### 🧠 Query intelligence
- 🔎 Filters (for example, cgpa above 8, department = CSE)
- 📈 Aggregates: count, average, group by department
- 🏆 Top-N and lowest-N queries (for example, top 3 students)
- ↕️ Sorting (sorted by / ordered by)
- 🪪 Lookup by roll number or ID
- 🤝 LLM fallback for questions the rules cannot parse

### 🗄️ Database management
- ➕ Add a database connection (MySQL, PostgreSQL, SQL Server, SQLite)
- 📃 List and delete saved connections
- 🎓 Built-in sample college database for instant testing
- 👤 Per-user connections using a user ID

### 🙌 Usability
- 🕘 Query history for each user
- 💡 Friendly error messages instead of crashes
- ❤️ Health-check endpoint for monitoring
- 📖 Auto-generated Swagger/OpenAPI documentation at `/docs`

---

## 🔐 3. Security Features

- ✅ **Read-only SQL only:** only SELECT-type queries are allowed (SELECT, WITH, EXPLAIN, SHOW, DESCRIBE).
- 🚫 **Destructive keyword blocking:** DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, GRANT and similar are rejected, even before connecting to the database.
- 1️⃣ **Single statement rule:** multiple statements separated by `;` are blocked.
- 🧩 **Malformed SQL checks:** incomplete clauses, unbalanced brackets and broken operators are rejected.
- 🕵️ **Hallucination guard:** SQL that uses a table not present in the database is rejected.
- 🎚️ **Filter check:** if the user asked for a condition (for example, cgpa above 8) and the SQL left it out, the query is rejected.
- 🧱 **LLM isolation:** the LLM only receives the table and column names. It never connects to the database. The backend validates and runs the SQL.
- 📏 **Row limits:** results are capped (default LIMIT 100, hard maximum 1000 rows).
- 🙈 **Credential protection:** database passwords are masked in error messages.
- 🔑 **Secrets in environment variables:** API keys are stored in Render environment settings and a local `.env` file that is excluded from GitHub.
- 🌐 **CORS restriction:** the backend accepts requests only from the configured frontend URL (`ALLOWED_ORIGINS`).
- 🔒 **HTTPS:** all traffic is encrypted by the Render hosting platform.

### 🛠️ Planned security improvements
- 🪙 Login with JWT authentication
- ⏱️ Rate limiting per user
- 👁️ Dedicated read-only database user
- ⌛ Query execution timeout

---

## 🧰 4. Tools and Technologies

### 🎨 Frontend
- ⚛️ React 19
- ⚡ Vite (build tool)
- 📡 Axios (API calls)
- 🧹 Oxlint (code linting)

### ⚙️ Backend
- 🐍 Python 3.11
- 🚀 FastAPI
- 🦄 Uvicorn (ASGI server)
- 🧬 SQLAlchemy (database access)
- 🔧 python-dotenv (environment variables)
- 🧠 LangChain with Anthropic Claude (LLM fallback)

### 🗄️ Database
- 💾 SQLite (sample college database and app storage)
- 🐬 MySQL, PostgreSQL and SQL Server connections supported

### 🧪 Testing
- ✔️ Pytest (regression tests)
- 🧾 Swagger UI and PowerShell for API testing

### 💻 Development tools
- 📝 VS Code
- 🌿 Git and GitHub
- 🪟 Windows PowerShell

---

## ☁️ 5. Deployment

- 🌍 **Platform:** Render (free tier)
- 🖥️ **Backend:** Render Web Service (FastAPI served with Uvicorn)
- 🎨 **Frontend:** Render Static Site (React built with Vite)
- 📄 **Config files:** `render.yaml` and `Procfile`
- 🔐 **Environment variables:** `ANTHROPIC_API_KEY`, `ALLOWED_ORIGINS`, `VITE_API_BASE_URL`
- 🔄 **CI/CD:** every `git push` to the `main` branch triggers an automatic redeploy

---

## 🗺️ 6. Architecture Diagram

```text
+------------------+      HTTPS      +--------------------------------+
|   User Browser   | --------------> |   React Frontend (Vite)        |
+------------------+                 |   Render Static Site           |
                                     +---------------+----------------+
                                                     |
                                           REST API (Axios, JSON)
                                                     |
                                                     v
                                     +--------------------------------+
                                     |   FastAPI Backend (Uvicorn)    |
                                     |   Render Web Service           |
                                     +---------------+----------------+
                                                     |
                                     +---------------v----------------+
                                     |  1. Discover database schema   |
                                     +---------------+----------------+
                                                     |
                                     +---------------v----------------+
                                     |  2. Rule engine builds SQL     |
                                     +---------------+----------------+
                                                     |
                                    cannot parse?    |
                              +----------------------+
                              |                      |
                              v                      |
                 +-------------------------+         |
                 | 3. LLM fallback (Claude)|         |
                 |    gets schema only     |         |
                 +------------+------------+         |
                              |                      |
                              +----------+-----------+
                                         |
                                         v
                         +-------------------------------+
                         |  4. SQL VALIDATOR             |
                         |  - SELECT only                |
                         |  - one statement              |
                         |  - tables must exist          |
                         |  - requested filters present  |
                         +-------+---------------+-------+
                                 |               |
                              unsafe            safe
                                 |               |
                                 v               v
                      +----------------+   +---------------------------+
                      | Blocked.       |   | 5. Execute on database    |
                      | Error returned |   |    (row limit applied)    |
                      +----------------+   +-------------+-------------+
                                                         |
                                                         v
                                           +---------------------------+
                                           |  MySQL / SQLite / others  |
                                           +-------------+-------------+
                                                         |
                                                 rows as JSON
                                                         |
                                                         v
                                           +---------------------------+
                                           | 6. React shows table + SQL|
                                           +---------------------------+
```

---

## 🔄 7. How It Works (Step by Step)

1. 💬 The user types a question in the React UI.
2. 📤 React sends the question and connection ID to the FastAPI backend.
3. 🗂️ The backend reads the database schema (tables and columns).
4. ⚙️ The rule engine tries to generate SQL from the question.
5. 🧠 If the rules cannot understand it, the LLM writes the SQL using only the schema.
6. 🛡️ The validator checks that the SQL is a single, safe SELECT using real tables.
7. 🚫 Unsafe queries are blocked and an error is returned.
8. ▶️ Safe queries run on the database with a row limit.
9. 📊 The rows are sent back as JSON, and React shows them in a table with the SQL.

---

## 🔌 8. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | ❤️ Check if the server is running |
| POST | `/api/databases/add` | ➕ Add a database connection |
| GET | `/api/databases/list` | 📃 List saved connections |
| DELETE | `/api/databases/{connection_id}` | 🗑️ Delete a connection |
| POST | `/api/query` | 💬 Ask a question and get results |
| GET | `/api/query-history` | 🕘 View past questions |

---

## 💡 9. Example Questions

- ✅ `Show all students`
- ✅ `Show top 3 students by cgpa in CSE department`
- ✅ `How many students are in each department?`
- 🚫 `Delete all students` (blocked by the validator)

---

## 💻 10. Run Locally

```bash
# Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Create a `.env` file in the project root with `ANTHROPIC_API_KEY=your_key_here`. Never commit this file. 🔑

---

## ⚠️ 11. Common Mistakes to Avoid

- ❌ Committing `.env` to GitHub. Keep it in `.gitignore`.
- ❌ Setting CORS to `*` in production.
- ❌ Trusting LLM output without validating it.
- ❌ Connecting with an admin or root database user. Use a read-only user.
- ⏳ Forgetting that the Render free tier sleeps. The first request can take up to a minute.

---

⭐ If you like this project, give it a star on GitHub!
