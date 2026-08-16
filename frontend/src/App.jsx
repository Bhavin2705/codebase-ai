import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import Header from './components/layout/Header';
import ThreePanelLayout from './components/layout/ThreePanelLayout';
import RepoOverview from './components/overview/RepoOverview';
import RepoImportModal from './components/import/RepoImportModal';
import { API_BASE_URL } from './config';

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();

  const [repositories, setRepositories] = useState(() => {
    try {
      const cached = localStorage.getItem('app_repositories');
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  });

  const [selectedRepo, setSelectedRepo] = useState(() => {
    try {
      const cachedId = localStorage.getItem('app_selected_repo_id');
      const cachedList = JSON.parse(localStorage.getItem('app_repositories') || '[]');
      return cachedList.find((r) => r.id === cachedId) || cachedList[0] || null;
    } catch {
      return null;
    }
  });

  const [isImportOpen, setIsImportOpen] = useState(false);

  // Sync state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('app_repositories', JSON.stringify(repositories));
    } catch {}
  }, [repositories]);

  useEffect(() => {
    if (selectedRepo?.id) {
      try {
        localStorage.setItem('app_selected_repo_id', selectedRepo.id);
      } catch {}
    }
  }, [selectedRepo]);

  // Sync selectedRepo when URL is /workspace/:repoId
  useEffect(() => {
    if (location.pathname.startsWith('/workspace/')) {
      const urlRepoId = location.pathname.split('/workspace/')[1];
      if (urlRepoId && urlRepoId !== selectedRepo?.id) {
        const found = repositories.find((r) => r.id === urlRepoId);
        if (found) setSelectedRepo(found);
      }
    }
  }, [location.pathname, repositories, selectedRepo]);

  // Fetch repositories from live API
  useEffect(() => {
    fetch(`${API_BASE_URL}/repositories`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setRepositories(data);
          setSelectedRepo((prev) => {
            const found = data.find((r) => r.id === prev?.id || r.name === prev?.name);
            return found || data[0];
          });
        }
      })
      .catch((err) => console.error('Failed to fetch repositories list:', err));
  }, []);

  const handleSelectRepo = (repo) => {
    setSelectedRepo(repo);
    if (location.pathname.startsWith('/workspace')) {
      navigate(`/workspace/${repo.id}`);
    }
  };

  const handleStartIndexing = (repoObj) => {
    setIsImportOpen(false);
    setRepositories((prev) => {
      const idx = prev.findIndex((r) => r.id === repoObj.id);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = repoObj;
        return copy;
      }
      return [repoObj, ...prev];
    });
    setSelectedRepo(repoObj);

    if (location.pathname.startsWith('/workspace')) {
      navigate(`/workspace/${repoObj.id}`);
    }
  };

  return (
    <>
      <Header
        repositories={repositories}
        selectedRepo={selectedRepo}
        onSelectRepo={handleSelectRepo}
        onOpenImport={() => setIsImportOpen(true)}
      />

      <Routes>
        <Route
          path="/"
          element={
            <RepoOverview
              repo={selectedRepo}
              onSelectQuestion={(q) => {
                const dest = selectedRepo?.id ? `/workspace/${selectedRepo.id}` : '/workspace';
                navigate(dest, { state: { initialQuestion: q } });
              }}
            />
          }
        />
        <Route
          path="/workspace/:repoId"
          element={<ThreePanelLayout selectedRepo={selectedRepo} />}
        />
        <Route
          path="/workspace"
          element={<ThreePanelLayout selectedRepo={selectedRepo} />}
        />
      </Routes>

      <RepoImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onStartIndexing={handleStartIndexing}
      />
    </>
  );
}
