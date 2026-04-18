import os
from contextlib import closing

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    database_url = os.getenv("DATABASE_URL", "").strip()
    return database_url.replace("/latex_genarator", "/latex_generator")


def init_db():
    database_url = get_database_url()
    if not database_url:
        return

    with closing(psycopg2.connect(database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS latex_history (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    extracted_text TEXT,
                    latex_output TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        connection.commit()


def save_history(filename, image_path, extracted_text, latex_output):
    database_url = get_database_url()
    if not database_url:
        return

    with closing(psycopg2.connect(database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO latex_history (filename, image_path, extracted_text, latex_output)
                VALUES (%s, %s, %s, %s)
                """,
                (filename, image_path, extracted_text, latex_output),
            )
        connection.commit()
