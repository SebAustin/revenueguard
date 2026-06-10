"""Deterministic reporting tools — NO LLM calls inside.

compute_exposure totals the $ at risk; build_report ranks the families and emits
both a human-readable markdown report and a machine-readable JSON structure. The
amount_at_risk emitted by each leak SQL is already an ANNUAL figure, so the grand
total is the headline annualized recoverable leak.
"""

# Stable display order / labels for the five leak families.
_FAMILY_LABELS = {
    "failed_payments": "Failed payments never retried",
    "expired_cards": "Expired cards on active subscriptions",
    "usage_on_cancelled": "Active usage on cancelled plans",
    "overdue_renewals": "Renewals past due with no invoice",
    "expired_discounts": "Discounts applied past expiry",
}

# Recommended remediation per family — shown in the report's Action column.
_FAMILY_ACTIONS = {
    "failed_payments": "Trigger dunning / retry the failed charge",
    "expired_cards": "Request an updated card before the next renewal",
    "usage_on_cancelled": "Back-bill the un-billed usage or hard-stop access",
    "overdue_renewals": "Raise the missing renewal invoice",
    "expired_discounts": "Remove the expired coupon from the subscription",
}


def compute_exposure(findings: list) -> dict:
    """Total the annual $ exposure across all leak findings.

    Args:
        findings: a flat list of finding dicts. Each finding must carry a
                  'leak_family' and an 'amount_at_risk' (annualized $).

    Returns:
        dict with by_family (family -> {count, exposure}), grand_total_annual,
        and finding_count.
    """
    by_family: dict = {}
    for f in findings:
        fam = f.get("leak_family", "unknown")
        amt = float(f.get("amount_at_risk", 0) or 0)
        bucket = by_family.setdefault(fam, {"count": 0, "exposure": 0.0})
        bucket["count"] += 1
        bucket["exposure"] = round(bucket["exposure"] + amt, 2)

    grand_total = round(sum(b["exposure"] for b in by_family.values()), 2)
    return {
        "by_family": by_family,
        "grand_total_annual": grand_total,
        "finding_count": len(findings),
    }


def build_report(findings: list, exposure: dict) -> dict:
    """Build a ranked leak report (markdown + JSON) from findings and exposure.

    Args:
        findings: flat list of finding dicts (see compute_exposure).
        exposure: the dict returned by compute_exposure.

    Returns:
        dict with keys: headline, markdown, json.
    """
    by_family = exposure.get("by_family", {})
    grand_total = exposure.get("grand_total_annual", 0.0)
    # Rank families by $ exposure, descending — biggest leaks first.
    ranked = sorted(by_family.items(), key=lambda kv: kv[1]["exposure"], reverse=True)

    n = exposure.get("finding_count", 0)
    headline = (
        f"${grand_total:,.0f}/yr in recoverable revenue leaks "
        f"across {n} finding{'' if n == 1 else 's'}"
    )

    lines = [
        "# RevenueGuard — Leak Audit Report",
        "",
        f"**Total exposure: {headline}**",
        "",
        "| Rank | Leak family | Findings | Annual exposure | Recommended action |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for i, (fam, bucket) in enumerate(ranked, start=1):
        lines.append(
            f"| {i} | {_FAMILY_LABELS.get(fam, fam)} | {bucket['count']} | "
            f"${bucket['exposure']:,.2f} | {_FAMILY_ACTIONS.get(fam, '—')} |"
        )

    lines += ["", "## Evidence by finding", ""]
    for fam, _ in ranked:
        lines.append(f"### {_FAMILY_LABELS.get(fam, fam)}")
        for f in [x for x in findings if x.get("leak_family") == fam]:
            cust = f.get("customer_name", f.get("customer_id", "?"))
            amt = float(f.get("amount_at_risk", 0) or 0)
            evidence = ", ".join(
                f"{k}={v}"
                for k, v in f.items()
                if k not in ("customer_name", "leak_family", "amount_at_risk")
            )
            lines.append(f"- **{cust}** — ${amt:,.2f} at risk  \n  `{evidence}`")
        lines.append("")

    return {
        "headline": headline,
        "markdown": "\n".join(lines),
        "json": {
            "grand_total_annual": grand_total,
            "by_family": by_family,
            "findings": findings,
        },
    }
