import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../config';
import { MOCK_INDEXING_STAGES } from '../../data/mockData';

export default function IndexProgressView({ repo, onComplete }) {
  const [stages, setStages] = useState(
    MOCK_INDEXING_STAGES.map(s => ({ ...s, status: 'pending' }))
  );
  const [error, setError] = useState('');

  useEffect(() => {
    if (!repo || !repo.id) return;

    const eventSource = new EventSource(`${API_BASE_URL}/repositories/${repo.id}/index-stream`);

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.status === 'finished') {
          eventSource.close();
          // Finalize index record
          fetch(`${API_BASE_URL}/repositories/${repo.id}/index`, { method: 'POST' })
            .then(() => onComplete())
            .catch(() => onComplete());
          return;
        }

        setStages((prev) =>
          prev.map((s) => {
            if (s.id === payload.stage_id) {
              return { ...s, status: 'completed', detail: payload.detail };
            }
            if (s.id === payload.stage_id + 1) {
              return { ...s, status: 'active' };
            }
            return s;
          })
        );
      } catch (err) {
        console.error('SSE Error:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('EventSource connection error:', err);
      eventSource.close();
      // Graceful fallback completion
      onComplete();
    };

    return () => {
      eventSource.close();
    };
  }, [repo, onComplete]);

  return (
    <div style={{
      maxWidth: '700px',
      margin: '60px auto',
      backgroundColor: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      padding: '28px'
    }}>
      <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
        Indexing Repository Pipeline
      </h2>
      <p style={{ color: 'var(--text-muted)', fontSize: '12px', fontFamily: 'var(--font-mono)', marginBottom: '24px' }}>
        Target: {repo ? repo.github_url : 'Repository'}
      </p>

      {error && (
        <div style={{ color: '#f87171', fontSize: '13px', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {stages.map((stage) => (
          <div
            key={stage.id}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              padding: '12px',
              backgroundColor: stage.status === 'active' ? 'var(--bg-panel-hover)' : 'var(--bg-dark)',
              border: `1px solid ${stage.status === 'active' ? 'var(--accent-blue)' : 'var(--border-color)'}`,
              borderRadius: '6px'
            }}
          >
            <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
              {stage.status === 'completed' && '[OK]'}
              {stage.status === 'active' && '[RUN]'}
              {stage.status === 'pending' && '[...]'}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: '13px', color: stage.status === 'pending' ? 'var(--text-muted)' : 'var(--text-main)' }}>
                Stage {stage.id}: {stage.name}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {stage.detail}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
