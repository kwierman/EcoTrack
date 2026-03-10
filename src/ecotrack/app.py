"""
EcoTrack Dashboard - Plotly Dash visualization app.
Design: Dark industrial/data aesthetic with green accents.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from ecotrack import Database, Analytics

# ─── Colour palette ──────────────────────────────────────────────────────────
BG          = "#0b0f0e"
CARD_BG     = "#111815"
BORDER      = "#1e2b27"
GREEN_1     = "#00ff87"   # primary accent
GREEN_2     = "#00c96d"
GREEN_3     = "#00945a"
MUTED       = "#4a6b60"
TEXT_PRI    = "#e8f5f0"
TEXT_SEC    = "#8ab8a8"
DANGER      = "#ff4d6d"
WARN        = "#ffb347"

MATERIAL_COLORS = {
    "plastic":  "#4ecdc4",
    "paper":    "#45b7d1",
    "glass":    "#96ceb4",
    "metal":    "#dda0dd",
    "organic":  "#98d8c8",
    "other":    "#778899",
}

REGION_COLORS = {
    "Europe":       GREEN_1,
    "Americas":     "#4ecdc4",
    "Asia-Pacific": "#45b7d1",
    "Africa":       WARN,
    "Middle East":  "#dda0dd",
}


# ─── Chart factories ──────────────────────────────────────────────────────────

def apply_dark_theme(fig, title="", height=None):
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=TEXT_PRI, family="'Courier New', monospace"),
                   x=0.02, y=0.97),
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT_SEC, size=11, family="'Courier New', monospace"),
        margin=dict(l=12, r=12, t=44, b=12),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        height=height,
    )
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(size=10))
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(size=10))
    return fig


def fig_recycling_bar(df: pd.DataFrame, year: int) -> go.Figure:
    """Horizontal bar — recycling rate leaderboard."""
    dfy = df.sort_values("overall_rate", ascending=True).tail(25)
    colors = [REGION_COLORS.get(r, GREEN_2) for r in dfy["region"]]
    fig = go.Figure(go.Bar(
        x=dfy["overall_rate"],
        y=dfy["country"],
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=dfy["overall_rate"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        textfont=dict(size=9, color=TEXT_SEC),
        hovertemplate="<b>%{y}</b><br>Recycling rate: %{x:.1f}%<extra></extra>",
    ))
    apply_dark_theme(fig, f"♻️  Recycling Rate by Country — {year}", height=560)
    fig.update_xaxes(range=[0, 100], ticksuffix="%")
    fig.update_layout(showlegend=False)
    return fig


def fig_waste_scatter(df: pd.DataFrame) -> go.Figure:
    """Scatter: GDP per capita vs per-capita waste generation."""
    fig = px.scatter(
        df, x="gdp_per_capita", y="total_waste_kg_cap",
        color="region", size="recycling_rate",
        hover_name="country",
        color_discrete_map=REGION_COLORS,
        size_max=28,
        labels={
            "gdp_per_capita": "GDP per Capita (USD)",
            "total_waste_kg_cap": "Waste Generated (kg/cap/yr)",
            "recycling_rate": "Recycling Rate (%)",
        },
    )
    apply_dark_theme(fig, "💰  Wealth vs Waste Generation  (bubble = recycling rate)", height=400)
    fig.update_traces(marker=dict(line=dict(width=0.5, color=BG)))
    return fig


def fig_material_sankey(df: pd.DataFrame, country: str) -> go.Figure:
    """Sankey diagram of material flows for a country."""
    if df.empty:
        return go.Figure()

    materials = df["material"].tolist()
    destinations = ["Recycled", "Landfilled", "Incinerated", "Composted"]

    labels = materials + destinations
    label_idx = {l: i for i, l in enumerate(labels)}

    sources, targets, values, colors = [], [], [], []

    mat_colors = list(MATERIAL_COLORS.values())
    for i, row in df.iterrows():
        mat = row["material"]
        si = label_idx[mat]
        for dest, col_key in [("Recycled", "recycled_kt"), ("Landfilled", "landfilled_kt"),
                               ("Incinerated", "incinerated_kt"), ("Composted", "composted_kt")]:
            val = row[col_key]
            if val > 0:
                sources.append(si)
                targets.append(label_idx[dest])
                values.append(val)
                colors.append(MATERIAL_COLORS.get(mat, MUTED) + "99")

    fig = go.Figure(go.Sankey(
        node=dict(
            pad=15, thickness=16,
            label=labels,
            color=[MATERIAL_COLORS.get(l, GREEN_3) for l in materials] +
                  [GREEN_1, DANGER, WARN, "#98d8c8"],
            line=dict(color=BG, width=0.5),
        ),
        link=dict(source=sources, target=targets, value=values, color=colors),
    ))
    apply_dark_theme(fig, f"🔄  Material Flow — {country}", height=400)
    return fig


def fig_trend_lines(df: pd.DataFrame, country: str) -> go.Figure:
    """Multi-line trend for waste KPIs over years."""
    if df.empty:
        return go.Figure()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08,
                        subplot_titles=["Waste (kg / capita / year)", "Recycling Rate (%)"])

    metrics = [
        ("total_waste_kg_cap", "Total Waste", GREEN_1, 1),
        ("msw_kg_cap",         "Municipal Solid",   GREEN_2, 1),
        ("e_waste_kg_cap",     "E-Waste",           DANGER, 1),
        ("food_waste_kg_cap",  "Food Waste",        WARN, 1),
    ]
    for col, name, color, row in metrics:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["year"], y=df[col], name=name,
                line=dict(color=color, width=2),
                mode="lines+markers",
                marker=dict(size=4),
            ), row=row, col=1)

    if "recycling_rate" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["recycling_rate"], name="Overall Recycling",
            line=dict(color=GREEN_1, width=2.5), fill="tozeroy",
            fillcolor=GREEN_1 + "18",
        ), row=2, col=1)

    apply_dark_theme(fig, f"📈  Trends — {country}", height=420)
    fig.update_layout(legend=dict(orientation="h", y=1.08))
    return fig


def fig_region_donut(df: pd.DataFrame) -> go.Figure:
    """Donut of countries per region."""
    region_counts = df.groupby("region").size().reset_index(name="count")
    colors = [REGION_COLORS.get(r, MUTED) for r in region_counts["region"]]
    fig = go.Figure(go.Pie(
        labels=region_counts["region"],
        values=region_counts["count"],
        hole=0.62,
        marker=dict(colors=colors, line=dict(color=BG, width=2)),
        textfont=dict(size=10, color=TEXT_PRI),
        hovertemplate="<b>%{label}</b><br>%{value} countries<extra></extra>",
    ))
    apply_dark_theme(fig, "🌍  Countries by Region", height=280)
    return fig


def fig_material_global_bar(df: pd.DataFrame) -> go.Figure:
    """Stacked bar: generated vs recycled by material globally."""
    colors = [MATERIAL_COLORS.get(m, MUTED) for m in df["material"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Generated (kt)", x=df["material"], y=df["total_generated_kt"],
        marker_color=[c + "55" for c in colors],
        hovertemplate="<b>%{x}</b><br>Generated: %{y:,.0f} kt<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Recycled (kt)", x=df["material"], y=df["total_recycled_kt"],
        marker_color=colors,
        hovertemplate="<b>%{x}</b><br>Recycled: %{y:,.0f} kt<extra></extra>",
    ))
    apply_dark_theme(fig, "🧪  Global Material Generation vs Recycling", height=300)
    fig.update_layout(barmode="overlay", bargap=0.2)
    return fig


def fig_heatmap_recycling(df: pd.DataFrame) -> go.Figure:
    """Heatmap of recycling rate by material & country."""
    materials = ["overall_rate", "plastic_rate", "paper_rate",
                 "glass_rate", "metal_rate", "organic_rate"]
    nice = ["Overall", "Plastic", "Paper", "Glass", "Metal", "Organic"]

    pivot = df[["country"] + materials].set_index("country")[materials]
    pivot.columns = nice

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0, BG], [0.3, GREEN_3], [0.7, GREEN_2], [1.0, GREEN_1]],
        zmin=0, zmax=100,
        text=[[f"{v:.0f}%" if not pd.isna(v) else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont=dict(size=8),
        hovertemplate="Country: %{y}<br>Material: %{x}<br>Rate: %{z:.1f}%<extra></extra>",
    ))
    apply_dark_theme(fig, "🗺️  Recycling Rates by Material & Country", height=700)
    return fig


# ─── App factory ─────────────────────────────────────────────────────────────

def create_app(db: Database):
    try:
        import dash
        from dash import dcc, html, Input, Output, callback
    except ImportError:
        raise ImportError("pip install dash plotly")

    app = dash.Dash(
        __name__,
        title="EcoTrack Dashboard",
        suppress_callback_exceptions=True,
    )

    ana = Analytics(db)

    # ── Load data ──────────────────────────────────────────────────────────
    countries_df   = db.get_countries()
    leaderboard    = db.get_recycling_leaderboard()
    mat_global     = ana.material_composition_global()
    efficiency     = ana.recycling_efficiency_score()
    top_improvers  = ana.top_improvers(10)
    global_summary = db.get_global_summary()
    material_flows_all = db.get_material_breakdown()

    all_years  = sorted(leaderboard["year"].unique().tolist(), reverse=True) if not leaderboard.empty else [2023]
    latest_yr  = all_years[0]
    all_country_codes = sorted(countries_df["country_code"].tolist()) if not countries_df.empty else []
    all_countries     = sorted(countries_df["country"].tolist()) if not countries_df.empty else []
    country_map = dict(zip(countries_df["country_code"], countries_df["country"])) if not countries_df.empty else {}

    # KPI cards
    def kpi(label, value, unit="", color=GREEN_1):
        return html.Div([
            html.Div(label, style={"fontSize": "10px", "color": TEXT_SEC, "letterSpacing": "2px",
                                   "textTransform": "uppercase", "marginBottom": "6px"}),
            html.Div([
                html.Span(value, style={"fontSize": "28px", "fontWeight": "700", "color": color}),
                html.Span(f" {unit}", style={"fontSize": "12px", "color": MUTED}),
            ]),
        ], style={
            "background": CARD_BG, "border": f"1px solid {BORDER}",
            "borderTop": f"2px solid {color}",
            "padding": "18px 22px", "borderRadius": "6px", "flex": "1",
        })

    n_countries = len(all_countries)
    avg_recycle = f"{leaderboard['overall_rate'].mean():.1f}%" if not leaderboard.empty else "N/A"
    avg_waste   = f"{countries_df['total_waste_kg_cap'].mean():.0f}" if not countries_df.empty else "N/A"
    top_country = leaderboard.iloc[0]["country"] if not leaderboard.empty else "N/A"

    # ── Layout ────────────────────────────────────────────────────────────
    FONT = "'Courier New', 'Lucida Console', monospace"

    app.layout = html.Div(style={
        "backgroundColor": BG, "minHeight": "100vh",
        "fontFamily": FONT, "color": TEXT_PRI,
    }, children=[

        # ── Header ────────────────────────────────────────────────────────
        html.Div(style={
            "borderBottom": f"1px solid {BORDER}",
            "padding": "20px 32px",
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "background": CARD_BG,
        }, children=[
            html.Div([
                html.Span("♻", style={"color": GREEN_1, "fontSize": "24px", "marginRight": "12px"}),
                html.Span("ECO", style={"color": GREEN_1, "fontSize": "22px", "fontWeight": "900",
                                        "letterSpacing": "4px"}),
                html.Span("TRACK", style={"color": TEXT_PRI, "fontSize": "22px", "fontWeight": "300",
                                          "letterSpacing": "4px"}),
            ]),
            html.Div("Global Sustainability & Waste Intelligence Platform",
                     style={"color": MUTED, "fontSize": "11px", "letterSpacing": "2px"}),
            html.Div(f"Data through {latest_yr}",
                     style={"color": GREEN_3, "fontSize": "10px", "letterSpacing": "1px"}),
        ]),

        # ── Tabs ──────────────────────────────────────────────────────────
        html.Div(style={"padding": "0 32px"}, children=[
            dcc.Tabs(id="tabs", value="overview", style={"borderBottom": f"1px solid {BORDER}"},
                     colors={"border": BORDER, "primary": GREEN_1, "background": BG},
                     children=[
                dcc.Tab(label="📊  Overview",    value="overview",    style={"color": MUTED},
                        selected_style={"color": GREEN_1, "borderTop": f"2px solid {GREEN_1}",
                                        "background": CARD_BG, "fontFamily": FONT}),
                dcc.Tab(label="🏆  Leaderboard", value="leaderboard", style={"color": MUTED},
                        selected_style={"color": GREEN_1, "borderTop": f"2px solid {GREEN_1}",
                                        "background": CARD_BG, "fontFamily": FONT}),
                dcc.Tab(label="📈  Country Drill-down", value="country", style={"color": MUTED},
                        selected_style={"color": GREEN_1, "borderTop": f"2px solid {GREEN_1}",
                                        "background": CARD_BG, "fontFamily": FONT}),
                dcc.Tab(label="🧪  Material Flows", value="materials", style={"color": MUTED},
                        selected_style={"color": GREEN_1, "borderTop": f"2px solid {GREEN_1}",
                                        "background": CARD_BG, "fontFamily": FONT}),
                dcc.Tab(label="🗺️  Heatmap", value="heatmap", style={"color": MUTED},
                        selected_style={"color": GREEN_1, "borderTop": f"2px solid {GREEN_1}",
                                        "background": CARD_BG, "fontFamily": FONT}),
            ]),
        ]),

        html.Div(id="tab-content", style={"padding": "24px 32px"}),
    ])

    # ── Tab content callback ───────────────────────────────────────────────
    @app.callback(Output("tab-content", "children"), Input("tabs", "value"))
    def render_tab(tab):

        # ── Overview ──────────────────────────────────────────────────────
        if tab == "overview":
            return html.Div([
                # KPIs
                html.Div([
                    kpi("Countries Tracked", str(n_countries), "nations"),
                    kpi("Avg Recycling Rate", avg_recycle, "", GREEN_1),
                    kpi("Avg Waste / Capita", avg_waste, "kg/yr", WARN),
                    kpi("Top Recycler", top_country, "", GREEN_2),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "20px"}),

                # Row 1
                html.Div([
                    html.Div(
                        dcc.Graph(figure=fig_waste_scatter(countries_df), config={"displayModeBar": False}),
                        style={"flex": "2", "background": CARD_BG, "border": f"1px solid {BORDER}",
                               "borderRadius": "6px", "overflow": "hidden"}
                    ),
                    html.Div(
                        dcc.Graph(figure=fig_region_donut(countries_df), config={"displayModeBar": False}),
                        style={"flex": "1", "background": CARD_BG, "border": f"1px solid {BORDER}",
                               "borderRadius": "6px", "overflow": "hidden"}
                    ),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "20px"}),

                # Row 2 – material global
                html.Div(
                    dcc.Graph(figure=fig_material_global_bar(mat_global), config={"displayModeBar": False}),
                    style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                           "borderRadius": "6px", "overflow": "hidden", "marginBottom": "20px"}
                ),

                # Top improvers table
                html.Div([
                    html.Div("📈  TOP RECYCLING IMPROVERS",
                             style={"color": GREEN_1, "fontSize": "11px", "letterSpacing": "2px",
                                    "padding": "14px 18px", "borderBottom": f"1px solid {BORDER}"}),
                    html.Table(style={"width": "100%", "borderCollapse": "collapse"}, children=[
                        html.Thead(html.Tr([
                            html.Th(h, style={"textAlign": "left", "color": MUTED,
                                              "fontSize": "10px", "padding": "8px 12px",
                                              "borderBottom": f"1px solid {BORDER}"})
                            for h in ["Country", "Region", "Start Rate", "End Rate", "Improvement"]
                        ])),
                        html.Tbody([
                            html.Tr([
                                html.Td(row["country"], style={"padding": "8px 12px", "color": TEXT_PRI}),
                                html.Td(row["region"],  style={"padding": "8px 12px", "color": MUTED}),
                                html.Td(f"{row['start_rate']:.1f}%", style={"padding": "8px 12px", "color": MUTED}),
                                html.Td(f"{row['end_rate']:.1f}%",   style={"padding": "8px 12px", "color": GREEN_2}),
                                html.Td(f"+{row['improvement']:.1f}pp",
                                        style={"padding": "8px 12px", "color": GREEN_1, "fontWeight": "700"}),
                            ], style={"borderBottom": f"1px solid {BORDER}", "fontSize": "12px"})
                            for _, row in top_improvers.iterrows()
                        ]),
                    ]),
                ], style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                           "borderRadius": "6px", "overflow": "hidden"}),
            ])

        # ── Leaderboard ───────────────────────────────────────────────────
        elif tab == "leaderboard":
            yr_options = [{"label": str(y), "value": y} for y in all_years]
            return html.Div([
                html.Div([
                    html.Label("Select Year:", style={"color": MUTED, "fontSize": "11px",
                                                      "marginRight": "12px", "letterSpacing": "1px"}),
                    dcc.Dropdown(id="lb-year", options=yr_options, value=latest_yr,
                                 clearable=False,
                                 style={"width": "120px", "backgroundColor": CARD_BG,
                                        "color": TEXT_PRI, "border": f"1px solid {BORDER}",
                                        "fontFamily": FONT}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),
                html.Div(dcc.Graph(id="lb-chart", config={"displayModeBar": False}),
                         style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                                "borderRadius": "6px", "overflow": "hidden"}),
            ])

        # ── Country drill-down ────────────────────────────────────────────
        elif tab == "country":
            code_options = [{"label": f"{country_map[c]} ({c})", "value": c}
                            for c in all_country_codes]
            return html.Div([
                html.Div([
                    html.Label("Country:", style={"color": MUTED, "fontSize": "11px",
                                                   "marginRight": "12px", "letterSpacing": "1px"}),
                    dcc.Dropdown(id="cd-country", options=code_options, value="DEU",
                                 clearable=False,
                                 style={"width": "260px", "backgroundColor": CARD_BG,
                                        "color": TEXT_PRI, "border": f"1px solid {BORDER}",
                                        "fontFamily": FONT}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

                html.Div([
                    html.Div(dcc.Graph(id="cd-trend", config={"displayModeBar": False}),
                             style={"flex": "1", "background": CARD_BG,
                                    "border": f"1px solid {BORDER}", "borderRadius": "6px",
                                    "overflow": "hidden"}),
                    html.Div(dcc.Graph(id="cd-sankey", config={"displayModeBar": False}),
                             style={"flex": "1", "background": CARD_BG,
                                    "border": f"1px solid {BORDER}", "borderRadius": "6px",
                                    "overflow": "hidden"}),
                ], style={"display": "flex", "gap": "16px"}),
            ])

        # ── Material flows ─────────────────────────────────────────────────
        elif tab == "materials":
            yr_options = [{"label": str(y), "value": y} for y in all_years]
            mat_options = [{"label": m.title(), "value": m}
                           for m in ["plastic", "paper", "glass", "metal", "organic", "other"]]
            return html.Div([
                html.Div([
                    html.Label("Year:", style={"color": MUTED, "fontSize": "11px",
                                               "marginRight": "8px"}),
                    dcc.Dropdown(id="mf-year", options=yr_options, value=latest_yr,
                                 clearable=False, style={"width": "110px", "backgroundColor": CARD_BG,
                                                         "fontFamily": FONT}),
                    html.Label("Material:", style={"color": MUTED, "fontSize": "11px",
                                                   "marginRight": "8px", "marginLeft": "20px"}),
                    dcc.Dropdown(id="mf-material", options=mat_options, value="plastic",
                                 clearable=False, style={"width": "140px", "backgroundColor": CARD_BG,
                                                         "fontFamily": FONT}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),
                html.Div(dcc.Graph(id="mf-chart", config={"displayModeBar": False}),
                         style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                                "borderRadius": "6px", "overflow": "hidden"}),
            ])

        # ── Heatmap ───────────────────────────────────────────────────────
        elif tab == "heatmap":
            return html.Div(
                dcc.Graph(figure=fig_heatmap_recycling(leaderboard), config={"displayModeBar": False}),
                style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                       "borderRadius": "6px", "overflow": "hidden"}
            )

    # ── Leaderboard year ───────────────────────────────────────────────────
    @app.callback(Output("lb-chart", "figure"), Input("lb-year", "value"))
    def update_leaderboard(year):
        dfy = db.get_recycling_leaderboard(year)
        return fig_recycling_bar(dfy, year)

    # ── Country drill-down ─────────────────────────────────────────────────
    @app.callback(
        Output("cd-trend",  "figure"),
        Output("cd-sankey", "figure"),
        Input("cd-country", "value"),
    )
    def update_country(code):
        trend_df = db.get_waste_trend(code)
        cname = country_map.get(code, code)

        flows = material_flows_all[
            (material_flows_all["country_code"] == code) &
            (material_flows_all["year"] == latest_yr)
        ].copy()

        return fig_trend_lines(trend_df, cname), fig_material_sankey(flows, cname)

    # ── Material flows ─────────────────────────────────────────────────────
    @app.callback(
        Output("mf-chart", "figure"),
        Input("mf-year",     "value"),
        Input("mf-material", "value"),
    )
    def update_material(year, material):
        df = material_flows_all[
            (material_flows_all["year"] == year) &
            (material_flows_all["material"] == material)
        ].copy()

        if df.empty:
            return go.Figure()

        df = df.sort_values("recycle_pct", ascending=True)
        color = MATERIAL_COLORS.get(material, GREEN_2)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["recycle_pct"], y=df["country"], orientation="h",
            marker=dict(color=color),
            text=df["recycle_pct"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else ""),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Recycled: %{x:.1f}%<extra></extra>",
        ))
        apply_dark_theme(fig, f"♻️  {material.title()} Recycling Rate — {year}", height=620)
        fig.update_xaxes(range=[0, 105], ticksuffix="%")
        return fig

    return app


# ─── Standalone entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    db = Database()
    from ecotrack import EcoScraper
    if db.stats()["waste_metrics"] == 0:
        print("No data found — seeding database …")
        scraper = EcoScraper(db)
        scraper.scrape_all()

    app = create_app(db)
    print("🚀  EcoTrack Dashboard  →  http://localhost:8050")
    app.run(debug=True, port=8050)
