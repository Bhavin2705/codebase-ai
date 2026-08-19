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

  const [repositories, setRepositories] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [isImportOpen, setIsImportOpen] = useState(false);

  // Remember selected repo ID across reloads
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

  // Fetch repositories from live API (single source of truth)
  const refreshRepositories = () => {
    return fetch(`${API_BASE_URL}/repositories`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setRepositories(data);
          setSelectedRepo((prev) => {
            if (!data.length) return null;
            if (location.pathname.startsWith('/workspace/')) {
              const urlRepoId = location.pathname.split('/workspace/')[1];
              if (urlRepoId) {
                const found = data.find((r) => r.id === urlRepoId);
                if (found) return found;
              }
            }
            if (prev) {
              const found = data.find((r) => r.id === prev.id || r.name === prev.name);
              if (found) return found;
            }
            const cachedId = localStorage.getItem('app_selected_repo_id');
            if (cachedId) {
              const found = data.find((r) => r.id === cachedId);
              if (found) return found;
            }
            return data[0];
          });
        }
      })
      .catch((err) => console.error('Failed to fetch repositories list:', err));
  };

  useEffect(() => {
    refreshRepositories();
  }, []);

  // Polling while any repository is indexing / pending
  useEffect(() => {
    const hasActiveIndexing = repositories.some(
      (r) => r.status && r.status !== 'ready' && r.status !== 'error' && r.status !== 'failed'
    );

    const intervalTime = hasActiveIndexing ? 1000 : 5000;
    const interval = setInterval(refreshRepositories, intervalTime);
    return () => clearInterval(interval);
  }, [repositories]);

  const handleSelectRepo = (repo) => {
    setSelectedRepo(repo);
    if (location.pathname.startsWith('/workspace')) {
      navigate(`/workspace/${repo.id}`);
    }
  };

  const handleStartIndexing = (repoObj) => {
    setIsImportOpen(false);
    const initialObj = {
      ...repoObj,
      status: 'indexing',
    };
    setRepositories((prev) => {
      const idx = prev.findIndex((r) => r.id === repoObj.id || (repoObj.name && r.name === repoObj.name));
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = initialObj;
        return copy;
      }
      return [initialObj, ...prev];
    });
    setSelectedRepo(initialObj);
    setTimeout(refreshRepositories, 1000);

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
              repositories={repositories}
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
