"""Database engine, session factory, and declarative base.

Uses a file-backed SQLite database with foreign-key enforcement enabled
on every connection.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./event_platform.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    """Enable SQLite foreign-key constraints on each new connection.

    SQLite only enforces foreign keys when the ``foreign_keys`` pragma is
    set on the connection; SQLAlchemy does not enable it by default.

    Args:
        dbapi_connection: Raw DBAPI connection being opened.
        connection_record: SQLAlchemy connection record for the pool.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Yield a database session and always close it afterwards.

    Intended for use as a FastAPI dependency.

    Yields:
        Session: SQLAlchemy session scoped to a single request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
