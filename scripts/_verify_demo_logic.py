"""Offline verification: replicate each leak SQL's semantics in Python against the
seed rows, then run the real reporting tools. Asserts the $18,650 demo headline.
Run: python scripts/_verify_demo_logic.py  (no GCP needed). Safe to delete."""
import datetime as dt
import importlib.util
import os
import sys
import types

# Stub google.cloud.bigquery so the seed module imports without the real SDK.
g = types.ModuleType("google"); gc = types.ModuleType("google.cloud")
bq = types.ModuleType("google.cloud.bigquery")
bq.SchemaField = lambda *a, **k: ("field", a, k)
bq.Client = object; bq.Dataset = object; bq.LoadJobConfig = object
sys.modules.update({"google": g, "google.cloud": gc, "google.cloud.bigquery": bq})
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "verify")

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
def _load(name, relpath):
    sp = importlib.util.spec_from_file_location(name, os.path.join(root, relpath))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

seed = _load("seed", "scripts/seed_bigquery.py")
# Load reporting_tools directly by path to skip the package __init__ (which imports ADK).
_rt = _load("reporting_tools", "revenueguard/tools/reporting_tools.py")
build_report, compute_exposure = _rt.build_report, _rt.compute_exposure

AS_OF = dt.date(2026, 6, 8)
def d(s): return dt.date.fromisoformat(s) if s else None

subs = {s["subscription_id"]: s for s in seed.SUBSCRIPTIONS}
invs = {i["invoice_id"]: i for i in seed.INVOICES}
custs = {c["customer_id"]: c for c in seed.CUSTOMERS}

def failed_payments():
    out = []
    for p in seed.PAYMENTS:
        if p["status"] != "failed" or p["retry_count"] != 0:
            continue
        i = invs[p["invoice_id"]]
        if i["status"] not in ("open", "uncollectible"):
            continue
        s = subs[i["subscription_id"]]
        if s["status"] != "active":
            continue
        out.append({"customer_id": s["customer_id"], "customer_name": custs[s["customer_id"]]["name"],
                    "leak_family": "failed_payments", "invoice_id": i["invoice_id"], "amount_at_risk": i["amount"]})
    return out

def expired_cards():
    out = []
    for pm in seed.PAYMENT_METHODS:
        if not pm["is_default"]:
            continue
        for s in seed.SUBSCRIPTIONS:
            if s["customer_id"] != pm["customer_id"] or s["status"] != "active":
                continue
            if dt.date(pm["exp_year"], pm["exp_month"], 1) < AS_OF.replace(day=1):
                out.append({"customer_id": s["customer_id"], "customer_name": custs[s["customer_id"]]["name"],
                            "leak_family": "expired_cards", "card_last4": pm["card_last4"], "amount_at_risk": s["annual_value"]})
    return out

def usage_on_cancelled():
    agg = {}
    for u in seed.USAGE_EVENTS:
        s = subs[u["subscription_id"]]
        if s["status"] != "cancelled" or not (d(u["usage_date"]) > d(s["cancelled_at"])):
            continue
        agg.setdefault(s["subscription_id"], 0.0)
        agg[s["subscription_id"]] += u["quantity"] * u["unit_price"]
    out = []
    for sid, amt in agg.items():
        if amt > 0:
            s = subs[sid]
            out.append({"customer_id": s["customer_id"], "customer_name": custs[s["customer_id"]]["name"],
                        "leak_family": "usage_on_cancelled", "subscription_id": sid, "amount_at_risk": amt})
    return out

def overdue_renewals():
    out = []
    for s in seed.SUBSCRIPTIONS:
        if s["status"] != "active" or not (d(s["renewal_date"]) < AS_OF):
            continue
        has_inv = any(i["subscription_id"] == s["subscription_id"] and d(i["issued_date"]) >= d(s["renewal_date"])
                      for i in seed.INVOICES)
        if not has_inv:
            out.append({"customer_id": s["customer_id"], "customer_name": custs[s["customer_id"]]["name"],
                        "leak_family": "overdue_renewals", "subscription_id": s["subscription_id"], "amount_at_risk": s["annual_value"]})
    return out

def expired_discounts():
    out = []
    for dc in seed.DISCOUNTS:
        s = subs[dc["subscription_id"]]
        if s["status"] != "active" or not (d(dc["valid_until"]) < AS_OF):
            continue
        out.append({"customer_id": s["customer_id"], "customer_name": custs[s["customer_id"]]["name"],
                    "leak_family": "expired_discounts", "coupon_code": dc["coupon_code"],
                    "amount_at_risk": round(s["annual_value"] * dc["percent_off"] / 100, 2)})
    return out

families = [failed_payments(), expired_cards(), usage_on_cancelled(), overdue_renewals(), expired_discounts()]
all_findings = [f for fam in families for f in fam]

EXPECT = {"failed_payments": (3, 2400.0), "expired_cards": (2, 1800.0),
          "usage_on_cancelled": (1, 12000.0), "overdue_renewals": (2, 2000.0),
          "expired_discounts": (1, 450.0)}

exposure = compute_exposure(all_findings)
print("Per-family results:")
ok = True
for fam, (ecount, eamt) in EXPECT.items():
    b = exposure["by_family"].get(fam, {"count": 0, "exposure": 0.0})
    status = "OK" if (b["count"] == ecount and abs(b["exposure"] - eamt) < 0.01) else "MISMATCH"
    ok = ok and status == "OK"
    print(f"  [{status}] {fam:<20} count={b['count']} (exp {ecount})  ${b['exposure']:,.2f} (exp ${eamt:,.2f})")

print(f"\nGrand total: ${exposure['grand_total_annual']:,.2f}  (expected $18,650.00)")
assert ok and abs(exposure["grand_total_annual"] - 18650.0) < 0.01, "DEMO MATH FAILED"
print("\nAll assertions passed.\n")
print(build_report(all_findings, exposure)["headline"])
