import React, { useState, useEffect } from 'react';
import { Folder, FolderOpen, ChevronRight, ChevronDown, FileCode, FileText } from 'lucide-react';
import { API_BASE_URL } from '../../config';

export default function NavPanel({ repoId: propRepoId, selectedRepo, onSelectFile }) {
  const repoId = propRepoId || selectedRepo?.id;
  const [tree, setTree] = useState([]);
  const [collapsedPaths, setCollapsedPaths] = useState(new Set());

  useEffect(() => {
    if (!repoId) {
      setTree([]);
      setCollapsedPaths(new Set());
      return;
    }

    fetch(`${API_BASE_URL}/repositories/${encodeURIComponent(repoId)}/tree`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setTree(data);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch repo tree:', err);
        setTree([]);
      });
  }, [repoId, selectedRepo?.status, selectedRepo?.stats?.files, selectedRepo?.file_count]);

  const toggleFolder = (folderKey) => {
    setCollapsedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(folderKey)) {
        next.delete(folderKey);
      } else {
        next.add(folderKey);
      }
      return next;
    });
  };

  const renderTree = (nodes, parentPath = '') => {
    if (!Array.isArray(nodes)) return null;
    return nodes.map((node, i) => {
      const isDir = node.type === 'dir' || node.type === 'folder' || Boolean(node.children);
      const name = node.name || (node.path ? node.path.split('/').pop() : 'folder');
      const nodeKey = node.path || (parentPath ? `${parentPath}/${name}` : `${name}-${i}`);

      if (isDir) {
        const isCollapsed = collapsedPaths.has(nodeKey);
        return (
          <div key={nodeKey || i} style={{ marginLeft: '6px' }}>
            <div
              className="tree-node dir"
              onClick={() => toggleFolder(nodeKey)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              {isCollapsed ? (
                <ChevronRight size={12} style={{ color: 'var(--text-subtle)', flexShrink: 0 }} />
              ) : (
                <ChevronDown size={12} style={{ color: 'var(--text-subtle)', flexShrink: 0 }} />
              )}
              {isCollapsed ? (
                <Folder size={14} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
              ) : (
                <FolderOpen size={14} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
              )}
              <span>{name}</span>
            </div>
            {!isCollapsed && node.children && node.children.length > 0 && renderTree(node.children, nodeKey)}
          </div>
        );
      }

      const isDoc = name.endsWith('.md') || name.endsWith('.txt');

      return (
        <div 
          key={node.path || `${parentPath}/${name}-${i}`} 
          className="tree-node file" 
          onClick={() => onSelectFile && onSelectFile(node.path)}
        >
          {isDoc ? (
            <FileText size={14} style={{ color: 'var(--text-subtle)', flexShrink: 0 }} />
          ) : (
            <FileCode size={14} style={{ color: 'var(--accent-violet)', flexShrink: 0 }} />
          )}
          <span>{name}</span>
        </div>
      );
    });
  };

  return (
    <nav className="nav-panel">
      <div className="panel-header">Repository Explorer</div>
      <div className="nav-section">
        {renderTree(tree)}
      </div>
    </nav>
  );
}
