from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sql_agent import query_database
from database import get_db, engine
from db_manager import DatabaseManager
from models import DatabaseConnection, QueryLog, Base
from security import validate_query
from datetime import datetime
from typing import List, Optional
import uuid
import os

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# ── Rate limiter (10 requests / minute per IP) ──────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI(
    title="SQL QueryAgent",
    description="Query any database using plain English"
)

# Attach limiter state and middleware
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# CORS — restrict to known frontend origin in production, allow all locally
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_allow_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def ensure_sample_database(db: Session):
    """Seed sample database if user has no registered databases"""
    try:
        manager = DatabaseManager(db)
        dbs = manager.get_user_databases("user1")
        if not dbs:
            sample_db_file = os.path.abspath("sample_college.db")
            sample_engine = create_engine(
                f"sqlite:///{sample_db_file}",
                connect_args={"check_same_thread": False},
            )
            with sample_engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS students (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        department TEXT NOT NULL,
                        cgpa REAL NOT NULL,
                        email TEXT,
                        graduation_year INTEGER
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS courses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        course_name TEXT NOT NULL,
                        department TEXT NOT NULL,
                        credits INTEGER NOT NULL
                    );
                """))
                res = conn.execute(text("SELECT COUNT(*) FROM students"))
                if res.scalar() == 0:
                    conn.execute(text("""
                        INSERT INTO students (name, department, cgpa, email, graduation_year) VALUES
                        ('Aarav Sharma', 'CSE', 9.2, 'aarav@college.edu', 2025),
                        ('Ananya Roy', 'CSE', 8.8, 'ananya@college.edu', 2025),
                        ('Rohan Mehta', 'ECE', 7.9, 'rohan@college.edu', 2026),
                        ('Priya Patel', 'EEE', 8.5, 'priya@college.edu', 2025),
                        ('Vikram Singh', 'MECH', 6.9, 'vikram@college.edu', 2026),
                        ('Sneha Gupta', 'CSE', 9.5, 'sneha@college.edu', 2024),
                        ('Karthik Raja', 'ECE', 8.1, 'karthik@college.edu', 2025);
                    """))
                    conn.execute(text("""
                        INSERT INTO courses (course_name, department, credits) VALUES
                        ('Database Management Systems', 'CSE', 4),
                        ('Artificial Intelligence', 'CSE', 4),
                        ('Digital Signal Processing', 'ECE', 3),
                        ('Power Electronics', 'EEE', 4),
                        ('Thermodynamics', 'MECH', 3);
                    """))
                    conn.commit()

            manager.add_database(
                user_id="user1",
                db_name="Sample College DB",
                db_type="sqlite",
                host="localhost",
                port=0,
                username="",
                password="",
                database="sample_college.db"
            )
    except Exception as e:
        print(f"Sample DB initialization note: {e}")


# ============= REQUEST/RESPONSE MODELS =============

class AddDatabaseRequest(BaseModel):
    db_name: str
    db_type: str  # "mysql", "postgresql", "mssql", "sqlite"
    host: str = "localhost"
    port: int = 3306
    username: str = ""
    password: str = ""
    database: str


class DatabaseInfo(BaseModel):
    id: str
    name: str
    type: str
    host: str
    port: int
    database: str
    username: str
    created_at: str


class QueryRequest(BaseModel):
    query: str
    connection_id: str
    user_id: str = "user1"


class QueryResponse(BaseModel):
    success: bool
    result: str
    query: str
    timestamp: str
    executed_sql: Optional[str] = None
    database_name: Optional[str] = None
    database_id: Optional[str] = None
    row_count: Optional[int] = None
    columns: Optional[List[str]] = None
    rows: Optional[List[dict]] = None


# ============= ROUTES =============

@app.get("/")
async def root():
    return {
        "message": "Multi-Database AI Agent API",
        "features": [
            "Connect multiple databases",
            "Query with natural language",
            "View all connected databases",
            "Query history & audit logs"
        ]
    }


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


# ============= DATABASE CONNECTION ENDPOINTS =============

@app.post("/api/databases/add")
async def add_database(
    request: AddDatabaseRequest,
    db: Session = Depends(get_db),
    user_id: str = "user1"
):
    manager = DatabaseManager(db)
    result = manager.add_database(
        user_id=user_id,
        db_name=request.db_name,
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        username=request.username,
        password=request.password,
        database=request.database
    )
    if not result["success"]:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/databases/list")
async def list_databases(
    db: Session = Depends(get_db),
    user_id: str = "user1"
):
    ensure_sample_database(db)
    manager = DatabaseManager(db)
    databases = manager.get_user_databases(user_id)
    return {
        "user_id": user_id,
        "total_databases": len(databases),
        "databases": databases
    }


@app.delete("/api/databases/{connection_id}")
async def delete_database(
    connection_id: str,
    db: Session = Depends(get_db),
    user_id: str = "user1"
):
    manager = DatabaseManager(db)
    result = manager.delete_connection(connection_id, user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ============= QUERY ENDPOINTS =============

@app.post("/api/query", response_model=QueryResponse)
@limiter.limit("10/minute")  # max 10 queries per minute per IP
async def execute_query(
    request: Request,           # ← slowapi requires this exact name
    query_req: QueryRequest,
    db: Session = Depends(get_db)
):
    # ── Security validation ────────────────────────────────────────────────
    check = validate_query(query_req.query)
    if not check["safe"]:
        raise HTTPException(
            status_code=400,
            detail=f"Query blocked: {check['reason']}"
        )

    if not query_req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(query_req.query) > 500:
        raise HTTPException(status_code=400, detail="Query too long")

    manager = DatabaseManager(db)

    # User-scoped lookup: a user can only query their own active connections.
    try:
        conn_model = manager.get_connection(query_req.connection_id, query_req.user_id)
        connection_string = manager.build_connection_string(conn_model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    response = query_database(
        connection_string=connection_string,
        question=query_req.query,
        expected_db_name=conn_model.database,
        db_type=conn_model.db_type,
        connection_id=conn_model.id
    )

    query_log = QueryLog(
        id=str(uuid.uuid4()),
        user_id=query_req.user_id,
        db_connection_id=conn_model.id,
        query_text=query_req.query,
        success=response["success"],
        result=response.get("result", response.get("error", "Unknown error"))
    )
    db.add(query_log)
    db.commit()

    return QueryResponse(
        success=response["success"],
        result=response.get("result", response.get("error", "Unknown error")),
        query=query_req.query,
        timestamp=response.get("timestamp", datetime.now().isoformat()),
        executed_sql=response.get("executed_sql"),
        database_name=response.get("database_name") or conn_model.database,
        database_id=conn_model.id,
        row_count=response.get("row_count"),
        columns=response.get("columns"),
        rows=response.get("rows")
    )


@app.get("/api/query-history")
async def get_query_history(
    db: Session = Depends(get_db),
    user_id: str = "user1",
    limit: int = 20
):
    logs = db.query(QueryLog).filter(
        QueryLog.user_id == user_id
    ).order_by(QueryLog.executed_at.desc()).limit(limit).all()

    connections = db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user_id
    ).all()
    conn_map = {c.id: f"{c.db_name} ({c.database})" for c in connections}

    return {
        "user_id": user_id,
        "total_queries": len(logs),
        "history": [
            {
                "query": log.query_text,
                "success": log.success,
                "timestamp": log.executed_at.isoformat(),
                "database_id": log.db_connection_id,
                "database_name": conn_map.get(log.db_connection_id, "Connected Database")
            }
            for log in logs
        ]
    }


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Multi-Database AI Agent backend...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)