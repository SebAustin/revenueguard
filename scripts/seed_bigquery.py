#!/usr/bin/env python3
"""Seed the RevenueGuard demo dataset in BigQuery with DETERMINISTIC planted leaks.

Run once before the demo:

    export GOOGLE_CLOUD_PROJECT=your-project
    python scripts/seed_bigquery.py

It drops + recreates the `revenueguard_demo` dataset and loads Fivetran-shaped
landed tables (customers, subscriptions, invoices, payments, payment_methods,
usage_events, discounts) with a fixed set of leaks anchored to as-of 2026-06-08.

Planted exposure (must total $18,650/yr — the demo headline):
    failed_payments     3 findings   $2,400   (3 x $800 unpaid invoices)
    expired_cards       2 findings   $1,800   (2 x $900 annual value)
    usage_on_cancelled  1 finding   $12,000   (un-billed usage, big ticket)
    overdue_renewals    2 findings   $2,000   (2 x $1,000 annual value)
    expired_discounts   1 finding      $450   (15% off a $3,000/yr sub)
    ----------------------------------------------------------------
    TOTAL                            $18,650

Control rows (must NOT be flagged) are included so the SQL has to discriminate:
a clean active customer, a retried failed payment, a cancelled sub with only
pre-cancellation usage, a still-valid discount, and valid cards.
"""

import os

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
DATASET = os.environ.get("RG_DATASET", "revenueguard_demo")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "US")
AS_OF = os.environ.get("RG_AS_OF_DATE", "2026-06-08")
SYNCED = f"{AS_OF}T06:00:00Z"  # uniform Fivetran landed-at timestamp

S = bigquery.SchemaField

SCHEMAS = {
    "customers": [
        S("customer_id", "STRING"), S("name", "STRING"), S("email", "STRING"),
        S("created_at", "DATE"), S("_fivetran_synced", "TIMESTAMP"),
    ],
    "subscriptions": [
        S("subscription_id", "STRING"), S("customer_id", "STRING"),
        S("plan_name", "STRING"), S("status", "STRING"),
        S("mrr", "FLOAT64"), S("annual_value", "FLOAT64"),
        S("current_period_start", "DATE"), S("current_period_end", "DATE"),
        S("renewal_date", "DATE"), S("cancelled_at", "DATE"),
        S("_fivetran_synced", "TIMESTAMP"),
    ],
    "invoices": [
        S("invoice_id", "STRING"), S("subscription_id", "STRING"),
        S("customer_id", "STRING"), S("amount", "FLOAT64"), S("status", "STRING"),
        S("issued_date", "DATE"), S("due_date", "DATE"), S("paid_at", "DATE"),
        S("_fivetran_synced", "TIMESTAMP"),
    ],
    "payments": [
        S("payment_id", "STRING"), S("invoice_id", "STRING"),
        S("customer_id", "STRING"), S("amount", "FLOAT64"), S("status", "STRING"),
        S("attempted_at", "TIMESTAMP"), S("retry_count", "INT64"),
        S("_fivetran_synced", "TIMESTAMP"),
    ],
    "payment_methods": [
        S("payment_method_id", "STRING"), S("customer_id", "STRING"),
        S("card_brand", "STRING"), S("card_last4", "STRING"),
        S("exp_month", "INT64"), S("exp_year", "INT64"), S("is_default", "BOOL"),
        S("_fivetran_synced", "TIMESTAMP"),
    ],
    "usage_events": [
        S("usage_id", "STRING"), S("customer_id", "STRING"),
        S("subscription_id", "STRING"), S("usage_date", "DATE"),
        S("quantity", "FLOAT64"), S("unit_price", "FLOAT64"),
        S("_fivetran_synced", "TIMESTAMP"),
    ],
    "discounts": [
        S("discount_id", "STRING"), S("customer_id", "STRING"),
        S("subscription_id", "STRING"), S("coupon_code", "STRING"),
        S("percent_off", "FLOAT64"), S("valid_from", "DATE"),
        S("valid_until", "DATE"), S("_fivetran_synced", "TIMESTAMP"),
    ],
}


def _sync(rows: list) -> list:
    """Stamp every row with the uniform Fivetran landed-at timestamp."""
    for r in rows:
        r["_fivetran_synced"] = SYNCED
    return rows


