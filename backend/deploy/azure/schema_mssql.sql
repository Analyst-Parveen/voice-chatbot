-- =====================================================================
-- Voice AI Assistant - create ALL application tables on MS SQL Server.
--
-- Generated from the app's own Alembic migrations (alembic upgrade head --sql),
-- through BOTH migrations (0001_initial + 0002_faq), so it matches the code
-- exactly and stamps the schema version as current (0002_faq).
--
-- HOW TO RUN (SSMS / Azure Data Studio):
--   1. Connect to the SQL Server as a user that can create schemas/tables.
--   2. Select the target database (e.g. IAPL) - or uncomment USE below.
--   3. Execute this whole script once.
--
-- Creates: schema 'voiceai' + 11 tables (sessions, messages, retrievals,
--   feedback, analytics, user_preferences, audit_logs, faq_intents,
--   faq_questions, faq_answers, faq_sources) + dbo.alembic_version.
--
-- Alternatively the app creates all of this itself:
--   cd backend && venv\Scripts\python.exe -m alembic upgrade head
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

-- Running upgrade 0001_initial -> 0002_faq

CREATE TABLE voiceai.faq_intents (
    id UNIQUEIDENTIFIER NOT NULL, 
    intent_key VARCHAR(128) NOT NULL, 
    category VARCHAR(64) NULL, 
    status VARCHAR(16) NOT NULL, 
    enabled BIT NOT NULL, 
    created_at DATETIMEOFFSET NOT NULL, 
    updated_at DATETIMEOFFSET NOT NULL, 
    CONSTRAINT pk_faq_intents PRIMARY KEY (id)
);

GO

CREATE UNIQUE INDEX ix_faq_intents_intent_key ON voiceai.faq_intents (intent_key);

GO

CREATE TABLE voiceai.faq_questions (
    id UNIQUEIDENTIFIER NOT NULL, 
    intent_id UNIQUEIDENTIFIER NOT NULL, 
    text VARCHAR(512) NOT NULL, 
    language_tag VARCHAR(16) NOT NULL, 
    is_quick_question BIT NOT NULL, 
    created_at DATETIMEOFFSET NOT NULL, 
    CONSTRAINT pk_faq_questions PRIMARY KEY (id), 
    CONSTRAINT fk_faq_questions_intent_id FOREIGN KEY(intent_id) REFERENCES voiceai.faq_intents (id) ON DELETE CASCADE
);

GO

CREATE INDEX ix_faq_questions_intent_id ON voiceai.faq_questions (intent_id);

GO

CREATE TABLE voiceai.faq_answers (
    id UNIQUEIDENTIFIER NOT NULL, 
    intent_id UNIQUEIDENTIFIER NOT NULL, 
    language VARCHAR(8) NOT NULL, 
    answer_text TEXT NOT NULL, 
    created_at DATETIMEOFFSET NOT NULL, 
    CONSTRAINT pk_faq_answers PRIMARY KEY (id), 
    CONSTRAINT fk_faq_answers_intent_id FOREIGN KEY(intent_id) REFERENCES voiceai.faq_intents (id) ON DELETE CASCADE
);

GO

CREATE INDEX ix_faq_answers_intent_id ON voiceai.faq_answers (intent_id);

GO

CREATE TABLE voiceai.faq_sources (
    id UNIQUEIDENTIFIER NOT NULL, 
    intent_id UNIQUEIDENTIFIER NOT NULL, 
    source VARCHAR(512) NOT NULL, 
    created_at DATETIMEOFFSET NOT NULL, 
    CONSTRAINT pk_faq_sources PRIMARY KEY (id), 
    CONSTRAINT fk_faq_sources_intent_id FOREIGN KEY(intent_id) REFERENCES voiceai.faq_intents (id) ON DELETE CASCADE
);

GO

CREATE INDEX ix_faq_sources_intent_id ON voiceai.faq_sources (intent_id);

GO

UPDATE alembic_version SET version_num='0002_faq' WHERE alembic_version.version_num = '0001_initial';

GO

COMMIT;

GO

