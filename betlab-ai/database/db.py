"""
BETLAB AI - Capa de acceso a SQLite
===================================

Funciones utilitarias para abrir conexiones, inicializar el esquema y
realizar operaciones de lectura/escritura reutilizables por todos los módulos.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pandas as pd

from config import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Devuelve una conexión con row_factory tipo dict y FK activadas."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def session(db_path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Context manager que commitea al salir y hace rollback ante errores."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Crea todas las tablas a partir de schema.sql (idempotente)."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with session(db_path) as conn:
        conn.executescript(schema)


def upsert(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    """INSERT OR REPLACE genérico a partir de un dict columna->valor."""
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
    conn.execute(sql, tuple(row.values()))


def insert(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> int:
    """INSERT simple; devuelve el lastrowid."""
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(row.values()))
    return int(cur.lastrowid)


def executemany(conn: sqlite3.Connection, sql: str, rows: Iterable[Sequence[Any]]) -> None:
    conn.executemany(sql, list(rows))


def query_df(sql: str, params: Sequence[Any] | None = None,
             db_path: Path | str = DB_PATH) -> pd.DataFrame:
    """Ejecuta una SELECT y devuelve un DataFrame de pandas."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(sql, conn, params=params or [])
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    init_db()
    print(f"Base de datos inicializada en {DB_PATH}")
