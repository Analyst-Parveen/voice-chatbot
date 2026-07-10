-- =====================================================================
-- Voice AI Assistant — create ALL application tables on MS SQL Server.
--
-- Generated from the application's own Alembic migrations
-- (alembic upgrade head --sql), so it matches the code exactly.
--
-- HOW TO RUN (SSMS or Azure Data Studio):
--   1. Connect to the SQL Server (e.g. 192.168.1.18) as a user that can
--      create schemas/tables in the target database.
--   2. Select the target database (e.g. IAPL) — or uncomment USE below.
--   3. Execute this whole script once.
--
-- What it creates:
--   schema  voiceai
--   tables  voiceai.sessions, voiceai.messages, voiceai.retrievals,
--           voiceai.feedback, voiceai.analytics, voiceai.user_preferences,
--           voiceai.audit_logs   (+ dbo.alembic_version bookkeeping)
--
-- Safe to hand to a DBA. Alternatively the app can create these itself:
--   cd backend && venv\Scripts\python.exe -m alembic upgrade head
-- The alembic_version INSERT at the end tells the app the schema is
-- current, so it will NOT try to re-create anything.
-- =====================================================================

-- USE [IAPL];
-- GO

BEGIN TRANSACTION;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

GO

-- Running upgrade  -> 0001_initial

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'voiceai') EXEC('CREATE SCHEMA [voiceai]');

GO

CREATE TABLE voiceai.sessions (
    id UNIQUEIDENTIFIER NOT NULL,
    user_ref VARCHAR(128) NULL,
    channel VARCHAR(16) NOT NULL,
    created_at DATETIMEOFFSET NOT NULL,
    last_active_at DATETIMEOFFSET NOT NULL,
    metadata NVARCHAR(max) NULL,
    is_active BIT NOT NULL,
    CONSTRAINT pk_sessions PRIMARY KEY (id)
);

GO

CREATE INDEX ix_sessions_user_ref ON voiceai.sessions (user_ref);

GO

CREATE TABLE voiceai.messages (
    id UNIQUEIDENTIFIER NOT NULL,
    session_id UNIQUEIDENTIFIER NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    input_type VARCHAR(16) NOT NULL,
    latency_ms INTEGER NULL,
    token_usage NVARCHAR(max) NULL,
    created_at DATETIMEOFFSET NOT NULL,
    CONSTRAINT pk_messages PRIMARY KEY (id),
    CONSTRAINT fk_messages_session_id FOREIGN KEY(session_id) REFERENCES voiceai.sessions (id) ON DELETE CASCADE
);

GO

CREATE INDEX ix_messages_session_id ON voiceai.messages (session_id);

GO

CREATE TABLE voiceai.retrievals (
    id UNIQUEIDENTIFIER NOT NULL,
    message_id UNIQUEIDENTIFIER NOT NULL,
    chunk_id VARCHAR(128) NOT NULL,
    source VARCHAR(512) NOT NULL,
    score FLOAT NOT NULL,
    used BIT NOT NULL,
    created_at DATETIMEOFFSET NOT NULL,
    CONSTRAINT pk_retrievals PRIMARY KEY (id),
    CONSTRAINT fk_retrievals_message_id FOREIGN KEY(message_id) REFERENCES voiceai.messages (id) ON DELETE CASCADE
);

GO

CREATE INDEX ix_retrievals_message_id ON voiceai.retrievals (message_id);

GO

CREATE TABLE voiceai.feedback (
    id UNIQUEIDENTIFIER NOT NULL,
    message_id UNIQUEIDENTIFIER NOT NULL,
    rating VARCHAR(8) NOT NULL,
    comment TEXT NULL,
    created_at DATETIMEOFFSET NOT NULL,
    CONSTRAINT pk_feedback PRIMARY KEY (id),
    CONSTRAINT fk_feedback_message_id FOREIGN KEY(message_id) REFERENCES voiceai.messages (id) ON DELETE CASCADE
);

GO

CREATE INDEX ix_feedback_message_id ON voiceai.feedback (message_id);

GO

CREATE TABLE voiceai.analytics (
    id UNIQUEIDENTIFIER NOT NULL,
    session_id UNIQUEIDENTIFIER NULL,
    event_type VARCHAR(64) NOT NULL,
    payload NVARCHAR(max) NULL,
    created_at DATETIMEOFFSET NOT NULL,
    CONSTRAINT pk_analytics PRIMARY KEY (id),
    CONSTRAINT fk_analytics_session_id FOREIGN KEY(session_id) REFERENCES voiceai.sessions (id) ON DELETE SET NULL
);

GO

CREATE INDEX ix_analytics_session_id ON voiceai.analytics (session_id);

GO

CREATE INDEX ix_analytics_event_type ON voiceai.analytics (event_type);

GO

CREATE TABLE voiceai.user_preferences (
    id UNIQUEIDENTIFIER NOT NULL,
    user_ref VARCHAR(128) NOT NULL,
    theme VARCHAR(16) NOT NULL,
    voice_enabled BIT NOT NULL,
    tts_voice VARCHAR(64) NULL,
    language VARCHAR(16) NOT NULL,
    updated_at DATETIMEOFFSET NOT NULL,
    CONSTRAINT pk_user_preferences PRIMARY KEY (id)
);

GO

CREATE UNIQUE INDEX uq_user_preferences_user_ref ON voiceai.user_preferences (user_ref);

GO

CREATE TABLE voiceai.audit_logs (
    id UNIQUEIDENTIFIER NOT NULL,
    actor VARCHAR(128) NULL,
    action VARCHAR(64) NOT NULL,
    entity VARCHAR(64) NOT NULL,
    entity_id VARCHAR(128) NULL,
    ip VARCHAR(64) NULL,
    created_at DATETIMEOFFSET NOT NULL,
    CONSTRAINT pk_audit_logs PRIMARY KEY (id)
);

GO

CREATE INDEX ix_audit_logs_actor ON voiceai.audit_logs (actor);

GO

INSERT INTO alembic_version (version_num) OUTPUT inserted.version_num VALUES ('0001_initial');

GO

COMMIT;

GO
