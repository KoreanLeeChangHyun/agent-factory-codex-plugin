PRAGMA foreign_keys = ON;

-- Agent Factory local catalog schema, version 3.
-- This database is a rebuildable projection. Authoritative bodies and runtime
-- recovery evidence remain in their resolved files and stores.

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT,
    checksum TEXT
);

INSERT OR IGNORE INTO schema_metadata (key, value) VALUES
    ('catalog_kind', 'rebuildable-local-projection'),
    ('schema_version', '3');
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES
    (1, 'initial-catalog-schema'),
    (2, 'agent-and-document-fts5-search'),
    (3, 'agent-search-timestamps');

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    role TEXT,
    source_path TEXT NOT NULL,
    observed_at TEXT,
    CHECK (length(agent_id) > 0),
    CHECK (length(source_path) > 0)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    role TEXT,
    status TEXT,
    resume_identity TEXT,
    source_path TEXT NOT NULL UNIQUE,
    created_at TEXT,
    updated_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    UNIQUE (agent_id, session_id),
    CHECK (length(session_id) > 0),
    CHECK (length(source_path) > 0)
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    session_id TEXT,
    role TEXT,
    actor TEXT,
    status TEXT,
    request_hash TEXT,
    source_path TEXT NOT NULL UNIQUE,
    accepted_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    UNIQUE (agent_id, run_id),
    FOREIGN KEY (agent_id, session_id)
        REFERENCES agent_sessions(agent_id, session_id),
    CHECK (length(run_id) > 0),
    CHECK (length(source_path) > 0),
    CHECK (request_hash IS NULL OR length(request_hash) = 64)
);

CREATE TABLE IF NOT EXISTS turns (
    turn_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    turn_sequence INTEGER NOT NULL CHECK (turn_sequence >= 0),
    status TEXT,
    source_path TEXT,
    started_at TEXT,
    finished_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    UNIQUE (run_id, turn_sequence),
    CHECK (source_path IS NULL OR length(source_path) > 0)
);

CREATE TABLE IF NOT EXISTS work_verification_loops (
    loop_id TEXT PRIMARY KEY,
    work_agent_id TEXT REFERENCES agents(agent_id) ON DELETE SET NULL,
    verification_agent_id TEXT REFERENCES agents(agent_id) ON DELETE SET NULL,
    status TEXT,
    phase TEXT,
    original_request_hash TEXT,
    original_request_path TEXT,
    latest_work_run_id TEXT,
    latest_verification_run_id TEXT,
    last_verification_decision TEXT,
    terminal_reason_code TEXT,
    terminal_reason_summary TEXT,
    source_path TEXT NOT NULL UNIQUE,
    created_at TEXT,
    updated_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    FOREIGN KEY (work_agent_id, latest_work_run_id)
        REFERENCES runs(agent_id, run_id),
    FOREIGN KEY (verification_agent_id, latest_verification_run_id)
        REFERENCES runs(agent_id, run_id),
    CHECK (length(loop_id) > 0),
    CHECK (length(source_path) > 0),
    CHECK (original_request_hash IS NULL OR length(original_request_hash) = 64),
    CHECK (latest_work_run_id IS NULL OR work_agent_id IS NOT NULL),
    CHECK (latest_verification_run_id IS NULL OR verification_agent_id IS NOT NULL),
    CHECK (
        work_agent_id IS NULL OR verification_agent_id IS NULL
        OR work_agent_id <> verification_agent_id
    )
);

