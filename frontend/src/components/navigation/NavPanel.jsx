import React, { useState, useEffect } from 'react';
import { Folder, FileCode, FileText } from 'lucide-react';
import { API_BASE_URL } from '../../config';

export default function NavPanel({ selectedRepo, onSelectFile }) {
  const repoId = selectedRepo?.id;
  const [tree, setTree] = useState([]);

  useEffect(() => {
    if (!repoId) {
      setTree([]);
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
  }, [repoId]);

  const renderTree = (nodes) => {
    if (!Array.isArray(nodes)) return null;
    return nodes.map((node, i) => {
      const isDir = node.type === 'dir' || node.type === 'folder' || Boolean(node.children);
      const name = node.name || (node.path ? node.path.split('/').pop() : 'folder');

      if (isDir) {
        return (
          <div key={i} style={{ marginLeft: '6px' }}>
            <div className="tree-node dir">
              <Folder size={14} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
              <span>{name}</span>
            </div>
            {node.children && node.children.length > 0 && renderTree(node.children)}
          </div>
        );
      }

      const isDoc = name.endsWith('.md') || name.endsWith('.txt');

      return (
        <div 
          key={i} 
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
