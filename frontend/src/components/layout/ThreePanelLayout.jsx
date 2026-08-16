import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import NavPanel from '../navigation/NavPanel';
import ChatPanel from '../chat/ChatPanel';
import EvidencePanel from '../evidence/EvidencePanel';
import { API_BASE_URL, getAuthHeaders } from '../../config';

function Toast({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div style={{
      position: 'fixed',
      top: '56px',
      right: '16px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            background: t.type === 'error' ? 'rgba(239,68,68,0.12)' : 'rgba(56,189,248,0.10)',
            border: `1px solid ${t.type === 'error' ? 'rgba(239,68,68,0.5)' : 'rgba(56,189,248,0.4)'}`,
            borderRadius: '8px',
            padding: '10px 14px',
            minWidth: '280px',
            maxWidth: '380px',
            backdropFilter: 'blur(8px)',
            boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
            animation: 'slideInRight 0.2s cubic-bezier(0.16,1,0.3,1)',
          }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '12px', color: t.type === 'error' ? '#f87171' : 'var(--accent-cyan)', marginBottom: '2px' }}>
              {t.title}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              {t.message}
            </div>
          </div>
          <button
            onClick={() => onDismiss(t.id)}
            style={{ background: 'none', border: 'none', color: 'var(--text-subtle)', cursor: 'pointer', fontSize: '14px', lineHeight: 1, padding: '0 2px' }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

export default function ThreePanelLayout({ selectedRepo }) {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const currentRepoId = repoId || selectedRepo?.id || null;
  const repoName = selectedRepo?.name || currentRepoId || 'Repository';

  const [conversations, setConversations] = useState([]);
  const [activeCitation, setActiveCitation] = useState(null);
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((title, message, type = 'error') => {
    const id = `toast-${Date.now()}`;
    setToasts((prev) => [...prev, { id, title, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 6000);
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Sync URL in address bar if /workspace without :repoId
  useEffect(() => {
    if (!repoId && currentRepoId) {
      navigate(`/workspace/${currentRepoId}`, { replace: true });
    }
  }, [repoId, currentRepoId, navigate]);

  useEffect(() => {
    if (!currentRepoId) return;
    const initialWelcomeMessage = {
      id: `init-${currentRepoId}`,
      repositoryId: currentRepoId,
      question: `Repository Loaded: ${repoName}`,
      answer: `Codebase indexed successfully! You can browse files in the Explorer or ask questions about architecture, functions, endpoints, or implementation details.`,
      citations: [],
      confidence: 'high'
    };
    setConversations([initialWelcomeMessage]);
    setActiveCitation(null);
  }, [currentRepoId, repoName]);

  // Fire starter question passed via router state from the overview page
  useEffect(() => {
    const starterQuestion = location.state?.initialQuestion;
    if (!starterQuestion || !currentRepoId) return;
    // Clear the state so a refresh/back-navigation doesn't re-fire
    window.history.replaceState({}, '', window.location.pathname);
    handleAskQuestion(starterQuestion);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentRepoId]);

  const handleSelectCitation = (citation) => {
    setActiveCitation(citation);
  };

  const handleSelectFile = (filePath) => {
    setActiveCitation({
      filePath,
      startLine: 1,
      endLine: 200,
      symbol: 'File View'
    });
  };

  const handleAskQuestion = async (qText) => {
    const tempId = `chat-${Date.now()}`;
    const pendingMsg = {
      id: tempId,
      repositoryId: currentRepoId,
      question: qText,
      isPending: true,
      answer: 'Analyzing codebase AST symbols and vector embeddings...',
      citations: [],
      confidence: 'medium'
    };

    setConversations((prev) => [...prev, pendingMsg]);

    try {
      const res = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          repository_id: currentRepoId,
          question: qText
        })
      });

      if (res.status === 401) {
        addToast('Unauthorized — 401', 'Invalid or missing API key. Update your key via Config in the header.', 'error');
        setConversations((prev) =>
          prev.map((msg) =>
            msg.id === tempId
              ? { ...msg, isPending: false, answer: '⚠️ API request rejected: 401 Unauthorized. Check your API key in Config.' }
              : msg
          )
        );
        return;
      }

      if (res.status === 403) {
        addToast('Forbidden — 403', 'Your API key does not have access to this resource.', 'error');
        setConversations((prev) =>
          prev.map((msg) =>
            msg.id === tempId
              ? { ...msg, isPending: false, answer: '⚠️ API request rejected: 403 Forbidden.' }
              : msg
          )
        );
        return;
      }

      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}${errText ? ': ' + errText.slice(0, 120) : ''}`);
      }

      const data = await res.json();
      setConversations((prev) =>
        prev.map((msg) => (msg.id === tempId ? data : msg))
      );

      if (data.citations && data.citations.length > 0) {
        setActiveCitation(data.citations[0]);
      }
    } catch (err) {
      addToast('Request Failed', err.message, 'error');
      setConversations((prev) =>
        prev.map((msg) =>
          msg.id === tempId
            ? { ...msg, isPending: false, answer: `Error: ${err.message}` }
            : msg
        )
      );
    }
  };

  return (
    <>
      <Toast toasts={toasts} onDismiss={dismissToast} />
      <div className="three-panel-container">
        <NavPanel selectedRepo={{ id: currentRepoId }} onSelectFile={handleSelectFile} />
        <ChatPanel
          conversations={conversations}
          onSelectCitation={handleSelectCitation}
          onAskQuestion={handleAskQuestion}
        />
        <EvidencePanel
          repoId={currentRepoId}
          activeCitation={activeCitation}
          onClose={() => setActiveCitation(null)}
        />
      </div>
    </>
  );
}
