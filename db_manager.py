import os
import uuid
import urllib.parse
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from models import DatabaseConnection
from typing import Dict, List


class DatabaseManager:
    """Manage multiple database connections with deduplication and verification."""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.connections_cache = {}

    def build_connection_string(self, conn: DatabaseConnection) -> str:
        """Convert stored credentials to a valid SQLAlchemy connection string."""
        db_type = (conn.db_type or "").lower()
        encoded_username = urllib.parse.quote_plus(conn.username or "")
        encoded_password = urllib.parse.quote_plus(conn.password or "")

        
        if db_type == "mysql":
            port = conn.port if conn.port else 3306
            return (
                f"mysql+pymysql://{encoded_username}:{encoded_password}"
                f"@{conn.host}:{port}/{conn.database}"
            )

        elif db_type == "postgresql":
            port = conn.port if conn.port else 5432
            return (
                f"postgresql+psycopg2://{encoded_username}:{encoded_password}"
                f"@{conn.host}:{port}/{conn.database}?sslmode=require"
            )

return (
    f"postgresql+psycopg2://{encoded_username}:{encoded_password}"
    f"@{conn.host}:{port}/{conn.database}?sslmode=require"
)
        elif db_type == "postgresql":
            port = conn.port if conn.port else 5432
            return f"postgresql://{encoded_username}:{encoded_password}@{conn.host}:{port}/{conn.database}"

        elif db_type == "mssql":
            port = conn.port if conn.port else 1433
            return f"mssql+pyodbc://{encoded_username}:{encoded_password}@{conn.host}:{port}/{conn.database}?driver=ODBC+Driver+17+for+SQL+Server"

        elif db_type == "sqlite":
            db_path = conn.database
            if db_path.startswith("sqlite:"):
                return db_path
            if not os.path.isabs(db_path):
                db_path = os.path.abspath(db_path)
            return f"sqlite:///{db_path}"

        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def add_database(self, user_id: str, db_name: str, db_type: str,
                     host: str, port: int, username: str, password: str,
                     database: str) -> Dict:
        """
        Test and add/update database connection for user.
        Prevents duplicate entries by updating existing matching connections.
        """
        try:
            # Clean inputs
            clean_db_type = (db_type or "").strip().lower()
            clean_host = (host or "localhost").strip()
            clean_database = (database or "").strip()
            clean_port = int(port) if port else (3306 if clean_db_type == "mysql" else 0)

            # Test connection first
            test_conn = DatabaseConnection(
                user_id=user_id,
                db_name=db_name,
                db_type=clean_db_type,
                host=clean_host,
                port=clean_port,
                username=username,
                password=password,
                database=clean_database
            )

            connection_string = self.build_connection_string(test_conn)

            if clean_db_type == "sqlite":
                engine = create_engine(connection_string, connect_args={"check_same_thread": False}, echo=False)
            else:
                engine = create_engine(connection_string, echo=False, pool_pre_ping=True)

            # Test the connection & verify active database
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                if clean_db_type == "mysql":
                    active_db = conn.execute(text("SELECT DATABASE()")).scalar()
                    if active_db and active_db.lower() != clean_database.lower():
                        engine.dispose()
                        return {
                            "success": False,
                            "message": f"Connection verified but connected to '{active_db}' instead of requested '{clean_database}'"
                        }
            engine.dispose()

            # Check if this database connection already exists for user (deduplication)
            existing_conn = self.db_session.query(DatabaseConnection).filter(
                DatabaseConnection.user_id == user_id,
                DatabaseConnection.db_type == clean_db_type,
                DatabaseConnection.host == clean_host,
                DatabaseConnection.port == clean_port,
                DatabaseConnection.database == clean_database
            ).first()

            if existing_conn:
                existing_conn.db_name = db_name
                existing_conn.username = username
                existing_conn.password = password
                existing_conn.is_active = True
                self.db_session.commit()
                return {
                    "success": True,
                    "message": f"Database '{db_name}' updated and connected successfully",
                    "connection_id": existing_conn.id
                }

            # If new connection, save as new row.
            # FIX: models.py has no default for `id`, so it must be set here.
            new_conn = DatabaseConnection(
                id=str(uuid.uuid4()),
                user_id=user_id,
                db_name=db_name,
                db_type=clean_db_type,
                host=clean_host,
                port=clean_port,
                username=username,
                password=password,
                database=clean_database,
                is_active=True
            )

            self.db_session.add(new_conn)
            self.db_session.commit()

            return {
                "success": True,
                "message": f"Database '{db_name}' connected successfully",
                "connection_id": new_conn.id
            }

        except Exception as e:
            self.db_session.rollback()
            safe_msg = str(e)
            if password:
                # Redact both the raw and the URL-encoded password.
                safe_msg = safe_msg.replace(password, "******")
                safe_msg = safe_msg.replace(urllib.parse.quote_plus(password), "******")
            return {
                "success": False,
                "message": f"Connection failed: {safe_msg}"
            }

    def get_user_databases(self, user_id: str) -> List[Dict]:
        """Get all active databases connected by user with unique configurations."""
        connections = self.db_session.query(DatabaseConnection).filter(
            DatabaseConnection.user_id == user_id,
            DatabaseConnection.is_active == True
        ).order_by(DatabaseConnection.created_at.asc()).all()

        # Deduplicate in memory by (db_type, host, port, database) in case legacy duplicates exist
        seen = set()
        unique_list = []
        for conn in connections:
            key = (conn.db_type.lower(), conn.host.lower(), conn.port, conn.database.lower())
            if key in seen:
                continue
            seen.add(key)
            unique_list.append({
                "id": conn.id,
                "name": conn.db_name,
                "type": conn.db_type,
                "host": conn.host,
                "port": conn.port,
                "database": conn.database,
                "username": conn.username,
                "created_at": conn.created_at.isoformat() if conn.created_at else ""
            })

        return unique_list

    def get_connection(self, connection_id: str, user_id: str) -> DatabaseConnection:
        """
        Retrieve the DatabaseConnection for a specific ID.
        Scoped to the owning user and active connections only, so one user
        can never query another user's database.
        """
        conn = self.db_session.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == user_id,
            DatabaseConnection.is_active == True
        ).first()

        if not conn:
            raise ValueError(f"Connection {connection_id} not found")

        return conn

    def get_connection_string(self, connection_id: str, user_id: str) -> str:
        """Get connection string for a specific database ID (user-scoped)."""
        conn = self.get_connection(connection_id, user_id)
        return self.build_connection_string(conn)

    def delete_connection(self, connection_id: str, user_id: str) -> Dict:
        """Delete / deactivate a database connection."""
        conn = self.db_session.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == user_id
        ).first()

        if not conn:
            return {"success": False, "message": "Connection not found"}

        conn.is_active = False
        self.db_session.commit()

        return {"success": True, "message": "Connection deleted"}
