import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

export default function LoadingStopwatch() {
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
        <span style={{ fontSize: '11px', color: 'var(--text-subtle)', fontFamily: 'var(--font-mono)' }}>
          Generating answer...
        </span>
      </div>
    </div>
  );
}
