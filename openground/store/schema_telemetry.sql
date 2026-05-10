-- OpenGround ground-side telemetry archive.
-- Column layout follows common ground-data practice: ground receipt time (ERT-like),
-- event time for the measurement (SCET/MET-style instant as unix ms), CCSDS primary-header
-- fields, plus a full JSONB envelope for UI/API parity (faults, flight rules, sim metadata).
-- Idempotent on startup; safe to run against an existing schema.

CREATE TABLE IF NOT EXISTS openground_telemetry (
    id BIGSERIAL PRIMARY KEY,

    ground_received_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    event_time_ms BIGINT NOT NULL,

    mission_id TEXT,

    apid INTEGER,
    sequence_count INTEGER NOT NULL DEFAULT 0,
    frame_octet_length INTEGER NOT NULL DEFAULT 0,

    telemetry_mode TEXT NOT NULL DEFAULT 'unknown',
    ingress_source TEXT,

    envelope JSONB NOT NULL
);

-- Add mission_id to pre-existing deployments that lack the column.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'openground_telemetry'
           AND column_name = 'mission_id'
    ) THEN
        ALTER TABLE openground_telemetry ADD COLUMN mission_id TEXT;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS openground_telemetry_event_time_ms_idx
    ON openground_telemetry (event_time_ms);

CREATE INDEX IF NOT EXISTS openground_telemetry_ground_received_idx
    ON openground_telemetry (ground_received_at);

CREATE INDEX IF NOT EXISTS openground_telemetry_mission_id_idx
    ON openground_telemetry (mission_id);
