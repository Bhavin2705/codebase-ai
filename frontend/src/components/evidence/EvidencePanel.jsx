import React, { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../../config';

export default function EvidencePanel({ repoId, activeCitation, onClose }) {
  const [fileContent, setFileContent] = useState('');
  const [loading, setLoading] = useState(false);
  const highlightRef = useRef(null);

  useEffect(() => {
    if (!activeCitation || !activeCitation.filePath || !repoId) {
      setFileContent('');
      return;
    }

    const path = activeCitation.filePath;

    setLoading(true);
    fetch(`${API_BASE_URL}/repositories/${encodeURIComponent(repoId)}/file?path=${encodeURIComponent(path)}`)
      .then(async (res) => {
        if (res.status === 404) {
          setFileContent('// Source file is no longer available.');
          return;
        }
        if (res.status >= 500) {
          setFileContent('// Unable to load source code from the backend.');
          return;
        }
        if (!res.ok) {
          setFileContent('// Unable to load source code from the backend.');
          return;
        }
        const data = await res.json();
        if (data && data.content) {
          setFileContent(data.content);
        } else {
          setFileContent(`// Code content for ${path}`);
        }
      })
      .catch(() => {
        setFileContent('// Backend connection failed.');
      })
      .finally(() => setLoading(false));
  }, [activeCitation, repoId]);

  // Scroll to highlighted line after content loads
  useEffect(() => {
    if (!loading && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [loading, fileContent, activeCitation]);

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
  const normalizedPath = filePath.replace(/\\/g, '/');
  const lines = fileContent ? fileContent.split('\n') : [];
  const fileName = normalizedPath ? normalizedPath.split('/').pop() : '';
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
            const isFirstHighlight = lineNum === startLine;
            return (
              <div
                key={lineNum}
                ref={isFirstHighlight ? highlightRef : null}
                className={`code-line ${isHighlighted ? 'highlighted' : ''}`}
              >
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
