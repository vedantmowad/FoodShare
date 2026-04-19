import mysql.connector
import os
from urllib.parse import urlparse

def get_connection():
    db_url = urlparse(os.getenv("DATABASE_URL"))

    return mysql.connector.connect(
        host=db_url.hostname,
        user=db_url.username,
        password=db_url.password,
        database=db_url.path.lstrip("/"),
        port=db_url.port
    )
