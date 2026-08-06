import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, HelpCircle } from 'lucide-react';

export default function RepoOverview({ repo, onSelectQuestion }) {
  const navigate = useNavigate();
  const targetRepoId = repo ? repo.id : 'repo-1';

  const handleOpenWorkspace = () => {
    navigate(`/workspace/${targetRepoId}`);
  };

  const handleQuestionClick = (q) => {
    if (onSelectQuestion) onSelectQuestion(q);
    navigate(`/workspace/${targetRepoId}`);
  };

  const getStarterQuestions = () => {
    const lang = repo && repo.language ? repo.language.toLowerCase() : '';

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

  const questions = getStarterQuestions();

  return (
    <div className="overview-container">
      <div className="overview-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-main)', letterSpacing: '-0.2px' }}>
              {repo ? repo.name : 'spring-projects/spring-petclinic'}
            </h1>
            <p style={{ color: 'var(--text-subtle)', fontSize: '12px', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
              {repo ? (repo.github_url || repo.url) : 'https://github.com/spring-projects/spring-petclinic'}
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
            <div className="stat-metric">{repo ? repo.language : 'Java / Spring Boot'}</div>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-subtle)', letterSpacing: '0.5px' }}>INDEXED FILES</div>
            <div className="stat-metric">{repo && repo.stats ? repo.stats.files : 42} Files</div>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-subtle)', letterSpacing: '0.5px' }}>PARSED SYMBOLS</div>
            <div className="stat-metric">{repo && repo.stats ? repo.stats.classes : 128} Symbols</div>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-subtle)', letterSpacing: '0.5px' }}>STACK SUPPORT</div>
            <div className="stat-metric" style={{ fontSize: '11px', color: 'var(--accent-cyan)' }}>
              {repo ? repo.language : 'Multi-Language'}
            </div>
          </div>
        </div>
      </div>

      <div className="overview-card">
        <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
          Suggested Starter Questions for {repo ? repo.name.split('/').pop() : 'Repository'}
        </h3>
        <p style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px' }}>
          Click a question to launch RAG semantic search and evidence code retrieval:
        </p>

        <div className="questions-grid">
          {questions.map((q, idx) => (
            <div
              key={idx}
              className="question-card"
              onClick={() => handleQuestionClick(q)}
            >
              <HelpCircle size={14} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: '2px' }} />
              <span style={{ lineHeight: '1.4' }}>{q}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
