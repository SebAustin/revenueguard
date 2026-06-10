-- LEAK FAMILY: expired_cards
-- The default card on a still-active subscription has already expired, so the
-- next renewal charge will bounce. amount_at_risk = the subscription's annual
-- value (the contract we will lose to involuntary churn if not fixed).
SELECT
  s.customer_id,
  c.name                                       AS customer_name,
  'expired_cards'                              AS leak_family,
  pm.payment_method_id,
  pm.card_brand,
  pm.card_last4,
  FORMAT('%02d/%d', pm.exp_month, pm.exp_year) AS card_expiry,
  s.annual_value                               AS amount_at_risk
FROM `{project}.{dataset}.payment_methods` pm
JOIN `{project}.{dataset}.subscriptions` s ON pm.customer_id = s.customer_id
JOIN `{project}.{dataset}.customers` c     ON s.customer_id = c.customer_id
WHERE pm.is_default = TRUE
  AND s.status = 'active'
  AND DATE(pm.exp_year, pm.exp_month, 1) < DATE_TRUNC(DATE '{as_of}', MONTH)
ORDER BY amount_at_risk DESC
