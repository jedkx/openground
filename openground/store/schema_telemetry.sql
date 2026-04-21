-- OpenGround ground-side telemetry archive.
-- Column layout follows common ground-data practice: ground receipt time (ERT-like),
-- event time for the measurement (SCET/MET-style instant as unix ms), CCSDS primary-header
-- fields, plus a full JSONB envelope for UI/API parity (faults, flight rules, sim metadata).
-- Idempotent on startup.

CREATE TABLE IF NOT EXISTS openground_telemetry (
    id BIGSERIAL PRIMARY KEY,

    ground_received_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    event_time_ms BIGINT NOT NULL,

    apid INTEGER,
    sequence_count INTEGER NOT NULL,
    frame_octet_length INTEGER NOT NULL,

    telemetry_mode TEXT NOT NULL DEFAULT 'unknown',
    ingress_source TEXT,

    envelope JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS openground_telemetry_event_time_ms_idx
    ON openground_telemetry (event_time_ms);

CREATE INDEX IF NOT EXISTS openground_telemetry_ground_received_idx
    ON openground_telemetry (ground_received_at);
