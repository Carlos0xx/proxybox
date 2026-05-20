-- ProxyBox SQLite schema.
--
-- Applied on every app startup via app.db.init.init_schema(). All statements
-- must be idempotent (IF NOT EXISTS). Use additive migrations only — never
-- drop or rename columns in place once shipped.

CREATE TABLE IF NOT EXISTS device (
    name          TEXT     PRIMARY KEY,
    label         TEXT     NOT NULL DEFAULT '',
    kind          TEXT     NOT NULL DEFAULT 'generic',
    vless_uuid    TEXT     NOT NULL,
    hy2_password  TEXT     NOT NULL,
    vless_port    INTEGER  NOT NULL,
    hy2_port      INTEGER  NOT NULL,
    sni           TEXT     NOT NULL,
    created_at    INTEGER  NOT NULL,
    last_seen     INTEGER,
    last_ip       TEXT,
    revoked       INTEGER  NOT NULL DEFAULT 0,
    notes         TEXT     NOT NULL DEFAULT '',
    sub_token     TEXT     NOT NULL UNIQUE,
    paused_until  INTEGER  NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS device_revoked_idx   ON device (revoked);
CREATE INDEX IF NOT EXISTS device_last_seen_idx ON device (last_seen);


-- Per-device traffic accounting, populated by app.workers.traffic.
-- One row per (device, UTC hour). Bytes are cumulative within the bucket.
-- bucket_ts is the UTC unix epoch of the hour's start (e.g. 2026-05-20 15:00 UTC).
CREATE TABLE IF NOT EXISTS traffic_log (
    device_name  TEXT    NOT NULL,
    bucket_ts    INTEGER NOT NULL,
    date         TEXT    NOT NULL,
    hour         INTEGER NOT NULL,
    rx_bytes     INTEGER NOT NULL DEFAULT 0,
    tx_bytes     INTEGER NOT NULL DEFAULT 0,
    conn_count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (device_name, bucket_ts)
);

CREATE INDEX IF NOT EXISTS traffic_log_bucket_idx ON traffic_log (bucket_ts);
CREATE INDEX IF NOT EXISTS traffic_log_date_idx   ON traffic_log (date);


-- Per-device per-host traffic accounting (v0.1.9+).
-- Worker periodically samples sing-box Clash API /connections and groups
-- by destination host name (metadata.host from sing-box). Each row =
-- one (device, hour, host) tuple with cumulative bytes / connection count.
-- app_group is the static classification we hand back to the SPA so the
-- "按 App 类型" bar chart can aggregate without re-running regexes.
CREATE TABLE IF NOT EXISTS host_log (
    device_name  TEXT    NOT NULL,
    bucket_ts    INTEGER NOT NULL,
    date         TEXT    NOT NULL,
    hour         INTEGER NOT NULL,
    host         TEXT    NOT NULL,
    app_group    TEXT    NOT NULL,
    rx_bytes     INTEGER NOT NULL DEFAULT 0,
    tx_bytes     INTEGER NOT NULL DEFAULT 0,
    conn_count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (device_name, bucket_ts, host)
);

CREATE INDEX IF NOT EXISTS host_log_device_idx ON host_log (device_name, bucket_ts);
CREATE INDEX IF NOT EXISTS host_log_app_idx    ON host_log (date, app_group);
CREATE INDEX IF NOT EXISTS host_log_date_idx   ON host_log (date);


-- WebAuthn passkey credentials. Populated only when features.passkey is on
-- and a user has registered at least one device. ``public_key`` is the
-- COSE-encoded public key from the authenticator's attestation.
CREATE TABLE IF NOT EXISTS passkey_credential (
    credential_id  TEXT     PRIMARY KEY,
    public_key     BLOB     NOT NULL,
    sign_count     INTEGER  NOT NULL DEFAULT 0,
    label          TEXT     NOT NULL DEFAULT '',
    created_at     INTEGER  NOT NULL,
    last_used_at   INTEGER
);
