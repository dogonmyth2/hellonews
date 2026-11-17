"""
query_postgres.py
Queries the local PostgreSQL database and displays the contents of tables.
"""

import json
import os
import sys
from pathlib import Path
import psycopg2
from psycopg2 import extras
from tabulate import tabulate

CONFIG_FILE = Path(__file__).resolve().parent / "dbconfig.json"


def load_config():
    """Load database parameters from dbconfig.json if available."""
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not parse {CONFIG_FILE.name}: {e}")
    return config


def get_db_connection():
    """Establish and return a connection to the PostgreSQL database."""
    file_cfg = load_config()

    host = os.getenv("PGHOST", file_cfg.get("host", "localhost"))
    port = int(os.getenv("PGPORT", file_cfg.get("port", 5432)))
    database = os.getenv("PGDATABASE", file_cfg.get("database", "postgres"))
    user = os.getenv("PGUSER", file_cfg.get("user", "postgres"))
    password = os.getenv("PGPASSWORD", file_cfg.get("password", "password12"))

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password,
        )
        return conn
    except psycopg2.OperationalError as err:
        print(f"[ERROR] Could not connect to PostgreSQL on {host}:{port}/{database}:")
        print(f"        {err}")
        sys.exit(1)


def display_table(conn, table_name="newtesttable", schema="public"):
    """Query and display all rows from a specified table."""
    full_table_name = f'"{schema}"."{table_name}"'
    query = f"SELECT * FROM {full_table_name} ORDER BY id ASC;"

    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        try:
            cur.execute(query)
            rows = cur.fetchall()
        except psycopg2.Error as err:
            print(f"[ERROR] Failed to query {full_table_name}: {err}")
            return

        if not rows:
            print(f"No records found in table {full_table_name}.")
            return

        headers = list(rows[0].keys())
        table_data = [list(row.values()) for row in rows]

        print(f"\n=== Content of {full_table_name} ({len(rows)} rows) ===\n")
        print(tabulate(table_data, headers=headers, tablefmt="github"))
        print("\n" + "=" * 50)


def list_tables(conn):
    """List all user tables in the database."""
    query = """
        SELECT schemaname, tablename, tableowner
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schemaname, tablename;
    """
    with conn.cursor() as cur:
        cur.execute(query)
        tables = cur.fetchall()

    if tables:
        print("\n=== User Tables in Database ===")
        print(tabulate(tables, headers=["Schema", "Table Name", "Owner"], tablefmt="github"))
    else:
        print("No user tables found.")


def main():
    conn = get_db_connection()
    try:
        # Display list of available user tables
        list_tables(conn)

        # Display rows from 'newtesttable'
        display_table(conn, table_name="newtesttable", schema="public")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
