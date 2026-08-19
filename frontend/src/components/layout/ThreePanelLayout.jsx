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
  const repoName = selectedRepo?.name || 'Codebase Workspace';

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

  // Hydrate chat history from backend on repository load / page refresh
  useEffect(() => {
    if (!currentRepoId) return;

    const title = selectedRepo?.name
      ? `Repository Loaded: ${selectedRepo.name}`
      : (repoName !== 'Codebase Workspace' ? `Repository Loaded: ${repoName}` : 'Repository Loaded');

    const initialWelcomeMessage = {
      id: `init-${currentRepoId}`,
      repositoryId: currentRepoId,
      question: title,
      answer: `Codebase indexed successfully! You can browse files in the Explorer or ask questions about architecture, functions, endpoints, or implementation details.`,
      citations: [],
      confidence: 'high'
    };

    fetch(`${API_BASE_URL}/chat/history/${encodeURIComponent(currentRepoId)}`, {
      headers: getAuthHeaders(),
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((history) => {
        if (Array.isArray(history) && history.length > 0) {
          const loadedMsgs = history.map((item) => ({
            id: item.id || `hist-${Math.random()}`,
            repositoryId: currentRepoId,
            question: item.question,
            answer: item.answer,
            citations: item.citations || [],
            confidence: item.confidence || 'high',
            isPending: false,
          }));
          setConversations([initialWelcomeMessage, ...loadedMsgs]);
        } else {
          setConversations((prev) => {
            if (prev.length === 0) return [initialWelcomeMessage];
            return prev.map((msg) => {
              if (msg.id === `init-${currentRepoId}` && selectedRepo?.name) {
                return { ...msg, question: `Repository Loaded: ${selectedRepo.name}` };
              }
              return msg;
            });
          });
        }
      })
      .catch((err) => {
        console.error('Failed to load chat history:', err);
        setConversations((prev) => (prev.length === 0 ? [initialWelcomeMessage] : prev));
      });

    setActiveCitation(null);
  }, [currentRepoId, selectedRepo?.name]);

  const handleClearChat = async () => {
    if (!currentRepoId) return;
    try {
      await fetch(`${API_BASE_URL}/chat/history/${encodeURIComponent(currentRepoId)}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      const title = selectedRepo?.name ? `Repository Loaded: ${selectedRepo.name}` : 'Repository Loaded';
      setConversations([{
        id: `init-${currentRepoId}`,
        repositoryId: currentRepoId,
        question: title,
        answer: `Codebase indexed successfully! You can browse files in the Explorer or ask questions about architecture, functions, endpoints, or implementation details.`,
        citations: [],
        confidence: 'high'
      }]);
      setActiveCitation(null);
      addToast('History Cleared', 'Chat history has been reset for this workspace.', 'info');
    } catch (err) {
      addToast('Clear Failed', err.message, 'error');
    }
  };

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
      answer: '',
      citations: [],
      confidence: 'medium'
    };

    setConversations((prev) => [...prev, pendingMsg]);

    try {
      const res = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          repository_id: currentRepoId,
          question: qText
        })
      });

      if (res.status === 401) {
        addToast('Unauthorized — 401', 'Invalid or missing API key. Verify VITE_API_KEY environment configuration.', 'error');
        setConversations((prev) =>
          prev.map((msg) =>
            msg.id === tempId
              ? { ...msg, isPending: false, answer: '⚠️ API request rejected: 401 Unauthorized. Verify API access key.' }
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

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedAnswer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data:')) continue;

          const jsonStr = trimmed.slice(5).trim();
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === 'token') {
              accumulatedAnswer += event.text;
              setConversations((prev) =>
                prev.map((msg) =>
                  msg.id === tempId
                    ? { ...msg, answer: accumulatedAnswer, isPending: true }
                    : msg
                )
              );
            } else if (event.type === 'done') {
              setConversations((prev) =>
                prev.map((msg) =>
                  msg.id === tempId
                    ? {
                        ...msg,
                        isPending: false,
                        answer: event.answer || accumulatedAnswer,
                        citations: event.citations || [],
                        confidence: event.confidence || 'high',
                        execution_time_ms: event.execution_time_ms,
                        thought_process: event.thought_process,
                      }
                    : msg
                )
              );
              if (event.citations && event.citations.length > 0) {
                setActiveCitation(event.citations[0]);
              }
            } else if (event.type === 'error') {
              throw new Error(event.message || 'Streaming response error');
            }
          } catch (jsonErr) {
            if (jsonErr.message && !jsonErr.message.includes('JSON')) {
              throw jsonErr;
            }
          }
        }
      }

      setConversations((prev) =>
        prev.map((msg) =>
          msg.id === tempId && msg.isPending
            ? { ...msg, isPending: false }
            : msg
        )
      );

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
        <NavPanel repoId={currentRepoId} selectedRepo={selectedRepo || { id: currentRepoId }} onSelectFile={handleSelectFile} />
        <ChatPanel
          conversations={conversations}
          onSelectCitation={handleSelectCitation}
          onAskQuestion={handleAskQuestion}
          onClearChat={handleClearChat}
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
