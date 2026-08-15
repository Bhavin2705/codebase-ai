import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, FolderPlus } from 'lucide-react';

export default function Header({ repositories, selectedRepo, onSelectRepo, onOpenImport }) {
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
