-- Silver layer: cleaned facts, one table per grain, every FEC candidate
-- and committee. Totals are views, never stored. Money is whole cents.

CREATE TABLE people (
    person_key  VARCHAR PRIMARY KEY,
    full_name   VARCHAR NOT NULL,
    first_name  VARCHAR,
    last_name   VARCHAR,
    roster_position INTEGER  -- order in the tracker; NULL = not tracked
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

CREATE TABLE double_counts (  -- data/source/dedup-applied.json: one row per dropped copy
    person_key    VARCHAR NOT NULL,
    cycle         INTEGER NOT NULL,
    kept_id       VARCHAR NOT NULL,
    dropped_id    VARCHAR NOT NULL,
    amount_cents  BIGINT NOT NULL
);

CREATE TABLE summary_differences (  -- dropped-copy cells left as filed: they differ from the kept copy
    position      INTEGER NOT NULL,  -- order the double-count record yields them
    person_key    VARCHAR NOT NULL,
    candidate_id  VARCHAR NOT NULL,
    cycle         INTEGER NOT NULL,
    field         VARCHAR NOT NULL,
    kept_id       VARCHAR NOT NULL,
    kept_cents    BIGINT NOT NULL,
    dropped_cents BIGINT NOT NULL
);

CREATE TABLE committees (  -- cm
    committee_id       VARCHAR NOT NULL,
    cycle              INTEGER NOT NULL,
    name               VARCHAR,
    committee_type     VARCHAR,
    designation        VARCHAR,
    organization_type  VARCHAR,
    committee_class    VARCHAR NOT NULL,
    kind               VARCHAR NOT NULL,  -- finer than class: winred_conduit, super_pacs, ...
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

CREATE TABLE files_read (  -- how many rows each FEC bulk file gave (a malformed row stops the build)
    file           VARCHAR NOT NULL,
    cycle          INTEGER NOT NULL,
    rows_read      BIGINT NOT NULL,
    columns        VARCHAR,  -- the header, for files that have one
    PRIMARY KEY (file, cycle)
);

CREATE TABLE outside_spending (  -- independent expenditures, every filing
    file_order       INTEGER,  -- first appearance in the file; NULL for a replaced filing
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
    election_type    VARCHAR,
    transaction_id   VARCHAR,
    excluded_because VARCHAR  -- NULL when counted; reported_again for a replaced filing
);

CREATE TABLE seats (  -- stable positions; a redrawn House map makes new seats
    seat_id             VARCHAR PRIMARY KEY,
    chamber             VARCHAR NOT NULL,
    state               VARCHAR NOT NULL,
    district            INTEGER,  -- House; 0 = at-large or delegate
    senate_class        INTEGER,  -- Senate
    voting              BOOLEAN NOT NULL,
    map_first_election  INTEGER   -- House: first covered election on this map
);

CREATE TABLE terms (  -- who holds which seat, and from what source
    person_key  VARCHAR NOT NULL,
    seat_id     VARCHAR NOT NULL,
    congress    INTEGER NOT NULL,
    start_date  VARCHAR NOT NULL,
    end_date    VARCHAR NOT NULL,
    party       VARCHAR,
    source      VARCHAR NOT NULL
);

CREATE TABLE candidacies (  -- cn: every registered candidate, per cycle file
    candidate_id          VARCHAR NOT NULL,
    cycle                 INTEGER NOT NULL,
    name                  VARCHAR,
    party                 VARCHAR,
    election_year         INTEGER,
    office                VARCHAR,
    office_state          VARCHAR,
    office_district       VARCHAR,
    incumbent_challenger  VARCHAR,
    status                VARCHAR,
    principal_committee   VARCHAR,
    seat_id               VARCHAR,  -- 2024/2026 House and regular Senate races
    PRIMARY KEY (candidate_id, cycle)
);
