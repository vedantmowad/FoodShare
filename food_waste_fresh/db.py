import os
from urllib.parse import urlparse
from flask_mysqldb import MySQL

mysql = MySQL()

def init_db(app):
    app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST")
    app.config['MYSQL_USER'] = os.getenv("MYSQL_USER")
    app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")

    db_url = os.getenv("DATABASE_URL")

    if db_url:
        parsed = urlparse(db_url)

        app.config['MYSQL_HOST'] = parsed.hostname
        app.config['MYSQL_USER'] = parsed.username
        app.config['MYSQL_PASSWORD'] = parsed.password
        app.config['MYSQL_DB'] = parsed.path.lstrip("/")
        app.config['MYSQL_PORT'] = parsed.port or 3306

    mysql.init_app(app)