CUSTOMERS = _sync([
    {"customer_id": "C001", "name": "Northwind Traders", "email": "ap@northwind.example", "created_at": "2024-02-01"},
    {"customer_id": "C002", "name": "Globex Corp",       "email": "ap@globex.example",    "created_at": "2024-03-15"},
    {"customer_id": "C003", "name": "Initech",           "email": "ap@initech.example",   "created_at": "2024-05-20"},
    {"customer_id": "C004", "name": "Umbrella Analytics","email": "ap@umbrella.example",  "created_at": "2024-06-10"},
    {"customer_id": "C005", "name": "Hooli",             "email": "ap@hooli.example",     "created_at": "2024-07-01"},
    {"customer_id": "C006", "name": "Vandelay Industries","email": "ap@vandelay.example", "created_at": "2023-11-05"},
    {"customer_id": "C007", "name": "Wonka SaaS",        "email": "ap@wonka.example",     "created_at": "2024-01-12"},
    {"customer_id": "C008", "name": "Stark Cloud",       "email": "ap@stark.example",     "created_at": "2024-04-18"},
    {"customer_id": "C009", "name": "Acme Cloud",        "email": "ap@acme.example",      "created_at": "2024-08-22"},
    {"customer_id": "C010", "name": "Soylent Data",      "email": "ap@soylent.example",   "created_at": "2023-09-30"},
])

# annual_value drives expired_cards / overdue_renewals / expired_discounts exposure.
SUBSCRIPTIONS = _sync([
    # --- failed_payments customers (active) ---
    {"subscription_id": "S001", "customer_id": "C001", "plan_name": "Growth",     "status": "active",    "mrr": 250.0,  "annual_value": 3000.0,  "current_period_start": "2026-05-08", "current_period_end": "2026-06-08", "renewal_date": "2026-06-08", "cancelled_at": None},
    {"subscription_id": "S002", "customer_id": "C002", "plan_name": "Growth",     "status": "active",    "mrr": 200.0,  "annual_value": 2400.0,  "current_period_start": "2026-05-25", "current_period_end": "2026-06-25", "renewal_date": "2026-07-01", "cancelled_at": None},
    {"subscription_id": "S003", "customer_id": "C003", "plan_name": "Starter",    "status": "active",    "mrr": 150.0,  "annual_value": 1800.0,  "current_period_start": "2026-05-15", "current_period_end": "2026-06-15", "renewal_date": "2026-07-15", "cancelled_at": None},
    # --- expired_cards customers (active, annual_value 900 each) ---
    {"subscription_id": "S004", "customer_id": "C004", "plan_name": "Starter",    "status": "active",    "mrr": 75.0,   "annual_value": 900.0,   "current_period_start": "2026-06-01", "current_period_end": "2026-07-01", "renewal_date": "2026-08-01", "cancelled_at": None},
    {"subscription_id": "S005", "customer_id": "C005", "plan_name": "Starter",    "status": "active",    "mrr": 75.0,   "annual_value": 900.0,   "current_period_start": "2026-06-01", "current_period_end": "2026-07-01", "renewal_date": "2026-09-01", "cancelled_at": None},
    # --- usage_on_cancelled big-ticket (cancelled 2026-03-01) ---
    {"subscription_id": "S006", "customer_id": "C006", "plan_name": "Enterprise", "status": "cancelled", "mrr": 1000.0, "annual_value": 12000.0, "current_period_start": "2026-02-01", "current_period_end": "2026-03-01", "renewal_date": "2026-03-01", "cancelled_at": "2026-03-01"},
    # --- overdue_renewals customers (active, renewal in the past, no new invoice) ---
    {"subscription_id": "S007", "customer_id": "C007", "plan_name": "Team",       "status": "active",    "mrr": 83.33,  "annual_value": 1000.0,  "current_period_start": "2026-04-10", "current_period_end": "2026-05-10", "renewal_date": "2026-05-10", "cancelled_at": None},
    {"subscription_id": "S008", "customer_id": "C008", "plan_name": "Team",       "status": "active",    "mrr": 83.33,  "annual_value": 1000.0,  "current_period_start": "2026-03-20", "current_period_end": "2026-04-20", "renewal_date": "2026-04-20", "cancelled_at": None},
    # --- CONTROL: clean active customer (must NOT be flagged) ---
    {"subscription_id": "S009", "customer_id": "C009", "plan_name": "Growth",     "status": "active",    "mrr": 300.0,  "annual_value": 3600.0,  "current_period_start": "2026-06-01", "current_period_end": "2026-07-01", "renewal_date": "2026-12-01", "cancelled_at": None},
    # --- CONTROL: cancelled sub with ONLY pre-cancellation usage (must NOT be flagged) ---
    {"subscription_id": "S010", "customer_id": "C010", "plan_name": "Team",       "status": "cancelled", "mrr": 400.0,  "annual_value": 4800.0,  "current_period_start": "2026-03-01", "current_period_end": "2026-04-01", "renewal_date": "2026-04-01", "cancelled_at": "2026-04-01"},
])

