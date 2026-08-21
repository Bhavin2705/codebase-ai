import React, { useState, useEffect, useRef } from 'react';
import { API_BASE_URL, getAuthHeaders } from '../../config';

function cleanGitUrl(url) {
  if (!url || !url.trim()) return url;
  let trimmed = url.trim();

  // If already starts with valid http:// or https://, leave unchanged
  if (trimmed.startsWith('https://') || trimmed.startsWith('http://')) {
    return trimmed;
  }

  // Clean broken protocols like "https: / /", "https: /", "https: //", "http: /"
  if (/^https?[\s:]/i.test(trimmed)) {
    return trimmed.replace(/^(https?)\s*:\s*(?:\/\s*)+/i, (m, proto) => `${proto.toLowerCase()}://`);
  }

  // Auto-prepend https:// for naked domains like github.com/...
  if (trimmed.startsWith('github.com')) {
    return `https://${trimmed}`;
  }

  return trimmed;
}

export default function RepoImportModal({ isOpen, onClose, onStartIndexing }) {
  const [repoUrl, setRepoUrl] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Debounce check: after user stops typing for 1.5s, verify/clean protocol
  useEffect(() => {
    if (!repoUrl || repoUrl.length < 5) return;

    const timer = setTimeout(() => {
      setRepoUrl((current) => cleanGitUrl(current));
    }, 1500);

    return () => clearTimeout(timer);
  }, [repoUrl]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const cleanUrl = cleanGitUrl(repoUrl);
    const githubRegex = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+(\.git)?$/i;
    if (!cleanUrl) {
      setError('Please provide a public GitHub repository URL.');
      return;
    }

    if (!githubRegex.test(cleanUrl)) {
      setError('Malformed GitHub URL. Format must be: https://github.com/owner/repository');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/repositories`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ github_url: cleanUrl })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to import repository');
      }

      const repoData = await res.json();
      onStartIndexing(repoData);
    } catch (err) {
      const isNetwork =
        err.name === 'TypeError' ||
        err.message.includes('fetch') ||
        err.message.includes('network') ||
        err.message.includes('Failed');

      if (isNetwork) {
        setError(
          'Backend is currently offline or waking up from Render standby. Please wait ~30–50 seconds and try again.'
        );
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.85)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      backdropFilter: 'blur(4px)'
    }}>
      <div style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        width: '560px',
        maxWidth: '90vw',
        padding: '24px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)'
      }}>
        <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px', color: 'var(--accent-blue)' }}>
          Import GitHub Repository
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '20px' }}>
          Enter a public GitHub repository URL to index architecture, symbols, and source files. Supported languages: Java, Python, JavaScript, and TypeScript.
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>
              Repository GitHub URL
            </label>
            <input
              type="text"
              className="chat-input"
              style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
              placeholder="https://github.com/spring-projects/spring-petclinic"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              onBlur={() => setRepoUrl((current) => cleanGitUrl(current))}
              disabled={loading}
            />
            {error && (
              <div style={{ color: '#f87171', fontSize: '12px', marginTop: '8px', lineHeight: '1.4', whiteSpace: 'pre-line', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '8px 12px', borderRadius: '6px' }}>
                {error}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Submitting...' : 'Begin Indexing'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
