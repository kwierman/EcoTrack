#!/usr/bin/env python3
"""
EcoTrack CLI - Command line interface for the sustainability data library.

Usage:
    python cli.py scrape          # Scrape all sources
    python cli.py stats           # Show database statistics
    python cli.py query           # Interactive query mode
    python cli.py export          # Export data to CSV
    python cli.py dashboard       # Launch Plotly Dash dashboard
"""

import sys
import os
import time
from pathlib import Path

# Add parent to path so we can import ecotrack
sys.path.insert(0, str(Path(__file__).parent))

import click
from ecotrack import Database, EcoScraper, Analytics


def _make_db(db_path):
    return Database(db_path)


@click.group()
@click.option("--db", default=None, help="Path to database file")
@click.pass_context
def cli(ctx, db):
    """🌱 EcoTrack - Sustainability & Waste Management Data CLI"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db


# --------------------------------------------------------------------------- #
# scrape                                                                       #
# --------------------------------------------------------------------------- #
@cli.command()
@click.option("--years", default="2015-2023", help="Year range, e.g. 2018-2023")
@click.option("--source", default=None, help="Specific source name to scrape")
@click.pass_context
def scrape(ctx, years, source):
    """Scrape sustainability data from online sources."""
    start, end = (int(y) for y in years.split("-"))
    year_list = list(range(start, end + 1))

    click.echo(f"\n🌍  EcoTrack Scraper")
    click.echo(f"    Years: {start}–{end}  ({len(year_list)} years)")
    click.echo(f"    Database: {ctx.obj['db_path'] or '~/.ecotrack/ecotrack.db'}")
    click.echo()

    db = _make_db(ctx.obj["db_path"])
    scraper = EcoScraper(db)

    t0 = time.time()
    if source:
        click.echo(f"  Scraping: {source} …")
        try:
            n = scraper.scrape_source(source, year_list)
            click.echo(f"  ✅  {n:,} records inserted.")
        except ValueError as e:
            click.echo(f"  ❌  {e}")
            sys.exit(1)
    else:
        results = scraper.scrape_all(year_list)
        for name, count in results.items():
            click.echo(f"  ✅  {name:<30} {count:>6,} records")

    elapsed = time.time() - t0
    click.echo(f"\n  Done in {elapsed:.1f}s\n")
    db.close()


# --------------------------------------------------------------------------- #
# stats                                                                        #
# --------------------------------------------------------------------------- #
@cli.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    db = _make_db(ctx.obj["db_path"])
    stats = db.stats()
    click.echo("\n📊  EcoTrack Database Statistics")
    click.echo("  " + "─" * 36)
    for table, count in stats.items():
        click.echo(f"  {table:<28} {count:>6,} rows")

    # Also show latest year
    row = db.execute("SELECT MAX(year) FROM waste_metrics").fetchone()
    latest = row[0] if row and row[0] else "N/A"
    click.echo(f"\n  Latest data year: {latest}")

    row = db.execute("SELECT COUNT(DISTINCT country_code) FROM waste_metrics").fetchone()
    click.echo(f"  Countries with data: {row[0] if row else 0}")
    click.echo()
    db.close()


# --------------------------------------------------------------------------- #
# query                                                                        #
# --------------------------------------------------------------------------- #
@cli.command()
@click.argument("sql", default="", required=False)
@click.option("--country", "-c", default=None, help="Filter by country code")
@click.option("--year", "-y", default=None, type=int, help="Filter by year")
@click.pass_context
def query(ctx, sql, country, year):
    """Run a SQL query or show predefined report."""
    import pandas as pd
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 140)

    db = _make_db(ctx.obj["db_path"])

    if sql:
        df = db.query_df(sql)
        click.echo(df.to_string(index=False))
    elif country:
        df = db.get_waste_trend(country)
        click.echo(f"\n📈  Waste & Recycling Trend: {country}\n")
        click.echo(df.to_string(index=False))
    else:
        # Default: recycling leaderboard
        df = db.get_recycling_leaderboard(year)
        click.echo(f"\n🏆  Recycling Leaderboard {year or '(latest)'}\n")
        click.echo(df[["country", "region", "year", "overall_rate",
                        "plastic_rate", "paper_rate"]].to_string(index=False))
    click.echo()
    db.close()


# --------------------------------------------------------------------------- #
# export                                                                       #
# --------------------------------------------------------------------------- #
@cli.command()
@click.option("--out", default="ecotrack_export", help="Output directory")
@click.pass_context
def export(ctx, out):
    """Export all tables to CSV files."""
    import pandas as pd
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)

    db = _make_db(ctx.obj["db_path"])
    tables = ["country_profiles", "waste_metrics", "recycling_rates",
              "material_flows", "data_sources", "scrape_log"]
    click.echo(f"\n💾  Exporting to {out_dir}/\n")
    for tbl in tables:
        df = db.query_df(f"SELECT * FROM {tbl}")
        path = out_dir / f"{tbl}.csv"
        df.to_csv(path, index=False)
        click.echo(f"  ✅  {tbl}.csv  ({len(df):,} rows)")
    click.echo()
    db.close()


# --------------------------------------------------------------------------- #
# analytics                                                                    #
# --------------------------------------------------------------------------- #
@cli.command()
@click.option("--report", type=click.Choice(
    ["efficiency", "improvers", "circular", "materials"]), default="efficiency")
@click.option("--year", "-y", default=None, type=int)
@click.pass_context
def analyze(ctx, report, year):
    """Run analytical reports."""
    db = _make_db(ctx.obj["db_path"])
    ana = Analytics(db)

    if report == "efficiency":
        df = ana.recycling_efficiency_score(year)
        click.echo("\n🔬  Recycling Efficiency Scores\n")
        click.echo(df[["country", "region", "efficiency_score",
                        "overall_rate", "waste_penalty"]].to_string(index=False))
    elif report == "improvers":
        df = ana.top_improvers()
        click.echo("\n📈  Top Recycling Improvers\n")
        click.echo(df.to_string(index=False))
    elif report == "circular":
        df = ana.circular_economy_index(year)
        click.echo("\n♻️  Circular Economy Index\n")
        click.echo(df.to_string(index=False))
    elif report == "materials":
        df = ana.material_composition_global(year)
        click.echo("\n🧪  Global Material Composition\n")
        click.echo(df.to_string(index=False))
    click.echo()
    db.close()


# --------------------------------------------------------------------------- #
# dashboard                                                                    #
# --------------------------------------------------------------------------- #
@cli.command()
@click.option("--port", default=8050, type=int)
@click.option("--host", default="0.0.0.0")
@click.option("--debug", is_flag=True, default=False)
@click.pass_context
def dashboard(ctx, port, host, debug):
    """Launch the interactive Plotly Dash dashboard."""
    click.echo(f"\n🚀  Starting EcoTrack Dashboard on http://{host}:{port}\n")
    # Import dashboard and run
    sys.path.insert(0, str(Path(__file__).parent))
    from dashboard.app import create_app
    db = _make_db(ctx.obj["db_path"])
    app = create_app(db)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    cli()
