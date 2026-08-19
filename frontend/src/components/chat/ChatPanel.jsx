import React, { useState, useEffect, useRef } from 'react';
import { Clock, Brain, ChevronDown, ChevronUp, FileCode2, MapPin, Send, RotateCcw, Trash2 } from 'lucide-react';

function LoadingStopwatch() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    const timer = setInterval(() => {
      setElapsed((Date.now() - startTime) / 1000);
    }, 100);
    return () => clearInterval(timer);
  }, []);

  const secStr = Math.floor(elapsed).toString().padStart(2, '0');
  const tenthStr = Math.floor((elapsed % 1) * 10);
  const formattedTime = `00:${secStr}.${tenthStr}`;

  return (
    <div className="loading-box">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="stopwatch-badge">
          <div className="spinner-pulse"></div>
          <Clock size={12} style={{ color: 'var(--accent-cyan)' }} />
          <span>{formattedTime}</span>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-subtle)', fontFamily: 'var(--font-mono)' }}>Generating answer...</span>
      </div>
    </div>
  );
}

function ThoughtProcessWidget({ thoughtProcess, executionTimeMs }) {
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
            <span style={{ fontSize: '10px', color: 'var(--accent-cyan)', background: 'rgba(56,189,248,0.1)', padding: '1px 6px', borderRadius: '4px' }}>
              {tp.query_type}
            </span>
          )}
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-subtle)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          {isExpanded ? (
            <>Hide details <ChevronUp size={13} /></>
          ) : (
            <>View details <ChevronDown size={13} /></>
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
                  <span key={i} className="tp-chip" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
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
                  <span key={i} className="tp-chip" style={{ color: 'var(--accent-cyan)' }}>#{kw}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatPanel({ conversations, onSelectCitation, onAskQuestion, onClearChat }) {
  const [input, setInput] = useState('');
  const inputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onAskQuestion(input.trim());
    setInput('');
  };

  const handleEditQuestion = (questionText) => {
    setInput(questionText);
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Parses markdown headers (###), bold text (**), lists (-), inline code (`code`), and citation markers
  const renderFormattedAnswer = (text, citations = []) => {
    if (!text) return null;

    // First handle [Label](cite:filePath#Lstart-Lend) replacements
    const citeRegex = /\[([^\]]+)\]\(cite:([^#]+)#L(\d+)-L(\d+)\)/g;
    const segments = [];
    let lastIdx = 0;
    let match;

    while ((match = citeRegex.exec(text)) !== null) {
      const [fullMatch, labelText, filePath, startLine, endLine] = match;
      const matchIndex = match.index;

      if (matchIndex > lastIdx) {
        segments.push({ type: 'text', content: text.substring(lastIdx, matchIndex) });
      }

      segments.push({
        type: 'cite',
        labelText,
        filePath,
        startLine: parseInt(startLine, 10),
        endLine: parseInt(endLine, 10),
        index: matchIndex
      });

      lastIdx = citeRegex.lastIndex;
    }

    if (lastIdx < text.length) {
      segments.push({ type: 'text', content: text.substring(lastIdx) });
    }

    return segments.map((seg, idx) => {
      if (seg.type === 'cite') {
        const normalizedPath = seg.filePath.replace(/\\/g, '/');
        const fileName = normalizedPath.split('/').pop();
        return (
          <button
            key={`cite-${idx}-${seg.startLine}`}
            className="inline-citation"
            onClick={() =>
              onSelectCitation({
                filePath: seg.filePath,
                startLine: seg.startLine,
                endLine: seg.endLine,
                label: seg.labelText || `${fileName}:${seg.startLine}`,
                symbol: fileName
              })
            }
          >
            {seg.labelText || `${fileName}:${seg.startLine}-${seg.endLine}`}
          </button>
        );
      }

      // Parse markdown block elements (#, ##, ### headers, **bold**, - lists, code blocks)
      const rawContent = seg.content;
      const lines = rawContent.split('\n');
      const renderedElements = [];
      let inCodeBlock = false;
      let codeBuffer = [];

      lines.forEach((rawLine, lineIdx) => {
        const line = rawLine.trim();

        if (line.startsWith('```')) {
          if (inCodeBlock) {
            renderedElements.push(
              <pre key={`code-${lineIdx}`} style={{
                background: 'rgba(15, 23, 42, 0.6)',
                padding: '10px 14px',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                overflowX: 'auto',
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
                margin: '8px 0'
              }}>
                <code>{codeBuffer.join('\n')}</code>
              </pre>
            );
            codeBuffer = [];
            inCodeBlock = false;
          } else {
            inCodeBlock = true;
          }
          return;
        }

        if (inCodeBlock) {
          codeBuffer.push(rawLine);
          return;
        }

        if (line === '.') return;

        if (line.startsWith('### ')) {
          renderedElements.push(<h3 key={lineIdx} style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-main)', marginTop: '8px', marginBottom: '4px' }}>{parseInlineMarkdown(line.replace('### ', ''))}</h3>);
          return;
        }
        if (line.startsWith('- ') || line.startsWith('* ')) {
          renderedElements.push(<li key={lineIdx} style={{ marginLeft: '16px', marginBottom: '3px' }}>{parseInlineMarkdown(line.substring(2))}</li>);
          return;
        }

        if (!line) {
          renderedElements.push(<br key={lineIdx} />);
          return;
        }

        renderedElements.push(
          <React.Fragment key={lineIdx}>
            {parseInlineMarkdown(rawLine)}
            {lineIdx < lines.length - 1 && <br />}
          </React.Fragment>
        );
      });

      return (
        <span key={`text-block-${idx}`}>
          {renderedElements}
        </span>
      );
    });
  };

  const parseInlineMarkdown = (lineStr) => {
    const parts = lineStr.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return parts.map((part, pIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={pIdx}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={pIdx}>{part.slice(1, -1)}</code>;
      }
      return part;
    });
  };

  return (
    <main className="chat-panel">
      {conversations.length > 1 && onClearChat && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '10px 20px 0' }}>
          <button
            type="button"
            onClick={onClearChat}
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-subtle)',
              fontSize: '11px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              cursor: 'pointer',
              padding: '4px 10px',
              borderRadius: '6px',
              transition: 'all 0.15s ease'
            }}
            title="Clear conversation history"
          >
            <Trash2 size={12} />
            <span>Clear History</span>
          </button>
        </div>
      )}

      <div className="chat-messages">
        {conversations.map((msg) => (
          <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div className="message-bubble user">
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
                <h2 className="user-question-header" style={{ margin: 0, flex: 1 }}>{msg.question}</h2>
                {!msg.id?.startsWith('init-') && (
                  <button
                    type="button"
                    title="Load question into input to tweak and re-ask"
                    onClick={() => handleEditQuestion(msg.question)}
                    style={{
                      background: 'rgba(56, 189, 248, 0.08)',
                      border: '1px solid rgba(56, 189, 248, 0.25)',
                      color: 'var(--accent-cyan)',
                      borderRadius: '6px',
                      padding: '3px 8px',
                      fontSize: '11px',
                      fontWeight: 500,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      cursor: 'pointer',
                      flexShrink: 0,
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <RotateCcw size={11} />
                    <span>Re-ask</span>
                  </button>
                )}
              </div>
            </div>

            <div className="message-bubble assistant">
              {msg.isPending && !msg.answer ? (
                <LoadingStopwatch />
              ) : (
                <>
                  <ThoughtProcessWidget
                    thoughtProcess={msg.thought_process}
                    executionTimeMs={msg.execution_time_ms}
                  />

                  <div className="answer-body">
                    {renderFormattedAnswer(msg.answer, msg.citations)}
                    {msg.isPending && <span className="streaming-cursor" style={{ display: 'inline-block', width: '6px', height: '14px', background: 'var(--accent-cyan)', marginLeft: '4px', verticalAlign: 'middle', animation: 'pulse 1s infinite' }}></span>}
                  </div>

                  {msg.citations && msg.citations.length > 0 && (
                    <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px solid var(--border-color)' }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-subtle)', marginBottom: '6px', letterSpacing: '0.6px' }}>
                        REFERENCED SOURCE EVIDENCE:
                      </div>
                      {msg.citations.map((cite) => (
                        <button
                          key={cite.id}
                          className="citation-chip"
                          onClick={() => onSelectCitation(cite)}
                        >
                          <MapPin size={11} style={{ color: 'var(--accent-cyan)' }} />
                          {cite.label}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="chat-input-container">
        <form onSubmit={handleSubmit} className="chat-input-box">
          <input
            ref={inputRef}
            type="text"
            className="chat-input"
            placeholder="Ask codebase architecture or implementation question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span>Ask</span>
            <Send size={13} />
          </button>
        </form>
      </div>
    </main>
  );
}