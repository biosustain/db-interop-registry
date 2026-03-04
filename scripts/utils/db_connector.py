"""Database connection utilities supporting both Azure and local PostgreSQL."""

import logging
import os
import time
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def get_azure_password():
    """Get database password from Azure Key Vault."""
    keyvault_name = os.getenv("KEYVAULT_NAME")
    secret_name = os.getenv("KEYVAULT_SECRET_NAME")

    keyvault_url = f"https://{keyvault_name}.vault.azure.net/"
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=keyvault_url, credential=credential)

    secret = secret_client.get_secret(secret_name)
    return secret.value


def get_azure_session():
    """Get SQLAlchemy session connected to Azure PostgreSQL."""
    password = get_azure_password()

    host = os.getenv("DB_HOST")
    database = os.getenv("DB_NAME")
    username = os.getenv("DB_USERNAME")

    connection_string = f"postgresql://{username}:{password}@{host}/{database}?sslmode=require"
    logger.info(f"Connecting to Azure PostgreSQL: {host}/{database}")

    engine = create_engine(connection_string, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)

    return Session()


def get_local_session():
    """Get SQLAlchemy session connected to local PostgreSQL."""
    host = os.getenv("LOCAL_DB_HOST", "localhost")
    port = os.getenv("LOCAL_DB_PORT", "5432")
    database = os.getenv("LOCAL_DB_NAME", "interopdb")
    username = os.getenv("LOCAL_DB_USERNAME", "app_user")
    password = os.getenv("LOCAL_DB_PASSWORD", "app_password")

    # Add a short connect timeout to fail fast if DB is unreachable
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}?connect_timeout=5"
    print(connection_string)
    logger.info(f"Connecting to local PostgreSQL: {host}:{port}/{database}")

    # pre_ping guards against stale connections; force an initial connect to surface errors early
    engine = create_engine(connection_string, pool_pre_ping=True)
    with engine.connect() as _:
        pass
    Session = sessionmaker(bind=engine)

    return Session()


def get_session():
    """Get database session based on CONNECTION_MODE environment variable."""
    mode = os.getenv("CONNECTION_MODE", "azure").lower()

    if mode == "local":
        return get_local_session()
    elif mode == "azure":
        return get_azure_session()
    else:
        raise ValueError(f"Invalid CONNECTION_MODE: {mode}. Use 'local' or 'azure'")


def execute_with_retry(session, stmt, max_retries=3):
    """Execute a statement and commit, retrying on transient connection errors (e.g. SSL drop)."""
    for attempt in range(1, max_retries + 1):
        try:
            session.execute(stmt)
            session.commit()
            return
        except OperationalError as e:
            session.rollback()
            session.close()
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            print(f"  Connection error (attempt {attempt}/{max_retries}): {e}. Retrying in {wait}s...")
            time.sleep(wait)


def commit_with_retry(session, max_retries=3):
    """Commit pending changes, retrying on transient connection errors (e.g. SSL drop)."""
    for attempt in range(1, max_retries + 1):
        try:
            session.commit()
            return
        except OperationalError as e:
            session.rollback()
            session.close()
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            print(f"  Connection error (attempt {attempt}/{max_retries}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
