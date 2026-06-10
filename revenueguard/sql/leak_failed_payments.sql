-- LEAK FAMILY: failed_payments (involuntary churn)
-- A payment failed, was NEVER retried (retry_count = 0), the invoice is still
-- unpaid, and the subscription is still active. This is revenue we already
-- earned but silently never collected. amount_at_risk = the unpaid invoice.
SELECT
  s.customer_id,
  c.name                          AS customer_name,
  'failed_payments'               AS leak_family,
  i.invoice_id,
  p.payment_id,
  p.attempted_at,
  p.retry_count,
  i.amount                        AS amount_at_risk
FROM `{project}.{dataset}.payments` p
JOIN `{project}.{dataset}.invoices` i      ON p.invoice_id = i.invoice_id
JOIN `{project}.{dataset}.subscriptions` s ON i.subscription_id = s.subscription_id
JOIN `{project}.{dataset}.customers` c     ON s.customer_id = c.customer_id
WHERE p.status = 'failed'
  AND p.retry_count = 0
  AND i.status IN ('open', 'uncollectible')
  AND s.status = 'active'
ORDER BY amount_at_risk DESC
