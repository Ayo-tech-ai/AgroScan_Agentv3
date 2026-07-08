"""
database.py

Pure data-layer setup for AgroScan's farm record book.

This is the ONLY file that would need to change if the storage
backend ever moves away from local SQLite (e.g. to a hosted
Postgres/Turso database for true persistence across redeploys —
"Path B" from our deployment discussion).
"""

import sqlite3
import pandas as pd


DATABASE_NAME = "agroscan.db"
EXCEL_FILE = "agroscan_farm_records_july2025_june2026.xlsx"


def create_farm_records_table():
    """
    Creates the farm_records table if it doesn't already exist.
    Idempotent — safe to call on every app cold start.
    """
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farm_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_date DATE UNIQUE NOT NULL,
        bird_count INTEGER NOT NULL,
        crates_collected INTEGER NOT NULL,
        feed_consumed_kg REAL NOT NULL,
        revenue REAL NOT NULL,
        expenses REAL NOT NULL,
        notes TEXT
    );
    """)
    connection.commit()
    connection.close()


def initialize_farm_record_book(excel_path):
    """
    Imports historical records from an Excel file into the
    farm_records table. Duplicate dates (already-existing
    record_date values) are silently skipped, not overwritten.

    Returns (imported_count, skipped_count).
    """
    df = pd.read_excel(excel_path)
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    imported = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            cursor.execute("""
            INSERT INTO farm_records (
                record_date, bird_count, crates_collected,
                feed_consumed_kg, revenue, expenses, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row["record_date"]),
                int(row["bird_count"]),
                int(row["crates_collected"]),
                float(row["feed_consumed_kg"]),
                float(row["revenue"]),
                float(row["expenses"]),
                row["notes"] if pd.notna(row["notes"]) else None
            ))
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1

    connection.commit()
    connection.close()
    return imported, skipped


def get_record_count():
    """Returns the total number of records currently in the table."""
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM farm_records")
    count = cursor.fetchone()[0]
    connection.close()
    return count
