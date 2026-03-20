-- ─────────────────────────────────────────────────────
-- Helmlock 4S — Full Schema Reset
-- Supabase Dashboard > SQL Editor > Run All
-- ─────────────────────────────────────────────────────

DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS lockers;

CREATE TABLE lockers (
  id            BIGSERIAL    PRIMARY KEY,
  locker_number INT4         UNIQUE NOT NULL,
  status        TEXT         NOT NULL DEFAULT 'available',
  updated_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE transactions (
  id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  locker_number   INT4         NOT NULL,
  payment_method  TEXT         NOT NULL,
  amount          INT4         NOT NULL DEFAULT 0,
  pin             TEXT         NOT NULL,
  status          TEXT         NOT NULL DEFAULT 'active',
  rented_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  expires_at      TIMESTAMPTZ  NOT NULL,
  retrieved_at    TIMESTAMPTZ,
  overtime_paid   BOOLEAN      NOT NULL DEFAULT FALSE,
  overtime_amount INT4         NOT NULL DEFAULT 0
);

-- Seed 12 lockers
INSERT INTO lockers (locker_number, status)
SELECT gs, 'available' FROM generate_series(1, 12) gs;

-- Verify
SELECT locker_number, status FROM lockers ORDER BY locker_number;