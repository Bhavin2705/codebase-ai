import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import NavPanel from '../navigation/NavPanel';
import ChatPanel from '../chat/ChatPanel';
import EvidencePanel from '../evidence/EvidencePanel';
import { MOCK_CONVERSATIONS } from '../../data/mockData';
import { API_BASE_URL } from '../../config';

export default function ThreePanelLayout({ selectedRepo }) {
  const { repoId } = useParams();
  const navigate = useNavigate();

  const currentRepoId = repoId || (selectedRepo ? selectedRepo.id : 'repo-1');
  const repoName = selectedRepo ? selectedRepo.name : (currentRepoId === 'repo-1' ? 'spring-projects/spring-petclinic' : currentRepoId);

  const [conversations, setConversations] = useState([]);
  const [activeCitation, setActiveCitation] = useState(null);

  // Sync URL in address bar if /workspace without :repoId
  useEffect(() => {
    if (!repoId && currentRepoId) {
      navigate(`/workspace/${currentRepoId}`, { replace: true });
    }
  }, [repoId, currentRepoId, navigate]);

  useEffect(() => {
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_id: currentRepoId,
          question: qText
        })
      });

      if (!res.ok) {
        throw new Error('Failed to retrieve AI answer');
      }

      const data = await res.json();
      setConversations((prev) =>
        prev.map((msg) => (msg.id === tempId ? data : msg))
      );

      if (data.citations && data.citations.length > 0) {
        setActiveCitation(data.citations[0]);
      }
    } catch (err) {
      setConversations((prev) =>
        prev.map((msg) =>
          msg.id === tempId
            ? { ...msg, answer: `Error retrieving grounded answer: ${err.message}` }
            : msg
        )
      );
    }
  };

  return (
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
  );
}
