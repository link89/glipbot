import os
import logging

from sqlalchemy.engine.url import URL

logging.basicConfig(level=logging.INFO)

PORT = int(os.environ.get("PORT", 8888))
DEBUG_MODE = os.environ.get("MODE", "PROD") == "DEBUG"

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME", "device_lab")

DB_URL = URL(
    drivername="mysql+pymysql",
    host=DB_HOST,
    username=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
)


TORNADO_SETTINGS = {
    "debug": DEBUG_MODE,
}
