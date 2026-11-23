-- Gold views over the silver tables.

CREATE OR REPLACE VIEW counted_committee_money AS
SELECT money.*, registry.committee_class, registry.kind
FROM committee_contributions AS money
JOIN committees AS registry USING (committee_id, cycle)
WHERE money.excluded_because IS NULL;

-- The money columns of total_accepted, per candidate ID and cycle.
-- individual_filed is weball as filed; individual counts each summary once.
CREATE OR REPLACE VIEW accepted_money AS
WITH committee_money AS (
    SELECT candidate_id, cycle,
        SUM(amount_cents) FILTER (committee_class = 'aipac')                AS aipac_pac_direct,
        SUM(amount_cents) FILTER (committee_class = 'aipac' AND is_earmark) AS aipac_earmark_transmitted,
        SUM(amount_cents) FILTER (committee_class = 'corporate')            AS corporate_pac,
        SUM(amount_cents) FILTER (committee_class = 'corporate' AND is_earmark) AS corporate_earmark_transmitted
    FROM counted_committee_money
    GROUP BY candidate_id, cycle
)
SELECT candidate_id, cycle,
    COALESCE(filed.individual_contributions_cents, 0)  AS individual_filed,
    COALESCE(summary.individual_contributions_cents, 0) AS individual,
    COALESCE(money.aipac_pac_direct, 0)                AS aipac_pac_direct,
    COALESCE(money.aipac_earmark_transmitted, 0)       AS aipac_earmark_transmitted,
    COALESCE(money.corporate_pac, 0)                   AS corporate_pac,
    COALESCE(money.corporate_earmark_transmitted, 0)   AS corporate_earmark_transmitted
FROM counted_summaries AS summary
JOIN candidate_summaries AS filed USING (candidate_id, cycle)
FULL OUTER JOIN committee_money AS money USING (candidate_id, cycle);

-- Counted committee money per candidate ID and cycle, by class and kind.
CREATE OR REPLACE VIEW committee_money_by_class AS
SELECT candidate_id, cycle, committee_class, kind,
    SUM(amount_cents)                              AS amount_cents,
    COALESCE(SUM(amount_cents) FILTER (is_earmark), 0) AS earmark_cents
FROM counted_committee_money
GROUP BY candidate_id, cycle, committee_class, kind;

-- Candidate IDs that appear anywhere in weball or pas2.
CREATE OR REPLACE VIEW candidates_on_file AS
SELECT candidate_id FROM candidate_summaries
UNION
SELECT candidate_id FROM committee_contributions;
