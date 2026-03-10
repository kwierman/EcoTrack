"""
Analytics - higher-order analysis on top of the database.
"""

import pandas as pd
from typing import Optional, List


class Analytics:
    """Analytical computations over ecotrack data."""

    def __init__(self, db):
        self.db = db

    def recycling_efficiency_score(self, year: Optional[int] = None) -> pd.DataFrame:
        """
        Composite score: blends overall_rate, e_waste_rate, organic_rate
        and penalises high per-capita waste generation.
        """
        yr = year or self._latest_year("recycling_rates")
        df = self.db.query_df("""
            SELECT cp.country, cp.country_code, cp.region,
                   rr.overall_rate, rr.plastic_rate, rr.e_waste_rate, rr.organic_rate,
                   wm.total_waste_kg_cap, wm.food_waste_kg_cap
            FROM recycling_rates rr
            JOIN country_profiles cp ON rr.country_code = cp.country_code
            JOIN waste_metrics wm ON rr.country_code = wm.country_code AND rr.year = wm.year
            WHERE rr.year = ?
        """, (yr,))

        if df.empty:
            return df

        # Normalise waste generation (lower is better → invert)
        max_waste = df["total_waste_kg_cap"].max()
        df["waste_penalty"] = df["total_waste_kg_cap"] / max_waste * 100
        df["efficiency_score"] = (
            df["overall_rate"] * 0.40 +
            df["e_waste_rate"] * 0.20 +
            df["organic_rate"] * 0.20 +
            (100 - df["waste_penalty"]) * 0.20
        ).round(1)
        return df.sort_values("efficiency_score", ascending=False).reset_index(drop=True)

    def waste_reduction_trend(self) -> pd.DataFrame:
        """Year-on-year change in per-capita waste by country."""
        df = self.db.query_df("""
            SELECT country_code, year, total_waste_kg_cap
            FROM waste_metrics
            ORDER BY country_code, year
        """)
        df["yoy_change_pct"] = df.groupby("country_code")["total_waste_kg_cap"].pct_change() * 100
        return df.dropna()

    def circular_economy_index(self, year: Optional[int] = None) -> pd.DataFrame:
        """Approximation of circular economy score: recycled / generated across materials."""
        yr = year or self._latest_year("material_flows")
        return self.db.query_df("""
            SELECT cp.country, cp.region, mf.year,
                   SUM(mf.generated_kt) as total_generated,
                   SUM(mf.recycled_kt + mf.composted_kt) as total_recovered,
                   SUM(mf.landfilled_kt) as total_landfilled,
                   ROUND(100.0 * SUM(mf.recycled_kt + mf.composted_kt) / 
                         NULLIF(SUM(mf.generated_kt), 0), 1) as recovery_rate
            FROM material_flows mf
            JOIN country_profiles cp ON mf.country_code = cp.country_code
            WHERE mf.year = ?
            GROUP BY cp.country, cp.region, mf.year
            ORDER BY recovery_rate DESC
        """, (yr,))

    def top_improvers(self, n: int = 10) -> pd.DataFrame:
        """Countries with greatest recycling rate improvement over available years."""
        return self.db.query_df(f"""
            WITH ranked AS (
                SELECT country_code, year, overall_rate,
                       ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY year ASC) as rn_first,
                       ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY year DESC) as rn_last
                FROM recycling_rates
            ),
            first_last AS (
                SELECT country_code,
                       MAX(CASE WHEN rn_first = 1 THEN overall_rate END) as first_rate,
                       MAX(CASE WHEN rn_last  = 1 THEN overall_rate END) as last_rate,
                       MAX(CASE WHEN rn_first = 1 THEN year END) as first_year,
                       MAX(CASE WHEN rn_last  = 1 THEN year END) as last_year
                FROM ranked GROUP BY country_code
            )
            SELECT cp.country, cp.region, fl.first_year, fl.last_year,
                   ROUND(fl.first_rate, 1) as start_rate,
                   ROUND(fl.last_rate, 1) as end_rate,
                   ROUND(fl.last_rate - fl.first_rate, 1) as improvement
            FROM first_last fl
            JOIN country_profiles cp ON fl.country_code = cp.country_code
            ORDER BY improvement DESC
            LIMIT {n}
        """)

    def material_composition_global(self, year: Optional[int] = None) -> pd.DataFrame:
        yr = year or self._latest_year("material_flows")
        return self.db.query_df("""
            SELECT material,
                   ROUND(SUM(generated_kt), 0) as total_generated_kt,
                   ROUND(SUM(recycled_kt), 0)  as total_recycled_kt,
                   ROUND(SUM(landfilled_kt), 0) as total_landfilled_kt,
                   ROUND(100.0 * SUM(recycled_kt) / NULLIF(SUM(generated_kt), 0), 1) as global_recycle_pct
            FROM material_flows
            WHERE year = ?
            GROUP BY material
            ORDER BY total_generated_kt DESC
        """, (yr,))

    def _latest_year(self, table: str) -> int:
        row = self.db.execute(f"SELECT MAX(year) FROM {table}").fetchone()
        return row[0] or 2023
