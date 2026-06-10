-- LEAK FAMILY: overdue_renewals
-- The subscription's renewal date has passed but NO invoice was ever raised for
-- the new term. Revenue that should have been billed on renewal silently wasn't.
-- amount_at_risk = the subscription's annual value (the un-billed renewal term).
SELECT
  s.customer_id,
  c.name                                         AS customer_name,
  'overdue_renewals'                             AS leak_family,
  s.subscription_id,
  s.renewal_date,
  DATE_DIFF(DATE '{as_of}', s.renewal_date, DAY) AS days_overdue,
  s.annual_value                                 AS amount_at_risk
FROM `{project}.{dataset}.subscriptions` s
JOIN `{project}.{dataset}.customers` c ON s.customer_id = c.customer_id
LEFT JOIN `{project}.{dataset}.invoices` i
       ON i.subscription_id = s.subscription_id
      AND i.issued_date >= s.renewal_date
WHERE s.status = 'active'
  AND s.renewal_date < DATE '{as_of}'
  AND i.invoice_id IS NULL
ORDER BY amount_at_risk DESC
