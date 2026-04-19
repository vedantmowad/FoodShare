import os
import mysql.connector
from urllib.parse import urlparse

def get_connection():

    db_url = os.getenv("DATABASE_URL")

    # If using Railway URL format
    if db_url:
        url = urlparse(db_url)

        return mysql.connector.connect(
            host=url.hostname,
            user=url.username,
            password=url.password,
            database=url.path.lstrip("/"),
            port=url.port or 3306
        )

    # fallback (manual env vars)
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        port=int(os.getenv("MYSQL_PORT", 3306))
    )
