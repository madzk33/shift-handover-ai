"""SQLite storage layer for persisting handover documents and raw inputs."""

import json
import sqlite3
from datetime import datetime, timezone

from schema import Handover

DEFAULT_DB_PATH = "handovers.db"


def _get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create a connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Create the handovers and raw_inputs tables if they don't exist.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = _get_connection(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS handovers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                shift_date TEXT NOT NULL,
                shift_type TEXT NOT NULL,
                operative TEXT NOT NULL,
                line_or_area TEXT NOT NULL,
                structured_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS raw_inputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                handover_id INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                transcript_source TEXT NOT NULL CHECK (transcript_source IN ('typed', 'voice')),
                FOREIGN KEY (handover_id) REFERENCES handovers(id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_handover(
    handover: Handover,
    raw_text: str,
    source: str,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Persist a structured handover and its raw input.

    Args:
        handover: Validated Handover instance.
        raw_text: The original raw text (typed or transcribed).
        source: Either 'typed' or 'voice'.
        db_path: Path to the SQLite database file.

    Returns:
        The auto-generated handover ID.
    """
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO handovers (created_at, shift_date, shift_type, operative, line_or_area, structured_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                handover.shift_date,
                handover.shift_type,
                handover.operative,
                handover.line_or_area,
                handover.model_dump_json(),
            ),
        )
        handover_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO raw_inputs (handover_id, raw_text, transcript_source)
            VALUES (?, ?, ?)
            """,
            (handover_id, raw_text, source),
        )
        conn.commit()
        return handover_id
    finally:
        conn.close()


def get_recent_handovers(
    limit: int = 10,
    db_path: str = DEFAULT_DB_PATH,
) -> list[dict]:
    """Fetch the most recent handovers, newest first.

    Args:
        limit: Maximum number of records to return.
        db_path: Path to the SQLite database file.

    Returns:
        List of dicts, each with row columns plus parsed structured_json.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, created_at, shift_date, shift_type, operative, line_or_area, structured_json
            FROM handovers
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        results = []
        for row in rows:
            record = dict(row)
            record["structured"] = json.loads(record.pop("structured_json"))
            results.append(record)
        return results
    finally:
        conn.close()


def get_handover_by_id(
    handover_id: int,
    db_path: str = DEFAULT_DB_PATH,
) -> dict | None:
    """Fetch a single handover by its ID.

    Args:
        handover_id: The handover primary key.
        db_path: Path to the SQLite database file.

    Returns:
        Dict with row columns plus parsed structured_json, or None if not found.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, created_at, shift_date, shift_type, operative, line_or_area, structured_json
            FROM handovers
            WHERE id = ?
            """,
            (handover_id,),
        ).fetchone()

        if row is None:
            return None

        record = dict(row)
        record["structured"] = json.loads(record.pop("structured_json"))
        return record
    finally:
        conn.close()