INVOICES = _sync([
    # Failed-payment invoices: unpaid, $800 each (amount_at_risk).
    {"invoice_id": "I001", "subscription_id": "S001", "customer_id": "C001", "amount": 800.0, "status": "open", "issued_date": "2026-05-13", "due_date": "2026-05-20", "paid_at": None},
    {"invoice_id": "I002", "subscription_id": "S002", "customer_id": "C002", "amount": 800.0, "status": "open", "issued_date": "2026-05-18", "due_date": "2026-05-25", "paid_at": None},
    {"invoice_id": "I003", "subscription_id": "S003", "customer_id": "C003", "amount": 800.0, "status": "open", "issued_date": "2026-05-21", "due_date": "2026-05-28", "paid_at": None},
    # Clean paid invoice for the control customer.
    {"invoice_id": "I004", "subscription_id": "S009", "customer_id": "C009", "amount": 300.0, "status": "paid", "issued_date": "2026-06-01", "due_date": "2026-06-08", "paid_at": "2026-06-02"},
    # Overdue-renewal subs DID have an old invoice BEFORE the renewal date, but
    # none on/after it — that absence is the leak.
    {"invoice_id": "I005", "subscription_id": "S007", "customer_id": "C007", "amount": 83.33, "status": "paid", "issued_date": "2026-04-01", "due_date": "2026-04-10", "paid_at": "2026-04-03"},
    {"invoice_id": "I006", "subscription_id": "S008", "customer_id": "C008", "amount": 83.33, "status": "paid", "issued_date": "2026-03-15", "due_date": "2026-03-20", "paid_at": "2026-03-17"},
    # CONTROL: an unpaid invoice whose payment WAS retried (see P005) — excluded.
    {"invoice_id": "I007", "subscription_id": "S009", "customer_id": "C009", "amount": 300.0, "status": "open", "issued_date": "2026-05-30", "due_date": "2026-06-06", "paid_at": None},
])

PAYMENTS = _sync([
    # Failed + never retried (retry_count = 0) → the 3 flagged leaks.
    {"payment_id": "P001", "invoice_id": "I001", "customer_id": "C001", "amount": 800.0, "status": "failed",    "attempted_at": "2026-05-21T09:00:00Z", "retry_count": 0},
    {"payment_id": "P002", "invoice_id": "I002", "customer_id": "C002", "amount": 800.0, "status": "failed",    "attempted_at": "2026-05-26T09:00:00Z", "retry_count": 0},
    {"payment_id": "P003", "invoice_id": "I003", "customer_id": "C003", "amount": 800.0, "status": "failed",    "attempted_at": "2026-05-29T09:00:00Z", "retry_count": 0},
    # Clean succeeded payment.
    {"payment_id": "P004", "invoice_id": "I004", "customer_id": "C009", "amount": 300.0, "status": "succeeded", "attempted_at": "2026-06-02T09:00:00Z", "retry_count": 0},
    # CONTROL: failed BUT retried 3x → excluded by retry_count = 0 filter.
    {"payment_id": "P005", "invoice_id": "I007", "customer_id": "C009", "amount": 300.0, "status": "failed",    "attempted_at": "2026-06-01T09:00:00Z", "retry_count": 3},
])

PAYMENT_METHODS = _sync([
    {"payment_method_id": "PM001", "customer_id": "C001", "card_brand": "visa",       "card_last4": "4242", "exp_month": 5,  "exp_year": 2028, "is_default": True},
    {"payment_method_id": "PM002", "customer_id": "C002", "card_brand": "visa",       "card_last4": "1881", "exp_month": 11, "exp_year": 2027, "is_default": True},
    {"payment_method_id": "PM003", "customer_id": "C003", "card_brand": "mastercard", "card_last4": "5100", "exp_month": 1,  "exp_year": 2029, "is_default": True},
    # EXPIRED cards on active subs → 2 flagged leaks.
    {"payment_method_id": "PM004", "customer_id": "C004", "card_brand": "visa",       "card_last4": "0004", "exp_month": 1,  "exp_year": 2026, "is_default": True},
    {"payment_method_id": "PM005", "customer_id": "C005", "card_brand": "amex",       "card_last4": "0005", "exp_month": 12, "exp_year": 2025, "is_default": True},
    {"payment_method_id": "PM006", "customer_id": "C006", "card_brand": "visa",       "card_last4": "0006", "exp_month": 1,  "exp_year": 2027, "is_default": True},
    {"payment_method_id": "PM007", "customer_id": "C007", "card_brand": "visa",       "card_last4": "0007", "exp_month": 3,  "exp_year": 2028, "is_default": True},
    {"payment_method_id": "PM008", "customer_id": "C008", "card_brand": "mastercard", "card_last4": "0008", "exp_month": 7,  "exp_year": 2027, "is_default": True},
    {"payment_method_id": "PM009", "customer_id": "C009", "card_brand": "visa",       "card_last4": "0009", "exp_month": 1,  "exp_year": 2030, "is_default": True},
    {"payment_method_id": "PM010", "customer_id": "C010", "card_brand": "visa",       "card_last4": "0010", "exp_month": 2,  "exp_year": 2027, "is_default": True},
])

