
import os
import uuid
import urllib.parse
from typing import Dict, List

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from models import DatabaseConnection


class DatabaseManager:
    """Manage multiple database connections with deduplication and verification."""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.connections_cache = {}

    def build_connection_string(self, conn: DatabaseConnection) -> str:
        """Convert stored credentials to a valid SQLAlchemy connection string."""

        db_type = (conn.db_type or "").strip().lower()
        encoded_username = urllib.parse.quote_plus(conn.username or "")
        encoded_password = urllib.parse.quote_plus(conn.password or "")

        if db_type == "mysql":
            port = conn.port or 3306
            return (
                f"mysql+pymysql://{encoded_username}:{encoded_password}"
                f"@{conn.host}:{port}/{conn.database}"
            )

        elif db_type == "postgresql":
            port = conn.port or 5432
            return (
                f"postgresql+psycopg2://{encoded_username}:{encoded_password}"
                f"@{conn.host}:{port}/{conn.database}?sslmode=require"
            )

        elif db_type == "mssql":
            port = conn.port or 1433
            return (
                f"mssql+pyodbc://{encoded_username}:{encoded_password}"
                f"@{conn.host}:{port}/{conn.database}"
                "?driver=ODBC+Driver+17+for+SQL+Server"
            )

        elif db_type == "sqlite":
            db_path = conn.database

            if db_path.startswith("sqlite:"):
                return db_path

            if not os.path.isabs(db_path):
                db_path = os.path.abspath(db_path)

            return f"sqlite:///{db_path}"

        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def add_database(
        self,
        user_id: str,
        db_name: str,
        db_type: str,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
    ) -> Dict:
        """Test and add or update a database connection."""

        engine = None

        try:
            clean_db_type = (db_type or "").strip().lower()
            clean_host = (host or "localhost").strip()
            clean_database = (database or "").strip()

            default_ports = {
                "mysql": 3306,
                "postgresql": 5432,
                "mssql": 1433,
                "sqlite": 0,
            }

            clean_port = (
                int(port)
                if port
                else default_ports.get(clean_db_type, 0)
            )

            if not clean_database:
                return {
                    "success": False,
                    "message": "Database name is required.",
                }

            test_conn = DatabaseConnection(
                user_id=user_id,
                db_name=db_name,
                db_type=clean_db_type,
                host=clean_host,
                port=clean_port,
                username=username,
                password=password,
                database=clean_database,
            )

            connection_string = self.build_connection_string(test_conn)

            if clean_db_type == "sqlite":
                engine = create_engine(
                    connection_string,
                    connect_args={"check_same_thread": False},
                    echo=False,
                )
            else:
                engine = create_engine(
                    connection_string,
                    echo=False,
                    pool_pre_ping=True,
                )

            # Verify that the database connection works.
            with engine.connect() as db_connection:
                db_connection.execute(text("SELECT 1"))

                # Verify the selected database for MySQL.
                if clean_db_type == "mysql":
                    active_db = db_connection.execute(
                        text("SELECT DATABASE()")
                    ).scalar()

                    if (
                        active_db
                        and active_db.lower() != clean_database.lower()
                    ):
                        return {
                            "success": False,
                            "message": (
                                f"Connected to '{active_db}' instead of "
                                f"'{clean_database}'."
                            ),
                        }

            engine.dispose()
            engine = None

            # Find an existing matching connection for this user.
            existing_conn = (
                self.db_session.query(DatabaseConnection)
                .filter(
                    DatabaseConnection.user_id == user_id,
                    DatabaseConnection.db_type == clean_db_type,
                    DatabaseConnection.host == clean_host,
                    DatabaseConnection.port == clean_port,
                    DatabaseConnection.database == clean_database,
                )
                .first()
            )

            if existing_conn:
                existing_conn.db_name = db_name
                existing_conn.username = username
                existing_conn.password = password
                existing_conn.is_active = True

                self.db_session.commit()

                return {
                    "success": True,
                    "message": (
                        f"Database '{db_name}' updated and connected "
                        "successfully."
                    ),
                    "connection_id": existing_conn.id,
                }

            # Create a new connection record.
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
                is_active=True,
            )

            self.db_session.add(new_conn)
            self.db_session.commit()

            return {
                "success": True,
                "message": f"Database '{db_name}' connected successfully.",
                "connection_id": new_conn.id,
            }

        except Exception as e:
            self.db_session.rollback()

            safe_msg = str(e)

            if password:
                safe_msg = safe_msg.replace(password, "******")
                encoded_password = urllib.parse.quote_plus(password)
                safe_msg = safe_msg.replace(encoded_password, "******")

            return {
                "success": False,
                "message": f"Connection failed: {safe_msg}",
            }

        finally:
            if engine is not None:
                engine.dispose()

    def get_user_databases(self, user_id: str) -> List[Dict]:
        """Return active database connections without duplicate entries."""

        connections = (
            self.db_session.query(DatabaseConnection)
            .filter(
                DatabaseConnection.user_id == user_id,
                DatabaseConnection.is_active == True,
            )
            .order_by(DatabaseConnection.created_at.asc())
            .all()
        )

        seen = set()
        unique_list = []

        for conn in connections:
            key = (
                (conn.db_type or "").lower(),
                (conn.host or "").lower(),
                conn.port,
                (conn.database or "").lower(),
            )

            if key in seen:
                continue

            seen.add(key)

            unique_list.append(
                {
                    "id": conn.id,
                    "name": conn.db_name,
                    "type": conn.db_type,
                    "host": conn.host,
                    "port": conn.port,
                    "database": conn.database,
                    "username": conn.username,
                    "created_at": (
                        conn.created_at.isoformat()
                        if conn.created_at
                        else ""
                    ),
                }
            )

        return unique_list

    def get_connection(
        self,
        connection_id: str,
        user_id: str,
    ) -> DatabaseConnection:
        """Retrieve an active connection owned by the specified user."""

        conn = (
            self.db_session.query(DatabaseConnection)
            .filter(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == user_id,
                DatabaseConnection.is_active == True,
            )
            .first()
        )

        if not conn:
            raise ValueError(
                f"Connection {connection_id} not found."
            )

        return conn

    def get_connection_string(
        self,
        connection_id: str,
        user_id: str,
    ) -> str:
        """Return the connection string for a user's database."""

        conn = self.get_connection(connection_id, user_id)
        return self.build_connection_string(conn)

    def delete_connection(
        self,
        connection_id: str,
        user_id: str,
    ) -> Dict:
        """Deactivate a database connection owned by the specified user."""

        conn = (
            self.db_session.query(DatabaseConnection)
            .filter(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == user_id,
            )
            .first()
        )

        if not conn:
            return {
                "success": False,
                "message": "Connection not found.",
            }

        conn.is_active = False
        self.db_session.commit()

        return {
            "success": True,
            "message": "Connection deleted successfully.",
        }
