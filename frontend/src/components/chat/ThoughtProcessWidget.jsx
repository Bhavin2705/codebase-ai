import React, { useState } from 'react';
import { Brain, ChevronDown, ChevronUp, FileCode2 } from 'lucide-react';

export default function ThoughtProcessWidget({ thoughtProcess, executionTimeMs }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!thoughtProcess && !executionTimeMs) return null;

  const timeSec = executionTimeMs ? (executionTimeMs / 1000).toFixed(2) : null;
  const tp = thoughtProcess || {};

  return (
    <div className="thought-process-card">
      <div className="thought-process-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="thought-process-title">
          <Brain size={14} style={{ color: 'var(--accent-violet)' }} />
          <span>Thought Process</span>
          {timeSec && <span className="thought-process-time-chip">{timeSec}s</span>}
          {tp.query_type && (
            <span
              style={{
                fontSize: '10px',
                color: 'var(--accent-cyan)',
                background: 'rgba(56,189,248,0.1)',
                padding: '1px 6px',
                borderRadius: '4px',
              }}
            >
              {tp.query_type}
            </span>
          )}
        </div>
        <span
          style={{
            fontSize: '11px',
            color: 'var(--text-subtle)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {isExpanded ? (
            <>
              Hide details <ChevronUp size={13} />
            </>
          ) : (
            <>
              View details <ChevronDown size={13} />
            </>
          )}
        </span>
      </div>

      {isExpanded && (
        <div className="thought-process-body">
          <div className="tp-grid">
            <div className="tp-item">
              <span className="tp-label">Query Mode</span>
              <span className="tp-value">{tp.query_type || 'Targeted Code RAG'}</span>
            </div>
            <div className="tp-item">
              <span className="tp-label">LLM Engine</span>
              <span className="tp-value">{tp.llm_engine || 'NVIDIA NIM'}</span>
            </div>
            <div className="tp-item">
              <span className="tp-label">Workspace Coverage</span>
              <span className="tp-value">
                Scanned {tp.total_files_scanned || 0} files • Retrieved {tp.contexts_retrieved || 0} contexts
              </span>
            </div>
            <div className="tp-item">
              <span className="tp-label">Execution Time</span>
              <span className="tp-value">{tp.execution_time_ms ? `${tp.execution_time_ms} ms` : 'Fast'}</span>
            </div>
          </div>

          {tp.contexts_analyzed && tp.contexts_analyzed.length > 0 && (
            <div className="tp-item" style={{ marginTop: '4px' }}>
              <span className="tp-label">Context Files Analyzed</span>
              <div className="tp-chips-row">
                {tp.contexts_analyzed.map((fp, i) => (
                  <span
                    key={i}
                    className="tp-chip"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                  >
                    <FileCode2 size={11} style={{ color: 'var(--accent-cyan)' }} />
                    {fp}
                  </span>
                ))}
              </div>
            </div>
          )}

          {tp.keywords_extracted && tp.keywords_extracted.length > 0 && (
            <div className="tp-item" style={{ marginTop: '4px' }}>
              <span className="tp-label">Extracted AST Keywords</span>
              <div className="tp-chips-row">
                {tp.keywords_extracted.map((kw, i) => (
                  <span key={i} className="tp-chip" style={{ color: 'var(--accent-cyan)' }}>
                    #{kw}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
