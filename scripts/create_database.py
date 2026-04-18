import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

load_dotenv()


def main():
    database_url = os.getenv("DATABASE_URL", "").strip()
    database_url = database_url.replace("/latex_genarator", "/latex_generator")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing in .env")

    maintenance_url = database_url.rsplit("/", 1)[0] + "/postgres"
    database_name = database_url.rsplit("/", 1)[1].split("?", 1)[0]

    connection = psycopg2.connect(maintenance_url)
    connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
        exists = cursor.fetchone()
        if exists:
            print(f"Database already exists: {database_name}")
        else:
            cursor.execute(f'CREATE DATABASE "{database_name}"')
            print(f"Created database: {database_name}")

    connection.close()


if __name__ == "__main__":
    main()
