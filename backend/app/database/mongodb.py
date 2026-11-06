import logging

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import Settings

logger = logging.getLogger(__name__)

_client: MongoClient | None = None
_database: Database | None = None


def connect_to_mongodb(settings: Settings) -> bool:
    global _client, _database

    close_mongodb_connection()
    try:
        client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
        )
        client.admin.command("ping")
        _client = client
        _database = client[settings.database_name]
        _database["users"].create_index("email", unique=True)
        logger.info("Connected to MongoDB database '%s'", settings.database_name)
        return True
    except PyMongoError:
        logger.exception("Could not connect to MongoDB; continuing without database access")
        if "client" in locals():
            client.close()
        return False


def get_database() -> Database | None:
    return _database


def is_mongodb_available() -> bool:
    if _client is None:
        return False
    try:
        _client.admin.command("ping")
        return True
    except PyMongoError:
        logger.warning("MongoDB health check failed")
        return False


def close_mongodb_connection() -> None:
    global _client, _database

    if _client is not None:
        _client.close()
    _client = None
    _database = None
