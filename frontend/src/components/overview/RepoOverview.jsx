import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, HelpCircle } from 'lucide-react';

export default function RepoOverview({ repo, repositories, onSelectQuestion }) {
  const navigate = useNavigate();

  const currentRepo = (repositories && repo)
    ? (repositories.find((r) => r.id === repo.id || (repo.name && r.name === repo.name)) || repo)
    : repo;

  const handleOpenWorkspace = () => {
    if (currentRepo?.id) {
      navigate(`/workspace/${currentRepo.id}`);
    } else {
      navigate('/workspace');
    }
  };

  const handleQuestionClick = (q) => {
    if (onSelectQuestion) {
      onSelectQuestion(q);
    } else {
      navigate(currentRepo?.id ? `/workspace/${currentRepo.id}` : '/workspace');
    }
  };

  const getStarterQuestions = () => {
    const lang = currentRepo?.language ? currentRepo.language.toLowerCase() : '';

    if (lang.includes('python')) {
      return [
        "How is the main entry point or module structure organized in this repository?",
        "Where are data processing algorithms and utility functions implemented?",
        "How are dependencies and configuration files structured across packages?",
        "What key functions or classes handle core data flow?"
      ];
    } else if (lang.includes('java') || lang.includes('spring')) {
      return [
        "How does authentication & security authorization work in this repository?",
        "Explain the data repository persistence layer for entities.",
        "Where are API endpoints handled for controllers?",
        "How is caching configured across services?"
      ];
    } else if (lang.includes('js') || lang.includes('react') || lang.includes('node') || lang.includes('mern')) {
      return [
        "How are Express routes and middleware configured?",
        "Where are React components and state management handled?",
        "Explain Mongoose database schemas and models.",
        "How are environment variables and config initialized?"
      ];
    }

    return [
      "Explain the overall architecture and folder structure of this repository.",
      "Where are primary business logic and entry points defined?",
      "How are configuration and environment variables managed?",
      "What key utility services or helpers are used throughout?"
    ];
  };

  const getDisplayStatus = (status) => {
    if (!status || status === 'ready' || status === 'indexed' || status === 'completed') {
      return 'indexed';
    }
    if (status === 'error' || status === 'failed') {
      return 'error';
    }
    return 'indexing...';
  };

  const questions = getStarterQuestions();

  if (!currentRepo) {
    return (
      <div className="overview-container">
        <div className="overview-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
          <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-main)' }}>
            No Repository Selected
          </h1>
          <p style={{ color: 'var(--text-subtle)', fontSize: '13px', marginTop: '8px' }}>
            Import a GitHub repository using the header button to start indexing and querying source code.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="overview-container">
      <div className="overview-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-main)', letterSpacing: '-0.2px' }}>
              {currentRepo.name}
            </h1>
            <p style={{ color: 'var(--text-subtle)', fontSize: '12px', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
              {currentRepo.github_url || ''}
            </p>
          </div>
          <button className="btn btn-primary" onClick={handleOpenWorkspace} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span>Open Workspace</span>
            <ArrowRight size={14} />
          </button>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '12px',
          marginTop: '16px',
          paddingTop: '12px',
          borderTop: '1px solid var(--border-color)'
        }}>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-subtle)', letterSpacing: '0.5px' }}>PRIMARY LANGUAGE</div>
            <div className="stat-metric">{currentRepo.language || 'Multi-Language'}</div>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-subtle)', letterSpacing: '0.5px' }}>INDEXED FILES</div>
            <div className="stat-metric">{currentRepo.stats?.files ?? currentRepo.file_count ?? 0} Files</div>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-subtle)', letterSpacing: '0.5px' }}>EXTRACTED SYMBOLS</div>
            <div className="stat-metric">{currentRepo.stats?.symbols ?? currentRepo.stats?.classes ?? currentRepo.symbol_count ?? 0} Symbols</div>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-subtle)', letterSpacing: '0.5px' }}>STATUS</div>
            <div
              className="stat-metric"
              style={{
                fontSize: '11px',
                color: (currentRepo.status === 'error' || currentRepo.status === 'failed')
                  ? '#f87171'
                  : 'var(--accent-cyan)'
              }}
            >
              {getDisplayStatus(currentRepo.status)}
            </div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: '24px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <HelpCircle size={16} style={{ color: 'var(--accent-cyan)' }} />
          <span>Starter Questions</span>
        </h2>
        <div className="questions-grid">
          {questions.map((q, idx) => (
            <div
              key={idx}
              className="question-card"
              onClick={() => handleQuestionClick(q)}
            >
              <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-main)', lineHeight: 1.5 }}>
                {q}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
