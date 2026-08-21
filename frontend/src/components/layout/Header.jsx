import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, FolderPlus } from 'lucide-react';

export default function Header({ repositories, selectedRepo, onSelectRepo, onOpenImport, isBackendOnline = true }) {
  const navigate = useNavigate();
  const repoList = repositories && repositories.length > 0 ? repositories : [];

  return (
    <header className="app-header">
      <div
        className="brand"
        onClick={() => navigate('/')}
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
        title="Return to Repositories Overview"
      >
        <Bot size={18} style={{ color: 'var(--accent-cyan)' }} />
        <span className="brand-badge">AI Codebase Knowledge Assistant</span>
        <div
          title={isBackendOnline ? 'Backend service online' : 'Backend waking up / offline'}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            padding: '2px 7px',
            borderRadius: '12px',
            background: isBackendOnline ? 'rgba(34, 197, 94, 0.1)' : 'rgba(245, 158, 11, 0.15)',
            border: `1px solid ${isBackendOnline ? 'rgba(34, 197, 94, 0.3)' : 'rgba(245, 158, 11, 0.4)'}`,
            fontSize: '10px',
            fontWeight: 600,
            color: isBackendOnline ? '#4ade80' : '#fbbf24',
            marginLeft: '6px',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: isBackendOnline ? '#22c55e' : '#f59e0b',
              boxShadow: isBackendOnline ? '0 0 6px rgba(34, 197, 94, 0.8)' : '0 0 6px rgba(245, 158, 11, 0.8)',
              animation: isBackendOnline ? 'none' : 'pulse 1.5s infinite',
            }}
          />
          <span>{isBackendOnline ? 'Live' : 'Waking Up'}</span>
        </div>
      </div>

      <div className="repo-selector-group">
        <label style={{ color: 'var(--text-subtle)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Repository:</label>
        <select
          className="repo-dropdown"
          value={selectedRepo ? selectedRepo.id : ''}
          onChange={(e) => {
            const targetId = e.target.value;
            if (targetId) {
              const targetRepo = repoList.find(r => r.id === targetId);
              if (targetRepo && onSelectRepo) {
                onSelectRepo(targetRepo);
              }
              navigate(`/workspace/${targetId}`);
            }
          }}
        >
          {repoList.map(repo => (
            <option key={repo.id} value={repo.id}>
              {repo.name} ({repo.language || 'Java'})
            </option>
          ))}
        </select>

        <button className="btn btn-secondary" onClick={onOpenImport} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          <FolderPlus size={14} />
          <span>Import Repo</span>
        </button>
      </div>
    </header>
  );
}
