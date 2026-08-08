CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    github_url VARCHAR(512) UNIQUE NOT NULL,
    language VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    current_version_id UUID,
    indexed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS repository_versions (
    id UUID PRIMARY KEY,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_sha VARCHAR(40) NOT NULL,
    branch VARCHAR(255) NOT NULL DEFAULT 'main',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    indexed_at TIMESTAMP WITH TIME ZONE,
    file_count INT NOT NULL DEFAULT 0,
    symbol_count INT NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_repo_commit_sha UNIQUE (repository_id, commit_sha)
);

ALTER TABLE repositories
    ADD CONSTRAINT fk_repositories_current_version
    FOREIGN KEY (current_version_id) REFERENCES repository_versions(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY,
    repository_version_id UUID NOT NULL REFERENCES repository_versions(id) ON DELETE CASCADE,
    path VARCHAR(1024) NOT NULL,
    language VARCHAR(50) NOT NULL,
    content TEXT,
    content_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_repo_version_file_path UNIQUE (repository_version_id, path)
);

CREATE TABLE IF NOT EXISTS symbols (
    id UUID PRIMARY KEY,
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    symbol_type VARCHAR(50) NOT NULL,
    signature TEXT,
    source_code TEXT NOT NULL,
    start_line INT NOT NULL,
    end_line INT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS indexing_jobs (
    id UUID PRIMARY KEY,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    repository_version_id UUID REFERENCES repository_versions(id) ON DELETE SET NULL,
    job_type VARCHAR(50) NOT NULL DEFAULT 'full_index',
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    progress INT NOT NULL DEFAULT 0,
    current_stage VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence VARCHAR(20) NOT NULL DEFAULT 'high',
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
