"""BigQuery audit tool — runs the revenue-leak detection SQL over landed data.

This is the data-side muscle of RevenueGuard. Each leak family maps to one
deterministic SQL file in ../sql. The agent calls `bigquery_run_audit` once per
family AFTER the Fivetran freshness gate has confirmed the source is healthy.
"""

import datetime
import decimal
import os
import pathlib

from google.cloud import bigquery

_SQL_DIR = pathlib.Path(__file__).parent.parent / "sql"

_LEAK_FAMILIES = {
    "failed_payments": "leak_failed_payments.sql",
    "expired_cards": "leak_expired_cards.sql",
    "usage_on_cancelled": "leak_usage_on_cancelled.sql",
    "overdue_renewals": "leak_overdue_renewals.sql",
    "expired_discounts": "leak_expired_discounts.sql",
}


def _jsonify(value):
    """Coerce BigQuery cell values into JSON-serializable primitives.

    The tool return is serialized and handed back to Gemini, so Decimal / date /
    datetime must become float / str first.
    """
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def get_leak_query(leak_family: str) -> dict:
    """Return the exact SQL query used to detect one leak family (for transparency).

    Args:
        leak_family: one of failed_payments, expired_cards, usage_on_cancelled,
                     overdue_renewals, expired_discounts.

    Returns:
        dict with keys: leak_family, sql (the rendered query, ready to run).
    """
    if leak_family not in _LEAK_FAMILIES:
        return {
            "error": f"unknown leak_family '{leak_family}'. "
            f"choose from {list(_LEAK_FAMILIES)}"
        }
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    dataset = os.environ.get("RG_DATASET", "revenueguard_demo")
    as_of = os.environ.get("RG_AS_OF_DATE", "2026-06-08")
    sql = (_SQL_DIR / _LEAK_FAMILIES[leak_family]).read_text().format(
        project=project, dataset=dataset, as_of=as_of
    )
    return {"leak_family": leak_family, "sql": sql}


def bigquery_run_audit(leak_family: str) -> dict:
    """Run one revenue-leak detection query over the landed BigQuery data.

    Args:
        leak_family: one of failed_payments, expired_cards, usage_on_cancelled,
                     overdue_renewals, expired_discounts.

    Returns:
        dict with keys: leak_family, row_count, exposure (sum of amount_at_risk
        across findings), and findings (a list of row dicts, each carrying its
        own amount_at_risk and SQL evidence columns).
    """
    if leak_family not in _LEAK_FAMILIES:
        return {
            "error": f"unknown leak_family '{leak_family}'. "
            f"choose from {list(_LEAK_FAMILIES)}"
        }

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    dataset = os.environ.get("RG_DATASET", "revenueguard_demo")
    as_of = os.environ.get("RG_AS_OF_DATE", "2026-06-08")

    sql = (_SQL_DIR / _LEAK_FAMILIES[leak_family]).read_text().format(
        project=project, dataset=dataset, as_of=as_of
    )

    client = bigquery.Client(project=project)
    findings = [
        {k: _jsonify(v) for k, v in dict(row).items()}
        for row in client.query(sql).result()
    ]
    exposure = round(sum(f.get("amount_at_risk", 0) or 0 for f in findings), 2)

    return {
        "leak_family": leak_family,
        "row_count": len(findings),
        "exposure": exposure,
        "findings": findings,
    }
