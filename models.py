from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class DatabaseConnection(Base):
    """Store user's database connections"""
    __tablename__ = "database_connections"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True)
    db_name = Column(String)  # "College DB", "Office DB", etc.
    db_type = Column(String)  # "mysql", "postgresql", "mssql"
    host = Column(String)
    port = Column(Integer)
    username = Column(String)
    password = Column(String)  # TODO: Encrypt this!
    database = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class QueryLog(Base):
    """Audit trail of all queries"""
    __tablename__ = "query_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True)
    db_connection_id = Column(String)
    query_text = Column(Text)
    success = Column(Boolean)
    result = Column(Text)
    executed_at = Column(DateTime, default=datetime.utcnow)