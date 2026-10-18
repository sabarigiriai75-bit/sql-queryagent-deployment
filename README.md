# sql-queryagent-deployment
SQL QueryAgent: project description

Overview
SQL QueryAgent is a web app where a user types a question in plain English (for example, “Show the top 5 customers by total sales this month”) and gets the answer from a MySQL database. An LLM turns the question into a SQL query, the backend checks that the query is safe, and only then runs it. Users never need to know SQL.

Tech stack

Layer	Technology	Role
Frontend	React	Question box, results table, query history
Backend	FastAPI (Python)	REST API, authentication, AI and security logic
AI	LLM API	Converts the question to SQL using the table schema
Database	MySQL	Stores the business data
Deployment	Cloud hosting	Makes the app available online for other users
Features
Natural language to SQL: type a question and get a query generated from your database schema.
Instant results: output is shown in a clean table.
Generated SQL shown to the user: you can see and learn from the query that ran.
Schema-aware prompts: the LLM only sees your real table and column names, which reduces wrong queries.
Error handling: if the SQL fails, the user gets a friendly message instead of a crash.
Query history: past questions can be viewed again (if you store them).
REST API with auto docs: FastAPI gives you Swagger docs at /docs.
Cloud deployment: the frontend, backend and database run online instead of on your laptop.
Security features

This is the most important part of a text-to-SQL app, because the LLM writes the queries.

SQL validation (SELECT only): before running anything, the backend blocks DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE and multiple statements separated by ;.
Read-only database user: the app connects to MySQL with an account that only has SELECT permission. Even if validation is bypassed, the database refuses writes.
SQL injection protection: user input is never pasted directly into trusted SQL, and the validator checks the generated query.
Environment variables for secrets: DB password and LLM API key live in a .env file or the cloud provider’s secret settings, never in the code or on GitHub.
CORS restriction: FastAPI only accepts requests from your own frontend URL.
Authentication (JWT/login): only logged-in users can query the data.
Rate limiting: limits requests per user so nobody can abuse your LLM API credits.
Row limit and timeout: results are capped (for example LIMIT 100) and long queries are stopped, so one query cannot overload the server.
HTTPS: the cloud platform encrypts traffic between browser and server.
Logging and audit: every question, generated SQL and user is recorded so suspicious activity can be traced.
How it works (step by step)
The user types a question in the React UI.
React sends it to the FastAPI backend.
FastAPI checks the login token and rate limit.
The backend sends the question plus the database schema to the LLM.
The LLM returns a SQL query.
The SQL validator checks that it is a single, safe SELECT.
FastAPI runs it on MySQL using the read-only user.
MySQL returns the rows to FastAPI, which sends them back as JSON.
React shows the result in a table.
Common mistakes to avoid
Connecting to MySQL with the root user. Always create a read-only user.
Committing .env to GitHub. Add it to .gitignore.
Setting CORS to * in production.
Trusting the LLM output without validating it.
