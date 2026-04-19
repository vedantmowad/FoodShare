import mysql.connector
import os
from urllib.parse import urlparse

db_url = urlparse(os.getenv("DATABASE_URL"))

conn = mysql.connector.connect(
    host=db_url.hostname,
    user=db_url.username,
    password=db_url.password,
    database=db_url.path.lstrip("/"),
    port=db_url.port
)