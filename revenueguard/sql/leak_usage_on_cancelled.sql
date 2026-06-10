-- LEAK FAMILY: usage_on_cancelled (un-billed usage — the big-ticket leak)
-- The product is still being consumed AFTER the subscription was cancelled,
-- and nothing is invoicing that usage. amount_at_risk = the un-billed usage
-- value accrued since the cancellation date.
SELECT
  s.customer_id,
  c.name                              AS customer_name,
  'usage_on_cancelled'                AS leak_family,
  s.subscription_id,
  s.cancelled_at,
  COUNT(*)                            AS usage_events,
  SUM(u.quantity * u.unit_price)      AS amount_at_risk
FROM `{project}.{dataset}.usage_events` u
JOIN `{project}.{dataset}.subscriptions` s ON u.subscription_id = s.subscription_id
JOIN `{project}.{dataset}.customers` c     ON s.customer_id = c.customer_id
WHERE s.status = 'cancelled'
  AND u.usage_date > s.cancelled_at
GROUP BY s.customer_id, c.name, s.subscription_id, s.cancelled_at
HAVING amount_at_risk > 0
ORDER BY amount_at_risk DESC
