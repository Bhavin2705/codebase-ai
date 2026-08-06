import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import Header from './components/layout/Header';
import ThreePanelLayout from './components/layout/ThreePanelLayout';
import RepoOverview from './components/overview/RepoOverview';
import RepoImportModal from './components/import/RepoImportModal';
import { MOCK_REPOSITORIES } from './data/mockData';
import { API_BASE_URL } from './config';

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();

  // Helper to deduplicate repositories by name
  const deduplicateRepos = (list) => {
    if (!Array.isArray(list)) return MOCK_REPOSITORIES;
    const map = new Map();
    list.forEach((repo) => {
      if (repo && repo.name && !map.has(repo.name)) {
        map.set(repo.name, repo);
      }
    });
    return Array.from(map.values());
  };

  // Instant local hydration from localStorage
  const [repositories, setRepositories] = useState(() => {
    try {
      const cached = localStorage.getItem('app_repositories');
      return cached ? deduplicateRepos(JSON.parse(cached)) : MOCK_REPOSITORIES;
    } catch {
      return MOCK_REPOSITORIES;
    }
  });

  const [selectedRepo, setSelectedRepo] = useState(() => {
    try {
      const cachedId = localStorage.getItem('app_selected_repo_id');
      const cachedList = deduplicateRepos(JSON.parse(localStorage.getItem('app_repositories') || '[]'));
      const found = cachedList.find((r) => r.id === cachedId);
      return found || cachedList[0] || MOCK_REPOSITORIES[0];
    } catch {
      return MOCK_REPOSITORIES[0];
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
    if (selectedRepo && selectedRepo.id) {
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
        if (found) {
          setSelectedRepo(found);
        }
      }
    }
  }, [location.pathname, repositories, selectedRepo]);

  // Fetch updated list from backend asynchronously
  useEffect(() => {
    fetch(`${API_BASE_URL}/repositories`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const uniqueData = deduplicateRepos(data);
          setRepositories(uniqueData);
          setSelectedRepo((prev) => {
            const found = uniqueData.find((r) => r.id === prev?.id || r.name === prev?.name);
            return found || uniqueData[0];
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
              onSelectQuestion={() => {}}
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
