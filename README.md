# RevenueGuard

**An agentic revenue-leak auditor for B2B SaaS finance teams — it verifies your data is fresh *before* it trusts it.**

> _Demo GIF + video link go here once recorded._

---

## Problem

B2B SaaS companies leak **2–5% of revenue** to billing errors they never see —
failed payments that were never retried, expired cards on active subscriptions,
usage billed against cancelled plans, renewals that silently never invoiced,
discounts that outlived their expiry. Worse: most leak-detection tools audit
**stale data**, so they cry wolf. Finance and RevOps teams stop trusting the
alerts, and the real leaks keep flowing.

## Solution

RevenueGuard is an autonomous agent that runs a strict **verify → audit → report**
loop:

1. **Verify before audit (the wedge).** Before auditing any revenue stream, the
   agent calls the **Fivetran MCP** to confirm the relevant connector synced
   recently and is healthy. If a source is stale or broken, it stops, reports it,
   and — with your confirmation — triggers a re-sync. No more false alerts from
   stale data.
2. **Audit.** Once freshness is confirmed, it runs multi-step leak detection over
   the landed data in **BigQuery** across five leak families.
3. **Act & report.** It produces a ranked report with **$ exposure per finding**,
   the **SQL evidence**, and a **recommended action** — and keeps the human in
   control (it proposes; you approve any write).

## Architecture

```
                    ┌──────────────────────────────────────┐
   Web UI           │           RevenueGuard Agent          │
   (ADK on          │            (ADK LlmAgent)             │
    Cloud Run)      │        model = gemini-2.5-pro         │
        │           │                                       │
        └──────────▶│  Tools:                               │
                    │   1) Fivetran MCP (McpToolset)  ◀── pipeline freshness/health/resync
                    │   2) bigquery_run_audit         ◀── leak SQL over landed data
                    │   3) compute_exposure           ◀── $ per finding
                    │   4) build_report               ◀── ranked markdown/JSON report
                    └───────────────┬───────────────────────┘
          ┌─────────────────────────┴───────────────────────┐
          ▼                                                   ▼
   Fivetran MCP server                               BigQuery dataset
   (stdio child process)                             revenueguard_demo.*
```

## Tech stack

- **Gemini 2.5 Pro** (via Vertex AI) — the reasoning engine.
- **Google Cloud Agent Builder / ADK** (`google-adk`) — the code-first agent surface.
- **Fivetran MCP** (`github.com/fivetran/fivetran-mcp`) — pipeline freshness, health, and re-sync, launched over stdio via `uvx`.
- **BigQuery** — the warehouse where Fivetran lands the billing data.
- **Cloud Run** — the public hosted URL.

## How we used Fivetran

Fivetran is **load-bearing**, not bolted on. The agent's freshness gate puts
Fivetran MCP calls on the **critical path of every audit**: it lists the relevant
connection, checks its last sync time, and refuses to audit until the data is
confirmed fresh — triggering a re-sync when it isn't. Auditing stale data is the
#1 source of false revenue-leak alerts, so this gate is the whole reason the audit
can be trusted.

```python
fivetran_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uvx",                                   # isolates the server's deps
            args=["--from", str(_MCP_DIR), "fivetran-mcp"],  # vendored clone
            env={
                "FIVETRAN_API_KEY": os.environ["FIVETRAN_API_KEY"],
                "FIVETRAN_API_SECRET": os.environ["FIVETRAN_API_SECRET"],
                "FIVETRAN_ALLOW_WRITES": "true",             # enables resume + re-sync
            },
        ),
        timeout=60,  # live API calls exceed ADK's ~5s default
    ),
    tool_filter=["list_connections", "get_connection_details", "get_connection_state",
                 "run_connection_setup_tests", "modify_connection",
                 "sync_connection", "resync_connection"],
)
```

The gate detects a paused/stale connector, the agent proposes a re-sync, and on
your approval it resumes the connector (`modify_connection`) and triggers a sync
(`sync_connection`) before it trusts a single row.

> _Screenshot of the Fivetran dashboard showing the connections goes here._

## The five leak families

| Leak family | What it catches |
| --- | --- |
| `failed_payments` | Failed charges never retried (involuntary churn) |
| `expired_cards` | Expired cards on still-active subscriptions |
| `usage_on_cancelled` | Active usage billed against a cancelled plan |
| `overdue_renewals` | Renewals past due with no invoice raised |
| `expired_discounts` | Discounts still applied months past expiry |

The seeded demo plants a fixed set of leaks totalling a memorable
**$18,650/yr** in recoverable revenue.

## Setup

```bash
pip install .                                   # 1. install deps (needs uv/uvx for the MCP)
cp .env.example .env                            # 2. fill in GCP + Fivetran creds
git clone https://github.com/fivetran/fivetran-mcp vendor/fivetran-mcp  # 3. vendor the MCP
python scripts/seed_bigquery.py                 # 4. seed the deterministic demo data
adk web                                          # 5. run the agent locally
```

Then ask: _“Audit my revenue for leaks across all five leak families.”_ Watch it
gate on the Fivetran connector, re-sync it, then return the ranked **$18,650/yr**
report — every finding with its $ exposure and SQL evidence.

> Requires [`uv`](https://docs.astral.sh/uv/) (provides `uvx`), which launches the
> Fivetran MCP in an isolated environment. The shipped agent runs on
> `gemini-2.5-pro` via Vertex AI; set `RG_MODEL` to override.

## Roadmap

- Promote the single agent to a `FreshnessGate` → `Auditor` two-agent sequence.
- Add write-back actions (auto-dunning, back-billing) behind human approval.
- Expand the leak library (proration errors, tax mismatches, FX drift).
- Scheduled audits with Slack/email digests for finance teams.

## License

[Apache-2.0](LICENSE).
