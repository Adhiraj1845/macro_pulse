"""
MCP Server — Macro Pulse
------------------------
Exposes Macro Pulse analytics as Model Context Protocol (MCP) tools,
allowing AI assistants like Claude to query macroeconomic data directly.

Tools exposed:
- get_market_summary       — latest values for all indicators and assets
- get_recession_risk       — composite recession risk score and signal breakdown
- get_correlation          — Pearson correlation between any indicator and asset
- get_macro_trend          — trend direction and magnitude for any indicator
- get_sector_impact        — correlation of an indicator with all tracked assets
- list_indicators          — list all tracked macroeconomic indicators
- list_assets              — list all tracked market assets

Usage:
    python scripts/run_mcp.py

The MCP server communicates over stdio, which is the standard transport
for MCP servers used by Claude Desktop and other MCP-compatible clients.
"""

import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Add project root to path so we can import app modules
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.services.analytics import (
    compute_correlation,
    compute_macro_trend,
    compute_market_summary,
    compute_recession_risk,
    compute_sector_impact,
)
from app.models.models import MacroIndicator, MarketAsset

server = Server("macro-pulse")


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_market_summary",
            description=(
                "Returns the latest values, trend directions, and period-over-period changes "
                "for all tracked macroeconomic indicators and market assets. "
                "Use this for a broad overview of current macro and market conditions."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_recession_risk",
            description=(
                "Returns a composite recession risk score from 0 to 100, "
                "based on four signals: yield curve spread (T10Y2Y), unemployment rate (UNRATE), "
                "CPI inflation (CPIAUCSL), and the federal funds rate (FEDFUNDS). "
                "Also returns individual signal scores and plain English interpretation."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_correlation",
            description=(
                "Computes the Pearson correlation coefficient between a macroeconomic indicator "
                "and a market asset. Both series are aligned on monthly frequency. "
                "Returns the correlation value, interpretation, and number of data points used."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "indicator_id": {
                        "type": "integer",
                        "description": "ID of the macroeconomic indicator (use list_indicators to find IDs)",
                    },
                    "asset_id": {
                        "type": "integer",
                        "description": "ID of the market asset (use list_assets to find IDs)",
                    },
                },
                "required": ["indicator_id", "asset_id"],
            },
        ),
        Tool(
            name="get_macro_trend",
            description=(
                "Analyses the trend direction and magnitude of a macroeconomic indicator "
                "over a specified number of periods using linear regression. "
                "Returns direction (rising/falling/stable), percentage change, and interpretation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "indicator_id": {
                        "type": "integer",
                        "description": "ID of the macroeconomic indicator",
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of monthly periods to analyse (default 24, max 120)",
                        "default": 24,
                    },
                },
                "required": ["indicator_id"],
            },
        ),
        Tool(
            name="get_sector_impact",
            description=(
                "Correlates a macroeconomic indicator against all tracked market assets, "
                "returning results sorted by absolute correlation strength. "
                "Useful for identifying which sectors or assets are most exposed to a given macro variable."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "indicator_id": {
                        "type": "integer",
                        "description": "ID of the macroeconomic indicator",
                    },
                },
                "required": ["indicator_id"],
            },
        ),
        Tool(
            name="list_indicators",
            description=(
                "Lists all macroeconomic indicators currently tracked in the database, "
                "including their IDs, FRED series IDs, names, and categories. "
                "Use this to find indicator IDs for other tool calls."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_assets",
            description=(
                "Lists all market assets currently tracked in the database, "
                "including their IDs, tickers, names, asset classes, and sectors. "
                "Use this to find asset IDs for other tool calls."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    db = SessionLocal()
    try:
        if name == "get_market_summary":
            result = compute_market_summary(db)
            # Summarise concisely for the AI
            lines = ["MARKET SUMMARY\n"]
            lines.append("Indicators:")
            for ind in result["indicators"]:
                val = ind["latest_value"] if ind["latest_value"] is not None else "No data"
                lines.append(f"  {ind['fred_series_id']} ({ind['name']}): {val} [{ind['trend']}] as of {ind['latest_date']}")
            lines.append("\nAssets:")
            for a in result["assets"]:
                val = f"${a['latest_close']:.2f}" if a["latest_close"] is not None else "No data"
                ret = f"{a['daily_return']*100:+.3f}%" if a["daily_return"] is not None else ""
                lines.append(f"  {a['ticker']} ({a['name']}): {val} {ret} [{a['trend']}]")
            lines.append(f"\nAs of: {result['as_of']}")
            output = "\n".join(lines)

        elif name == "get_recession_risk":
            result = compute_recession_risk(db)
            lines = [
                f"RECESSION RISK SCORE: {result['score']}/100",
                f"Level: {result['level']}",
                f"Summary: {result['summary']}",
                f"As of: {result['as_of_date']}",
                "\nSignal Breakdown:",
            ]
            for s in result["signals"]:
                val = f"{s['current_value']:.3f}" if s["current_value"] is not None else "No data"
                lines.append(
                    f"  {s['name']} ({s['fred_series_id']}): value={val}, "
                    f"signal={s['signal_score']*100:.0f}%, contribution={s['contribution']:.1f}pts"
                )
            output = "\n".join(lines)

        elif name == "get_correlation":
            indicator_id = arguments["indicator_id"]
            asset_id = arguments["asset_id"]
            result = compute_correlation(indicator_id, asset_id, db)
            output = (
                f"CORRELATION ANALYSIS\n"
                f"Indicator: {result['indicator_name']}\n"
                f"Asset: {result['asset_ticker']}\n"
                f"Pearson Correlation: {result['correlation']:.4f}\n"
                f"Interpretation: {result['interpretation']}\n"
                f"Data Points: {result['data_points']} monthly observations\n"
                f"Period: {result['start_date']} to {result['end_date']}"
            )

        elif name == "get_macro_trend":
            indicator_id = arguments["indicator_id"]
            periods = arguments.get("periods", 24)
            result = compute_macro_trend(indicator_id, periods, db)
            output = (
                f"MACRO TREND — {result['indicator_name']} ({result['fred_series_id']})\n"
                f"Direction: {result['direction'].upper()}\n"
                f"Change over {result['periods']} periods: {result['change_pct']:+.2f}%\n"
                f"Latest value: {result['latest_value']} ({result['latest_date']})\n"
                f"Earliest value: {result['earliest_value']} ({result['earliest_date']})\n"
                f"Interpretation: {result['interpretation']}"
            )

        elif name == "get_sector_impact":
            indicator_id = arguments["indicator_id"]
            result = compute_sector_impact(indicator_id, db)
            lines = [
                f"SECTOR IMPACT — {result['indicator_name']} ({result['fred_series_id']})",
                f"Assets analysed: {result['total_assets_analysed']} | Excluded: {result['insufficient_data_assets']}",
                "\nRanked by correlation strength:",
            ]
            for r in result["results"][:10]:  # Top 10
                lines.append(
                    f"  {r['ticker']:6} ({r['sector'] or 'N/A':25}) "
                    f"r={r['correlation']:+.4f}  {r['interpretation']}"
                )
            output = "\n".join(lines)

        elif name == "list_indicators":
            indicators = db.query(MacroIndicator).all()
            lines = ["TRACKED INDICATORS\n"]
            for i in indicators:
                lines.append(f"  ID={i.id}  {i.fred_series_id:12} {i.name} [{i.category.value}]")
            output = "\n".join(lines)

        elif name == "list_assets":
            assets = db.query(MarketAsset).all()
            lines = ["TRACKED ASSETS\n"]
            for a in assets:
                lines.append(f"  ID={a.id}  {a.ticker:6} {a.name} [{a.asset_class.value}] {a.sector or ''}")
            output = "\n".join(lines)

        else:
            output = f"Unknown tool: {name}"

    except Exception as e:
        output = f"Error: {str(e)}"
    finally:
        db.close()

    return [TextContent(type="text", text=output)]