"""
service.py

FarmRecordService centralizes all business logic and database
interaction for the farm record book: inheritance rules for
partial updates, revenue calculation, validation, and lookups.

This is the file to touch if business rules change — e.g. the
known soft spot around partial date-range coverage reporting,
or a future addition like mortality tracking.
"""

import sqlite3
from datetime import date

from .database import DATABASE_NAME


class FarmRecordService:

    CRATE_PRICE = 3500

    def __init__(self, database_name=DATABASE_NAME):
        self.database_name = database_name

    def get_connection(self):
        return sqlite3.connect(self.database_name)

    def get_total_records(self):
        connection = self.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM farm_records")
        total = cursor.fetchone()[0]
        connection.close()
        return total

    def record_exists(self, record_date):
        connection = self.get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM farm_records WHERE record_date=?",
            (record_date,)
        )
        exists = cursor.fetchone()[0] > 0
        connection.close()
        return exists

    def get_record_by_date(self, record_date):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM farm_records WHERE record_date=?",
            (record_date,)
        )
        row = cursor.fetchone()
        connection.close()
        return dict(row) if row else None

    def get_previous_record(self, record_date):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT * FROM farm_records
            WHERE record_date < ?
            ORDER BY record_date DESC
            LIMIT 1
            """,
            (record_date,)
        )
        row = cursor.fetchone()
        connection.close()
        return dict(row) if row else None

    def get_most_recent_record(self):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT * FROM farm_records
            ORDER BY record_date DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        connection.close()
        return dict(row) if row else None

    def get_summary(self, start_date, end_date):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS days_recorded,
                COALESCE(SUM(crates_collected), 0) AS total_crates,
                COALESCE(SUM(feed_consumed_kg), 0) AS total_feed_kg,
                COALESCE(SUM(revenue), 0) AS total_revenue,
                COALESCE(SUM(expenses), 0) AS total_expenses
            FROM farm_records
            WHERE record_date BETWEEN ? AND ?
            """,
            (start_date, end_date)
        )
        row = cursor.fetchone()
        connection.close()

        result = dict(row)
        result["net_profit"] = result["total_revenue"] - result["total_expenses"]
        result["start_date"] = start_date
        result["end_date"] = end_date
        return result

    def get_all_records(self):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM farm_records ORDER BY record_date")
        rows = cursor.fetchall()
        connection.close()
        return [dict(row) for row in rows]

    def validate_daily_record(self, bird_count, crates_collected):
        eggs = crates_collected * 30
        maximum_eggs = bird_count * 0.95
        if eggs > maximum_eggs:
            return (
                False,
                f"{crates_collected} crates ({eggs} eggs) appears "
                f"unrealistic for {bird_count} birds."
            )
        return True, "Validation passed."

    def record_daily_farm_data(
        self, crates_collected=None, bird_count=None,
        feed_consumed_kg=None, expenses=None,
        notes=None, record_date=None
    ):
        """
        Records or updates one day's farm data.

        Business Rules:
        - Today's date is used if record_date is omitted.
        - Missing fields inherit from TODAY'S OWN existing record
          first (if one exists), otherwise from the most recent
          prior record. This prevents same-day updates from
          silently reverting to an earlier day's values.
        - crates_collected is NOT required for an update (removed
          per deliberate decision) — it also inherits like any
          other field.
        - Revenue is calculated automatically.
        - Returns 'previous_values' so callers can report exactly
          what changed on an update.
        """
        if record_date is None:
            record_date = date.today().isoformat()

        existing_record = self.get_record_by_date(record_date)
        previous_day_record = self.get_previous_record(record_date)

        reference_record = existing_record or previous_day_record

        if reference_record:
            if crates_collected is None:
                crates_collected = reference_record["crates_collected"]
            if bird_count is None:
                bird_count = reference_record["bird_count"]
            if feed_consumed_kg is None:
                feed_consumed_kg = reference_record["feed_consumed_kg"]
            if expenses is None:
                expenses = reference_record["expenses"]
            if notes is None:
                notes = reference_record["notes"]
        else:
            if crates_collected is None:
                raise ValueError("crates_collected is required for the first record.")
            if bird_count is None:
                raise ValueError("bird_count is required for the first record.")
            if feed_consumed_kg is None:
                raise ValueError("feed_consumed_kg is required for the first record.")
            if expenses is None:
                raise ValueError("expenses is required for the first record.")

        revenue = crates_collected * self.CRATE_PRICE

        valid, message = self.validate_daily_record(bird_count, crates_collected)
        if not valid:
            return {"success": False, "message": message}

        connection = self.get_connection()
        cursor = connection.cursor()

        if existing_record:
            cursor.execute(
                """
                UPDATE farm_records
                SET bird_count=?, crates_collected=?, feed_consumed_kg=?,
                    revenue=?, expenses=?, notes=?
                WHERE record_date=?
                """,
                (bird_count, crates_collected, feed_consumed_kg,
                 revenue, expenses, notes, record_date)
            )
            action = "updated"
        else:
            cursor.execute(
                """
                INSERT INTO farm_records(
                    record_date, bird_count, crates_collected,
                    feed_consumed_kg, revenue, expenses, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_date, bird_count, crates_collected,
                 feed_consumed_kg, revenue, expenses, notes)
            )
            action = "recorded"

        connection.commit()
        connection.close()

        return {
            "success": True,
            "action": action,
            "record_date": record_date,
            "previous_values": existing_record,
            "bird_count": bird_count,
            "crates_collected": crates_collected,
            "feed_consumed_kg": feed_consumed_kg,
            "revenue": revenue,
            "expenses": expenses,
            "notes": notes,
            "message": f"Farm record successfully {action}."
        }
