import pytest
from sqlalchemy import MetaData, text
from sqlalchemy.orm import scoped_session, sessionmaker

from backend import create_app
from backend import db as _db


@pytest.fixture(scope="session")
def app(request):
    """Session-wide test `Flask` application."""
    _app = create_app({"WTF_CSRF_ENABLED": False})

    # Establish an application context before running the tests.
    ctx = _app.app_context()
    ctx.push()

    def teardown():
        ctx.pop()

    request.addfinalizer(teardown)
    return _app


@pytest.fixture(scope="session")
def db(app, request):
    """Session-wide test database."""

    def teardown():
        # Drop using reflected metadata to honor real FK dependencies.
        engine = _db.engine
        with engine.begin() as conn:
            meta = MetaData()
            meta.reflect(bind=conn)
            try:
                if meta.tables:
                    meta.drop_all(bind=conn)
                else:
                    # Fallback: reset schema if nothing reflected (defensive)
                    conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                    conn.execute(text("CREATE SCHEMA public"))
            except Exception:
                # Last-resort fallback to ensure clean teardown
                conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))

    _db.app = app
    # Ensure a clean schema before creating tables for tests
    engine = _db.engine
    with engine.begin() as conn:
        meta = MetaData()
        meta.reflect(bind=conn)
        if meta.tables:
            meta.drop_all(bind=conn)
        else:
            # Reset schema if nothing reflected (handles prior failed runs)
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

    _db.create_all()

    request.addfinalizer(teardown)
    return _db


@pytest.fixture(scope="function")
def session(db, request):
    """Creates a new database session for a test."""
    connection = db.engine.connect()
    transaction = connection.begin()

    db.session = scoped_session(session_factory=sessionmaker(bind=connection))

    def teardown():
        transaction.rollback()
        connection.close()
        db.session.remove()

    request.addfinalizer(teardown)
    return db.session


@pytest.fixture()
def client(app):
    """Functional test client for route testing."""
    return app.test_client()
