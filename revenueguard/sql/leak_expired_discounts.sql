-- LEAK FAMILY: expired_discounts
-- A discount is still attached to an active subscription months after it expired,
-- so every invoice cycle leaks the discounted amount. amount_at_risk = the annual
-- value of the discount that should no longer apply.
SELECT
  s.customer_id,
  c.name                                          AS customer_name,
  'expired_discounts'                             AS leak_family,
  d.coupon_code,
  d.percent_off,
  d.valid_until,
  DATE_DIFF(DATE '{as_of}', d.valid_until, DAY)   AS days_expired,
  ROUND(s.annual_value * d.percent_off / 100, 2)  AS amount_at_risk
FROM `{project}.{dataset}.discounts` d
JOIN `{project}.{dataset}.subscriptions` s ON d.subscription_id = s.subscription_id
JOIN `{project}.{dataset}.customers` c     ON s.customer_id = c.customer_id
WHERE s.status = 'active'
  AND d.valid_until < DATE '{as_of}'
ORDER BY amount_at_risk DESC
