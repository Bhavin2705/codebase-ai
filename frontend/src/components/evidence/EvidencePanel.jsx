import React, { useState, useEffect } from 'react';
import { MOCK_CODE_FILES } from '../../data/mockData';
import { API_BASE_URL } from '../../config';

export default function EvidencePanel({ repoId, activeCitation, onClose }) {
  const [fileContent, setFileContent] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeCitation || !activeCitation.filePath) {
      setFileContent('');
      return;
    }

    const path = activeCitation.filePath;
    const currentRepoId = repoId || 'repo-1';

    setLoading(true);
    fetch(`${API_BASE_URL}/repositories/${currentRepoId}/file?path=${encodeURIComponent(path)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.content) {
          setFileContent(data.content);
        } else if (MOCK_CODE_FILES[path]) {
          setFileContent(MOCK_CODE_FILES[path].content);
        } else {
          setFileContent(`// Code content for ${path}\n// File indexed in repo: ${currentRepoId}`);
        }
      })
      .catch(() => {
        if (MOCK_CODE_FILES[path]) {
          setFileContent(MOCK_CODE_FILES[path].content);
        } else {
          setFileContent(`// Code content for ${path}`);
        }
      })
      .finally(() => setLoading(false));
  }, [activeCitation, repoId]);

  if (!activeCitation) {
    return (
      <aside className="evidence-panel">
        <header className="evidence-header">
          <span className="evidence-title">Evidence Code Preview</span>
        </header>
        <div style={{ padding: '20px 16px', color: 'var(--text-muted)', textAlign: 'center' }}>
          Select a file from Explorer or click a citation reference to inspect source code.
        </div>
      </aside>
    );
  }

  const { filePath = '', startLine = 1, endLine = 100, symbol = '' } = activeCitation || {};
  const lines = fileContent ? fileContent.split('\n') : [];
  const fileName = filePath ? filePath.split('/').pop() : '';
  const displaySymbol = symbol && symbol !== fileName && symbol !== 'File View' ? `(${symbol})` : '';

  return (
    <aside className="evidence-panel">
      <header className="evidence-header">
        <span className="evidence-title" title={filePath}>
          {fileName} {displaySymbol}
        </span>
        <button 
          onClick={onClose} 
          className="btn btn-secondary" 
          style={{ padding: '2px 8px', fontSize: '11px' }}
        >
          Close
        </button>
      </header>

      <div className="evidence-path-banner">
        Path: {filePath} (Lines {startLine}-{endLine})
      </div>

      <div className="code-container">
        {loading ? (
          <div style={{ padding: '16px', color: 'var(--text-muted)' }}>
            Loading file contents...
          </div>
        ) : lines.length > 0 ? (
          lines.map((lineText, idx) => {
            const lineNum = idx + 1;
            const isHighlighted = lineNum >= startLine && lineNum <= endLine;
            return (
              <div key={lineNum} className={`code-line ${isHighlighted ? 'highlighted' : ''}`}>
                <span className="line-num">{lineNum}</span>
                <span className="line-content">{lineText}</span>
              </div>
            );
          })
        ) : (
          <div style={{ padding: '16px', color: 'var(--text-muted)' }}>
            Source code file not loaded.
          </div>
        )}
      </div>
    </aside>
  );
}
