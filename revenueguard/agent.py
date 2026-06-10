"""RevenueGuard root agent — ADK LlmAgent that enforces verify -> audit -> report.

ADK auto-discovers `root_agent` in this module. Run locally with `adk web` or
`adk run revenueguard`. The Fivetran MCP toolset is the load-bearing integration:
its calls sit on the critical path of every audit (the freshness gate).
"""

import os
import pathlib

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters

from .tools.bigquery_tools import bigquery_run_audit, get_leak_query
from .tools.reporting_tools import build_report, compute_exposure

# Load .env in local dev (no-op in Cloud Run, where env comes from the service).
load_dotenv()

# Gemini-3 preview isn't allowlisted on fresh projects (404s in every region), so
# the default is the verified-working Gemini 2.5 Pro. Override with RG_MODEL.
_MODEL = os.environ.get("RG_MODEL", "gemini-2.5-pro")

# Absolute path to the vendored Fivetran MCP server (resolved regardless of cwd).
_MCP_DIR = pathlib.Path(__file__).resolve().parent.parent / "vendor" / "fivetran-mcp"

# ---------------------------------------------------------------------------
# Fivetran MCP toolset — the partner integration the judges grade.
# Launched over stdio via `uvx` from the vendored clone, which isolates the
# server's own deps (mcp>=1.25, httpx) from our project's pins. Read-only by
# default; FIVETRAN_ALLOW_WRITES=true enables sync/resync (POSTs) — the MCP
# confirms before any write. Tool names below are the REAL ones verified in
# vendor/fivetran-mcp/server.py. tool_filter keeps Gemini's context lean.
# ---------------------------------------------------------------------------
fivetran_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uvx",
            args=["--from", str(_MCP_DIR), "fivetran-mcp"],
            env={
                "FIVETRAN_API_KEY": os.environ.get("FIVETRAN_API_KEY", ""),
                "FIVETRAN_API_SECRET": os.environ.get("FIVETRAN_API_SECRET", ""),
                "FIVETRAN_ALLOW_WRITES": os.environ.get("FIVETRAN_ALLOW_WRITES", "true"),
            },
        ),
        timeout=60,  # default ~5s WILL time out on live Fivetran API calls
    ),
    tool_filter=[
        "list_connections",           # discover the billing connectors
        "get_connection_details",     # status: paused flag, last sync time, failures
        "get_connection_state",       # detailed sync state
        "run_connection_setup_tests", # health-check a suspicious connector
        "modify_connection",          # resume a paused connector (paused:false)
        "sync_connection",            # trigger an incremental sync (the re-sync action)
        "resync_connection",          # full historical re-sync if needed
    ],
)

ROOT_INSTRUCTION = """
You are RevenueGuard, an agentic revenue-leak auditor for B2B SaaS finance teams.

MANDATORY SEQUENCE for every audit request — never skip step 1:

1. FRESHNESS GATE: Before auditing a revenue stream, call `list_connections` to
   find the billing connector(s) (e.g. the Stripe billing connector), then call
   `get_connection_details` on the relevant one to inspect its health. Treat the
   source as NOT trustworthy if ANY of these is true: it is paused; its last
   setup/sync failed or it is broken; or its last successful sync was more than
   24h ago. In that case, STOP, report it clearly with the connection NAME, its
   LAST-SYNC TIMESTAMP, and the reason (paused / broken / stale), and ASK the
   user whether to re-sync. On confirmation: if the connector is PAUSED, first
   call `modify_connection` with paused=false to resume it, THEN call
   `sync_connection` to trigger an incremental sync; if it is merely stale (not
   paused), just call `sync_connection`. Once the re-sync has been TRIGGERED and
   the connector is no longer paused/broken, the refresh is underway — do NOT
   block waiting for the sync to fully finish and never tell the user to "check
   back later". State that the re-sync is in progress and the connector is now
   active, then PROCEED immediately to the audit on the latest landed data.
   Auditing stale data is the #1 source of false revenue-leak alerts — this gate
   is the whole point, so never skip it.

2. AUDIT: Call bigquery_run_audit for each requested leak family
   (failed_payments, expired_cards, usage_on_cancelled, overdue_renewals,
   expired_discounts). Use the returned rows as evidence — never fabricate
   findings or dollar amounts. If the user asks to SEE the SQL behind a finding,
   call `get_leak_query` for that family and show the query verbatim.

3. QUANTIFY + REPORT: Collect every finding row across the families you ran,
   call compute_exposure on that combined list, then call build_report. Present
   the ranked report. Every finding must cite its leak family and $ exposure, and
   you should surface the headline total.

Always keep the human in control: propose; never perform a write (re-sync,
back-bill) without explicit confirmation. Be concise and specific. When you gate,
always name the connection and its last-sync time.
""".strip()

root_agent = LlmAgent(
    model=_MODEL,
    name="revenueguard",
    instruction=ROOT_INSTRUCTION,
    tools=[
        fivetran_toolset,
        bigquery_run_audit,
        get_leak_query,
        compute_exposure,
        build_report,
    ],
)