CREATE TABLE IF NOT EXISTS loop_runs (
    loop_id TEXT NOT NULL REFERENCES work_verification_loops(loop_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    sequence INTEGER CHECK (sequence IS NULL OR sequence >= 0),
    graph_role TEXT,
    relationship_kind TEXT NOT NULL DEFAULT 'unknown',
    observed_at TEXT,
    PRIMARY KEY (loop_id, run_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS run_relationships (
    parent_run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    child_run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    relationship_kind TEXT NOT NULL DEFAULT 'unknown',
    source_path TEXT,
    observed_at TEXT,
    PRIMARY KEY (parent_run_id, child_run_id, relationship_kind),
    CHECK (parent_run_id <> child_run_id),
    CHECK (source_path IS NULL OR length(source_path) > 0)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS dispatches (
    dispatch_id TEXT PRIMARY KEY,
    loop_id TEXT REFERENCES work_verification_loops(loop_id) ON DELETE SET NULL,
    source_run_id TEXT REFERENCES runs(run_id) ON DELETE SET NULL,
    target_run_id TEXT REFERENCES runs(run_id) ON DELETE SET NULL,
    operation TEXT,
    target_role TEXT,
    status TEXT,
    request_hash TEXT,
    source_path TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    CHECK (length(dispatch_id) > 0),
    CHECK (length(source_path) > 0),
    CHECK (request_hash IS NULL OR length(request_hash) = 64)
);

CREATE TABLE IF NOT EXISTS document_types (
    type_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
) WITHOUT ROWID;

INSERT OR IGNORE INTO document_types (type_code, description) VALUES
    ('original', 'source-faithful evidence'),
    ('processed', 'derived working knowledge'),
    ('specification', 'accepted and reconciled project knowledge');

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL
        REFERENCES document_types(type_code),
    title TEXT,
    status TEXT,
    resolved_store TEXT,
    source_path TEXT NOT NULL UNIQUE,
    created_at TEXT,
    updated_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    UNIQUE (document_id, document_type),
    CHECK (length(document_id) > 0),
    CHECK (length(source_path) > 0)
);

CREATE TABLE IF NOT EXISTS representation_kinds (
    kind_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
) WITHOUT ROWID;

INSERT OR IGNORE INTO representation_kinds (kind_code, description) VALUES
    ('source-native', 'native or source-appropriate Original representation'),
    ('processed-markdown', 'local-adapter Processed Markdown representation'),
    ('human-html', 'Human-facing Specification browser representation'),
    ('ai-skill', 'AI-facing Specification Skill representation'),
    ('legacy', 'preserved legacy representation'),
    ('other', 'recognized representation outside the initial vocabulary'),
    ('unknown', 'source does not provide a supported representation kind');

CREATE TABLE IF NOT EXISTS document_representations (
    representation_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    representation_kind TEXT NOT NULL DEFAULT 'unknown'
        REFERENCES representation_kinds(kind_code),
    resolved_store TEXT,
    source_path TEXT NOT NULL UNIQUE,
    media_type TEXT,
    content_hash TEXT,
    availability_status TEXT,
    created_at TEXT,
    updated_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    UNIQUE (document_id, representation_id, representation_kind),
    CHECK (length(representation_id) > 0),
    CHECK (length(source_path) > 0),
    CHECK (content_hash IS NULL OR length(content_hash) = 64)
);

CREATE TABLE IF NOT EXISTS document_relationship_kinds (
    kind_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
) WITHOUT ROWID;

INSERT OR IGNORE INTO document_relationship_kinds (kind_code, description) VALUES
    ('derivation', 'source-backed derivation relationship'),
    ('evidence', 'source-backed evidentiary relationship'),
    ('provenance', 'source-backed provenance relationship'),
    ('legacy', 'preserved legacy relationship'),
    ('other', 'recognized relationship outside the initial vocabulary'),
    ('unknown', 'source records a relationship without a supported kind');

CREATE TABLE IF NOT EXISTS document_relationships (
    relationship_id TEXT PRIMARY KEY,
    source_document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    target_document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    relationship_kind TEXT NOT NULL DEFAULT 'unknown'
        REFERENCES document_relationship_kinds(kind_code),
    evidence_representation_id TEXT
        REFERENCES document_representations(representation_id) ON DELETE SET NULL,
    source_path TEXT,
    observed_at TEXT,
    CHECK (length(relationship_id) > 0),
    CHECK (source_document_id <> target_document_id),
    CHECK (source_path IS NULL OR length(source_path) > 0)
);

CREATE TABLE IF NOT EXISTS agent_document_relationships (
    relationship_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    run_id TEXT,
    relationship_kind TEXT NOT NULL DEFAULT 'unknown',
    source_path TEXT,
    observed_at TEXT,
    FOREIGN KEY (agent_id, run_id)
        REFERENCES runs(agent_id, run_id) ON DELETE CASCADE,
    CHECK (length(relationship_id) > 0),
    CHECK (length(relationship_kind) > 0),
    CHECK (source_path IS NULL OR length(source_path) > 0)
);

CREATE TABLE IF NOT EXISTS specification_pair_status (
    document_id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL DEFAULT 'specification'
        CHECK (document_type = 'specification'),
    human_representation_id TEXT,
    human_representation_kind TEXT NOT NULL DEFAULT 'human-html'
        CHECK (human_representation_kind = 'human-html'),
    ai_representation_id TEXT,
    ai_representation_kind TEXT NOT NULL DEFAULT 'ai-skill'
        CHECK (ai_representation_kind = 'ai-skill'),
    pair_status TEXT NOT NULL DEFAULT 'unknown' CHECK (
        pair_status IN (
            'aligned', 'misaligned', 'missing-human', 'missing-ai',
            'inaccessible', 'legacy', 'unknown'
        )
    ),
    evidence_path TEXT,
    checked_at TEXT,
    observed_at TEXT,
    error_code TEXT,
    error_summary TEXT,
    FOREIGN KEY (document_id, document_type)
        REFERENCES documents(document_id, document_type) ON DELETE CASCADE,
    FOREIGN KEY (
        document_id, human_representation_id, human_representation_kind
    ) REFERENCES document_representations(
        document_id, representation_id, representation_kind
    ),
    FOREIGN KEY (
        document_id, ai_representation_id, ai_representation_kind
    ) REFERENCES document_representations(
        document_id, representation_id, representation_kind
    ),
    CHECK (human_representation_id IS NULL OR human_representation_id <> ai_representation_id),
    CHECK (evidence_path IS NULL OR length(evidence_path) > 0),
    CHECK (
        (pair_status IN ('aligned', 'misaligned', 'inaccessible')
            AND human_representation_id IS NOT NULL
            AND ai_representation_id IS NOT NULL)
        OR (pair_status = 'missing-human'
            AND human_representation_id IS NULL
            AND ai_representation_id IS NOT NULL)
        OR (pair_status = 'missing-ai'
            AND human_representation_id IS NOT NULL
            AND ai_representation_id IS NULL)
        OR pair_status IN ('legacy', 'unknown')
    )
) WITHOUT ROWID;

-- Version 2 search projection, extended in version 3 with searchable Agent
-- timestamps. These normalized rows bind stable source-backed entity or
-- representation identity and result metadata; FTS tables contain only
-- explicitly bounded searchable fields produced during rebuild.
CREATE TABLE IF NOT EXISTS agent_search_entities (
    search_entity_id TEXT PRIMARY KEY,
    entity_kind TEXT NOT NULL CHECK (
        entity_kind IN ('agent', 'session', 'run', 'loop', 'dispatch')
    ),
    entity_id TEXT NOT NULL,
    agent_id TEXT REFERENCES agents(agent_id) ON DELETE CASCADE,
    role TEXT,
    status TEXT,
    error_summary TEXT,
    timestamp TEXT,
    source_path TEXT NOT NULL,
    UNIQUE (entity_kind, entity_id, source_path),
    CHECK (length(search_entity_id) > 0),
    CHECK (length(entity_id) > 0),
    CHECK (length(source_path) > 0)
) WITHOUT ROWID;

CREATE VIRTUAL TABLE IF NOT EXISTS agent_search_fts USING fts5(
    search_entity_id UNINDEXED,
    entity_id,
    role,
    status,
    error_summary,
    timestamp,
    source_path,
    tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS document_search_entries (
    search_entry_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    representation_id TEXT NOT NULL
        REFERENCES document_representations(representation_id) ON DELETE CASCADE,
    document_type TEXT NOT NULL REFERENCES document_types(type_code),
    representation_kind TEXT NOT NULL REFERENCES representation_kinds(kind_code),
    title TEXT,
    source_path TEXT NOT NULL UNIQUE,
    media_type TEXT,
    index_status TEXT NOT NULL CHECK (
        index_status IN (
            'indexed', 'truncated', 'excluded-format', 'excluded-binary',
            'excluded-total-limit', 'inaccessible', 'invalid-utf8'
        )
    ),
    source_bytes INTEGER CHECK (source_bytes IS NULL OR source_bytes >= 0),
    indexed_bytes INTEGER NOT NULL DEFAULT 0 CHECK (indexed_bytes >= 0),
    truncated INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0, 1)),
    error_code TEXT,
    FOREIGN KEY (document_id, document_type)
        REFERENCES documents(document_id, document_type) ON DELETE CASCADE,
    FOREIGN KEY (document_id, representation_id, representation_kind)
        REFERENCES document_representations(
            document_id, representation_id, representation_kind
        ) ON DELETE CASCADE,
    CHECK (length(search_entry_id) > 0),
    CHECK (length(source_path) > 0)
) WITHOUT ROWID;

CREATE VIRTUAL TABLE IF NOT EXISTS document_search_fts USING fts5(
    search_entry_id UNINDEXED,
    title,
    source_path,
    body,
    tokenize = 'unicode61'
);

CREATE INDEX IF NOT EXISTS idx_agent_search_kind_status
    ON agent_search_entities(entity_kind, status, source_path);
CREATE INDEX IF NOT EXISTS idx_document_search_type_status
    ON document_search_entries(document_type, index_status, source_path);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_agent ON agent_sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_runs_agent_status ON runs(agent_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated_at);
CREATE INDEX IF NOT EXISTS idx_turns_status ON turns(status);
CREATE INDEX IF NOT EXISTS idx_loops_status_updated ON work_verification_loops(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_loop_runs_run ON loop_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_run_relationships_child ON run_relationships(child_run_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_loop ON dispatches(loop_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_target_run ON dispatches(target_run_id);
CREATE INDEX IF NOT EXISTS idx_documents_type_status ON documents(document_type, status);
CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at);
CREATE INDEX IF NOT EXISTS idx_representations_document_kind
    ON document_representations(document_id, representation_kind);
CREATE INDEX IF NOT EXISTS idx_document_relationships_source
    ON document_relationships(source_document_id, relationship_kind);
CREATE INDEX IF NOT EXISTS idx_document_relationships_target
    ON document_relationships(target_document_id, relationship_kind);
CREATE INDEX IF NOT EXISTS idx_agent_document_document
    ON agent_document_relationships(document_id, relationship_kind);
CREATE INDEX IF NOT EXISTS idx_agent_document_run ON agent_document_relationships(run_id);
