
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    config = {
        "host": os.getenv("DB_HOST"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "port": int(os.getenv("DB_PORT", "3306"))
    }

    ca_file = os.getenv("DB_SSL_CA")

    if ca_file:
        if not os.path.isabs(ca_file):
            ca_file = os.path.join(os.path.dirname(__file__), ca_file)

        config["ssl_ca"] = ca_file
        config["ssl_verify_cert"] = True
        config["ssl_verify_identity"] = True

    return mysql.connector.connect(**config)
