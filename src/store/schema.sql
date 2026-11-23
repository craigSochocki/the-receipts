-- Silver layer: cleaned facts, one table per grain, every FEC candidate
-- and committee. Totals are views, never stored. Money is whole cents.

CREATE TABLE people (
    person_key  VARCHAR PRIMARY KEY,
    full_name   VARCHAR NOT NULL,
    first_name  VARCHAR,
    last_name   VARCHAR
);

CREATE TABLE person_candidate_ids (
    person_key    VARCHAR NOT NULL,
    candidate_id  VARCHAR NOT NULL,
    position      INTEGER NOT NULL,  -- order on the person's record
    PRIMARY KEY (person_key, candidate_id)
);

CREATE TABLE candidate_summaries (  -- weball, as filed
    candidate_id                             VARCHAR NOT NULL,
    cycle                                    INTEGER NOT NULL,
    name                                     VARCHAR,
    office_state                             VARCHAR,
    office_district                          VARCHAR,
    party                                    VARCHAR,
    total_receipts_cents                     BIGINT NOT NULL,
    transfers_from_authorized_cents          BIGINT NOT NULL,
    total_disbursements_cents                BIGINT NOT NULL,
    transfers_to_authorized_cents            BIGINT NOT NULL,
    cash_start_cents                         BIGINT NOT NULL,
    cash_end_cents                           BIGINT NOT NULL,
    candidate_contributions_cents            BIGINT NOT NULL,
    candidate_loans_cents                    BIGINT NOT NULL,
    other_loans_cents                        BIGINT NOT NULL,
    candidate_loan_repayments_cents          BIGINT NOT NULL,
    other_loan_repayments_cents              BIGINT NOT NULL,
    debts_owed_by_cents                      BIGINT NOT NULL,
    individual_contributions_cents           BIGINT NOT NULL,
    other_committee_contributions_cents      BIGINT NOT NULL,
    coverage_end                             VARCHAR,
    PRIMARY KEY (candidate_id, cycle)
);

CREATE TABLE counted_summaries (  -- weball, each double-counted summary counted once
    candidate_id                             VARCHAR NOT NULL,
    cycle                                    INTEGER NOT NULL,
    name                                     VARCHAR,
    office_state                             VARCHAR,
    office_district                          VARCHAR,
    party                                    VARCHAR,
    total_receipts_cents                     BIGINT NOT NULL,
    transfers_from_authorized_cents          BIGINT NOT NULL,
    total_disbursements_cents                BIGINT NOT NULL,
    transfers_to_authorized_cents            BIGINT NOT NULL,
    cash_start_cents                         BIGINT NOT NULL,
    cash_end_cents                           BIGINT NOT NULL,
    candidate_contributions_cents            BIGINT NOT NULL,
    candidate_loans_cents                    BIGINT NOT NULL,
    other_loans_cents                        BIGINT NOT NULL,
    candidate_loan_repayments_cents          BIGINT NOT NULL,
    other_loan_repayments_cents              BIGINT NOT NULL,
    debts_owed_by_cents                      BIGINT NOT NULL,
    individual_contributions_cents           BIGINT NOT NULL,
    other_committee_contributions_cents      BIGINT NOT NULL,
    coverage_end                             VARCHAR,
    PRIMARY KEY (candidate_id, cycle)
);

CREATE TABLE summary_corrections (  -- every cell counted_summaries changed, and why
    person_key    VARCHAR NOT NULL,
    candidate_id  VARCHAR NOT NULL,
    cycle         INTEGER NOT NULL,
    field         VARCHAR NOT NULL,
    filed_cents   BIGINT NOT NULL,
    counted_cents BIGINT NOT NULL,
    kept_id       VARCHAR NOT NULL
);

CREATE TABLE committees (  -- cm
    committee_id       VARCHAR NOT NULL,
    cycle              INTEGER NOT NULL,
    name               VARCHAR,
    committee_type     VARCHAR,
    designation        VARCHAR,
    organization_type  VARCHAR,
    committee_class    VARCHAR NOT NULL,
    PRIMARY KEY (committee_id, cycle)
);

CREATE TABLE committee_contributions (  -- pas2, contributions to candidates
    committee_id     VARCHAR NOT NULL,
    candidate_id     VARCHAR NOT NULL,
    cycle            INTEGER NOT NULL,
    amount_cents     BIGINT NOT NULL,
    is_earmark       BOOLEAN NOT NULL,
    date             VARCHAR,
    excluded_because VARCHAR  -- NULL when counted
);

CREATE TABLE outside_spending (  -- independent expenditures, latest filing
    spender_id       VARCHAR NOT NULL,
    spender_name     VARCHAR,
    candidate_id     VARCHAR,
    candidate_name   VARCHAR,
    cycle            INTEGER NOT NULL,
    direction        VARCHAR,
    amount_cents     BIGINT NOT NULL,
    office           VARCHAR,
    office_state     VARCHAR,
    office_district  VARCHAR,
    expenditure_date VARCHAR,
    excluded_because VARCHAR  -- NULL when counted
);