# C006: $12,000 of usage AFTER cancellation (2026-03-01). unit_price 2.0, qty 1500 x 4 = 12,000.
# Plus one PRE-cancellation event that must be excluded.
USAGE_EVENTS = _sync([
    {"usage_id": "U001", "customer_id": "C006", "subscription_id": "S006", "usage_date": "2026-02-15", "quantity": 1000.0, "unit_price": 2.0},  # pre-cancel: excluded
    {"usage_id": "U002", "customer_id": "C006", "subscription_id": "S006", "usage_date": "2026-03-15", "quantity": 1500.0, "unit_price": 2.0},
    {"usage_id": "U003", "customer_id": "C006", "subscription_id": "S006", "usage_date": "2026-04-15", "quantity": 1500.0, "unit_price": 2.0},
    {"usage_id": "U004", "customer_id": "C006", "subscription_id": "S006", "usage_date": "2026-05-15", "quantity": 1500.0, "unit_price": 2.0},
    {"usage_id": "U005", "customer_id": "C006", "subscription_id": "S006", "usage_date": "2026-06-05", "quantity": 1500.0, "unit_price": 2.0},
    # CONTROL: C010 cancelled 2026-04-01 with ONLY pre-cancel usage → excluded.
    {"usage_id": "U006", "customer_id": "C010", "subscription_id": "S010", "usage_date": "2026-03-10", "quantity": 500.0,  "unit_price": 2.0},
    # CONTROL: C009 active usage → excluded (sub not cancelled).
    {"usage_id": "U007", "customer_id": "C009", "subscription_id": "S009", "usage_date": "2026-06-01", "quantity": 100.0,  "unit_price": 2.0},
])

DISCOUNTS = _sync([
    # Expired 2026-02-08 (4 months ago) but still on active sub S001 → flagged. 15% of $3,000 = $450.
    {"discount_id": "D001", "customer_id": "C001", "subscription_id": "S001", "coupon_code": "LAUNCH15",  "percent_off": 15.0, "valid_from": "2025-08-08", "valid_until": "2026-02-08"},
    # CONTROL: still valid through end of year → excluded.
    {"discount_id": "D002", "customer_id": "C009", "subscription_id": "S009", "coupon_code": "PARTNER10", "percent_off": 10.0, "valid_from": "2026-01-01", "valid_until": "2026-12-31"},
])

TABLES = {
    "customers": CUSTOMERS,
    "subscriptions": SUBSCRIPTIONS,
    "invoices": INVOICES,
    "payments": PAYMENTS,
    "payment_methods": PAYMENT_METHODS,
    "usage_events": USAGE_EVENTS,
    "discounts": DISCOUNTS,
}


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    dataset_id = f"{PROJECT}.{DATASET}"

    print(f"Recreating dataset {dataset_id} (location={LOCATION}) ...")
    client.delete_dataset(dataset_id, delete_contents=True, not_found_ok=True)
    ds = bigquery.Dataset(dataset_id)
    ds.location = LOCATION
    client.create_dataset(ds)

    for name, rows in TABLES.items():
        table_id = f"{dataset_id}.{name}"
        job_config = bigquery.LoadJobConfig(
            schema=SCHEMAS[name],
            write_disposition="WRITE_TRUNCATE",
        )
        client.load_table_from_json(rows, table_id, job_config=job_config).result()
        print(f"  loaded {len(rows):>3} rows -> {name}")

    print(
        "\nDone. Planted exposure should total $18,650/yr:\n"
        "  failed_payments    $2,400 | expired_cards   $1,800\n"
        "  usage_on_cancelled $12,000 | overdue_renewals $2,000\n"
        "  expired_discounts    $450\n"
        f"As-of date: {AS_OF}. Make ONE Fivetran connector stale (>24h) for the gate demo."
    )


if __name__ == "__main__":
    main()
