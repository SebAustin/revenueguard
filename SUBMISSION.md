# RevenueGuard — Devpost Submission

**Tagline:** An agentic revenue-leak auditor for B2B SaaS finance teams — it verifies your data is fresh *before* it trusts it.

**Try it out:** Live demo → `<CLOUD_RUN_URL>` · GitHub → `<REPO_URL>` · Video → `<VIDEO_URL>`

---

## Inspiration

B2B SaaS companies leak 2–5% of revenue to billing errors they never see — failed payments that were never retried, expired cards on active subscriptions, usage billed against cancelled plans, renewals that silently never invoiced, discounts that outlived their expiry. The brutal irony: most leak-detection tools audit **stale data**, so they cry wolf. Finance and RevOps teams stop trusting the alerts, and the real money keeps draining. I wanted an agent that earns trust by checking the pipeline *first*.

## What it does

RevenueGuard is an autonomous agent that runs a strict **verify → audit → report** loop. Before it audits anything, it uses the Fivetran MCP to confirm the billing connector synced recently and is healthy — if it's stale or paused, it stops, says so, and (with your approval) re-syncs. Only then does it run multi-step leak detection over the landed data in BigQuery across five leak families, and returns a ranked report with the dollar exposure, SQL evidence, and a recommended action for every finding. The human stays in control: it proposes, you approve any write.

## How I built it

- **Gemini 2.5 Pro** (via Vertex AI) — the reasoning engine that drives the audit loop and tool calls.
- **Google Cloud Agent Builder / ADK** (`google-adk`) — the code-first agent (`LlmAgent`) whose instruction enforces the verify→audit→report sequence.
- **Fivetran MCP** (`github.com/fivetran/fivetran-mcp`) — launched over stdio via `uvx`; the freshness gate calls `list_connections` / `get_connection_details`, and on approval `modify_connection` + `sync_connection` to resume and re-sync.
- **BigQuery** — the warehouse holding Fivetran-shaped billing tables; five deterministic SQL queries detect the leak families.
- **Cloud Run** — hosts the public web app.

## Challenges I ran into

- **Making Fivetran load-bearing, not decorative.** The freshness gate had to sit on the critical path of every audit. I wired the real MCP tools so the agent literally refuses to audit a paused connector and re-syncs it live.
- **A flaky live demo.** Live MCP calls exceed ADK's ~5s default timeout (raised to 60s), and a re-sync doesn't finish instantly — so the agent now triggers the refresh and proceeds rather than dead-ending on a wait.
- **Deterministic numbers.** The demo plants a fixed set of leaks that sum to exactly **$18,650/yr** so the report is identical every run.

## Accomplishments I'm proud of

A genuinely real pipeline — Fivetran → BigQuery — with an agent that catches a stale connector, fixes it, and returns a precise, evidence-backed leak report that totals $18,650/yr, all while keeping a human in the loop for every write.

## What's next

- Promote the single agent to a `FreshnessGate` → `Auditor` two-agent sequence.
- Write-back actions (auto-dunning, back-billing) behind human approval.
- Scheduled audits with Slack/email digests, and a business case: recover 2–5% of ARR that finance teams can't currently see.

## Built with

`gemini-2.5-pro` · vertex-ai · google-adk · google-cloud-agent-builder · fivetran · model-context-protocol · bigquery · cloud-run · python · uv
