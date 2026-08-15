import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, FolderPlus, Key, Check, X } from 'lucide-react';
import { getApiKey, setApiKey } from '../../config';

export default function Header({ repositories, selectedRepo, onSelectRepo, onOpenImport }) {
  const navigate = useNavigate();
  const repoList = repositories && repositories.length > 0 ? repositories : [];

  const [showKeyInput, setShowKeyInput] = useState(false);
  const [keyDraft, setKeyDraft] = useState('');

  const handleOpenKeyInput = () => {
    setKeyDraft(getApiKey());
    setShowKeyInput(true);
  };

  const handleSaveKey = () => {
    setApiKey(keyDraft.trim());
    setShowKeyInput(false);
  };

  const handleCancelKey = () => {
    setShowKeyInput(false);
    setKeyDraft('');
  };

  const currentKey = getApiKey();

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

        {showKeyInput ? (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <input
              type="text"
              id="api-key-input"
              className="chat-input"
              style={{ width: '200px', padding: '4px 8px', fontSize: '12px', fontFamily: 'var(--font-mono)' }}
              value={keyDraft}
              onChange={(e) => setKeyDraft(e.target.value)}
              placeholder="Enter API key..."
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveKey();
                if (e.key === 'Escape') handleCancelKey();
              }}
            />
            <button
              id="api-key-save-btn"
              className="btn btn-primary"
              style={{ padding: '4px 8px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              onClick={handleSaveKey}
              title="Save API key"
            >
              <Check size={13} /> Save
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 8px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              onClick={handleCancelKey}
              title="Cancel"
            >
              <X size={13} />
            </button>
          </div>
        ) : (
          <button
            id="api-key-btn"
            className="btn btn-secondary"
            onClick={handleOpenKeyInput}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            title={currentKey ? `API Key set (${currentKey.slice(0, 8)}…)` : 'No API key set'}
          >
            <Key size={14} style={{ color: currentKey ? 'var(--accent-cyan)' : 'var(--text-subtle)' }} />
            <span>Config</span>
          </button>
        )}

        <button className="btn btn-secondary" onClick={onOpenImport} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          <FolderPlus size={14} />
          <span>Import Repo</span>
        </button>
      </div>
    </header>
  );
}
