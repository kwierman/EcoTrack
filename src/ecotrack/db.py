"""
Database layer - DuckDB-style analytics via SQLite + pandas.
Uses SQLModel-inspired patterns with dataclasses.
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd


DEFAULT_DB_PATH = Path.home() / ".ecotrack" / "ecotrack.db"


class Database:
    """
    SQLite-backed database with DuckDB-style analytical query support.
    Uses pandas for in-memory OLAP operations.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_schema()

    # ------------------------------------------------------------------ #
    # Connection management                                                #
    # ------------------------------------------------------------------ #

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------ #
    # Schema initialisation                                                #
    # ------------------------------------------------------------------ #

    def _init_schema(self):
        conn = self.connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS data_sources (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                url         TEXT,
                description TEXT,
                last_scraped TEXT,
                record_count INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS country_profiles (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                country             TEXT NOT NULL,
                country_code        TEXT NOT NULL UNIQUE,
                region              TEXT,
                population          INTEGER,
                gdp_per_capita      REAL,
                updated_at          TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS waste_metrics (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code        TEXT NOT NULL,
                year                INTEGER NOT NULL,
                total_waste_kg_cap  REAL,   -- kg per capita per year
                msw_kg_cap          REAL,   -- municipal solid waste
                industrial_waste_kt REAL,   -- kilotonnes
                hazardous_waste_kt  REAL,
                e_waste_kg_cap      REAL,
                food_waste_kg_cap   REAL,
                source_id           INTEGER REFERENCES data_sources(id),
                scraped_at          TEXT DEFAULT (datetime('now')),
                UNIQUE(country_code, year)
            );

            CREATE TABLE IF NOT EXISTS recycling_rates (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code    TEXT NOT NULL,
                year            INTEGER NOT NULL,
                overall_rate    REAL,   -- 0-100 %
                paper_rate      REAL,
                plastic_rate    REAL,
                glass_rate      REAL,
                metal_rate      REAL,
                organic_rate    REAL,
                e_waste_rate    REAL,
                source_id       INTEGER REFERENCES data_sources(id),
                scraped_at      TEXT DEFAULT (datetime('now')),
                UNIQUE(country_code, year)
            );

            CREATE TABLE IF NOT EXISTS material_flows (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code    TEXT NOT NULL,
                year            INTEGER NOT NULL,
                material        TEXT NOT NULL,  -- plastic, paper, glass, metal, organic, other
                generated_kt    REAL,
                recycled_kt     REAL,
                landfilled_kt   REAL,
                incinerated_kt  REAL,
                composted_kt    REAL,
                source_id       INTEGER REFERENCES data_sources(id),
                scraped_at      TEXT DEFAULT (datetime('now')),
                UNIQUE(country_code, year, material)
            );

            CREATE TABLE IF NOT EXISTS scrape_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT,
                status      TEXT,   -- success / error
                records     INTEGER DEFAULT 0,
                message     TEXT,
                duration_s  REAL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_waste_country_year  ON waste_metrics(country_code, year);
            CREATE INDEX IF NOT EXISTS idx_recycle_country_year ON recycling_rates(country_code, year);
            CREATE INDEX IF NOT EXISTS idx_flow_country_year   ON material_flows(country_code, year);
        """)
        conn.commit()

    # ------------------------------------------------------------------ #
    # Generic helpers                                                      #
    # ------------------------------------------------------------------ #

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.connect().execute(sql, params)

    def query_df(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """Return a SQL result as a pandas DataFrame (DuckDB-style)."""
        return pd.read_sql_query(sql, self.connect(), params=params)

    def upsert(self, table: str, data: Dict[str, Any], conflict_cols: List[str]):
        """Insert or replace a row."""
        cols = list(data.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"
        self.connect().execute(sql, [data[c] for c in cols])
        self.connect().commit()

    def bulk_upsert(self, table: str, rows: List[Dict[str, Any]]):
        """Bulk insert list of dicts, ignoring conflicts."""
        if not rows:
            return
        cols = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"
        conn = self.connect()
        conn.executemany(sql, [[r[c] for c in cols] for r in rows])
        conn.commit()

    # ------------------------------------------------------------------ #
    # Convenience query methods                                            #
    # ------------------------------------------------------------------ #

    def get_countries(self) -> pd.DataFrame:
        return self.query_df("""
            SELECT cp.*, 
                   wm.year as latest_year,
                   wm.total_waste_kg_cap,
                   rr.overall_rate as recycling_rate
            FROM country_profiles cp
            LEFT JOIN waste_metrics wm ON cp.country_code = wm.country_code
            LEFT JOIN recycling_rates rr ON cp.country_code = rr.country_code 
                AND rr.year = wm.year
            WHERE wm.year = (
                SELECT MAX(year) FROM waste_metrics wm2 
                WHERE wm2.country_code = cp.country_code
            )
            ORDER BY cp.country
        """)

    def get_waste_trend(self, country_code: str) -> pd.DataFrame:
        return self.query_df("""
            SELECT wm.year, wm.total_waste_kg_cap, wm.msw_kg_cap,
                   wm.e_waste_kg_cap, wm.food_waste_kg_cap,
                   rr.overall_rate as recycling_rate,
                   rr.plastic_rate, rr.paper_rate, rr.glass_rate
            FROM waste_metrics wm
            LEFT JOIN recycling_rates rr 
                ON wm.country_code = rr.country_code AND wm.year = rr.year
            WHERE wm.country_code = ?
            ORDER BY wm.year
        """, (country_code,))

    def get_material_breakdown(self, year: Optional[int] = None) -> pd.DataFrame:
        year_filter = f"AND mf.year = {year}" if year else ""
        return self.query_df(f"""
            SELECT mf.country_code, cp.country, mf.year, mf.material,
                   mf.generated_kt, mf.recycled_kt, mf.landfilled_kt,
                   mf.incinerated_kt, mf.composted_kt,
                   ROUND(100.0 * mf.recycled_kt / NULLIF(mf.generated_kt, 0), 1) as recycle_pct
            FROM material_flows mf
            JOIN country_profiles cp ON mf.country_code = cp.country_code
            WHERE 1=1 {year_filter}
            ORDER BY mf.year, mf.country_code, mf.material
        """)

    def get_global_summary(self) -> pd.DataFrame:
        return self.query_df("""
            SELECT 
                year,
                COUNT(DISTINCT country_code) as countries,
                ROUND(AVG(total_waste_kg_cap), 1) as avg_waste_kg_cap,
                ROUND(AVG(msw_kg_cap), 1) as avg_msw_kg_cap,
                ROUND(MIN(total_waste_kg_cap), 1) as min_waste,
                ROUND(MAX(total_waste_kg_cap), 1) as max_waste
            FROM waste_metrics
            GROUP BY year
            ORDER BY year
        """)

    def get_recycling_leaderboard(self, year: Optional[int] = None) -> pd.DataFrame:
        year_clause = f"AND rr.year = {year}" if year else ""
        return self.query_df(f"""
            SELECT cp.country, cp.country_code, cp.region,
                   rr.year, rr.overall_rate, rr.plastic_rate,
                   rr.paper_rate, rr.glass_rate, rr.metal_rate,
                   rr.organic_rate
            FROM recycling_rates rr
            JOIN country_profiles cp ON rr.country_code = cp.country_code
            WHERE rr.year = (
                SELECT MAX(year) FROM recycling_rates rr2
                WHERE rr2.country_code = rr.country_code
            )
            {year_clause}
            ORDER BY rr.overall_rate DESC
        """)

    def stats(self) -> Dict[str, int]:
        counts = {}
        for tbl in ["waste_metrics", "recycling_rates", "material_flows",
                    "country_profiles", "data_sources"]:
            row = self.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
            counts[tbl] = row[0]
        return counts
