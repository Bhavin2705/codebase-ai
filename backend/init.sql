CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    github_url VARCHAR(512) UNIQUE NOT NULL,
    language VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    indexed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    path VARCHAR(1024) NOT NULL,
    language VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_repo_file_path UNIQUE (repository_id, path)
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

CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence VARCHAR(20) NOT NULL DEFAULT 'high',
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
