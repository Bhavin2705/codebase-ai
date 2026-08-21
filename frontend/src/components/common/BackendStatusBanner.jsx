import React, { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, RefreshCw, CheckCircle2, WifiOff } from 'lucide-react';
import { API_BASE_URL } from '../../config';

export default function BackendStatusBanner({ onStatusChange }) {
  const [status, setStatus] = useState('checking'); // 'online' | 'offline' | 'checking'
  const [secondsOffline, setSecondsOffline] = useState(0);
  const [isManualChecking, setIsManualChecking] = useState(false);

  const checkHealth = useCallback(async (isManual = false) => {
    if (isManual) setIsManualChecking(true);
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);

      const res = await fetch(`${API_BASE_URL}/health`, {
        signal: controller.signal,
        cache: 'no-store',
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        setStatus('online');
        setSecondsOffline(0);
        if (onStatusChange) onStatusChange(true);
      } else {
        setStatus('offline');
        if (onStatusChange) onStatusChange(false);
      }
    } catch {
      setStatus('offline');
      if (onStatusChange) onStatusChange(false);
    } finally {
      if (isManual) setIsManualChecking(false);
    }
  }, [onStatusChange]);

  // Initial check on mount
  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  // Polling interval depending on state
  useEffect(() => {
    const intervalMs = status === 'offline' ? 5000 : 35000;
    const interval = setInterval(() => {
      checkHealth();
    }, intervalMs);
    return () => clearInterval(interval);
  }, [status, checkHealth]);

  // Offline timer
  useEffect(() => {
    if (status !== 'offline') {
      setSecondsOffline(0);
      return;
    }
    const timer = setInterval(() => {
      setSecondsOffline((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [status]);

  if (status === 'online') {
    return null;
  }

  return (
    <div
      style={{
        background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.12) 0%, rgba(239, 68, 68, 0.12) 100%)',
        borderBottom: '1px solid rgba(245, 158, 11, 0.35)',
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        fontSize: '12px',
        color: '#fbbf24',
        zIndex: 50,
        animation: 'fadeIn 0.2s ease-in',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
        <div
          style={{
            width: '24px',
            height: '24px',
            borderRadius: '6px',
            background: 'rgba(245, 158, 11, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {status === 'checking' ? (
            <RefreshCw size={13} className="spin-slow" style={{ color: '#fbbf24' }} />
          ) : (
            <AlertTriangle size={13} style={{ color: '#f59e0b' }} />
          )}
        </div>

        <div style={{ lineHeight: 1.4 }}>
          <strong style={{ color: '#fef3c7', fontWeight: 600 }}>
            {status === 'checking'
              ? 'Checking backend connection...'
              : 'Backend server is waking up / temporarily offline'}
          </strong>
          <span style={{ color: 'rgba(254, 243, 199, 0.75)', marginLeft: '8px' }}>
            {status === 'offline' && (
              <>
                Render free instance sleeps when idle. Booting up now (~30–50s). Will auto-reconnect
                {secondsOffline > 0 ? ` (${secondsOffline}s elapsed)` : ''}.
              </>
            )}
          </span>
        </div>
      </div>

      <button
        onClick={() => checkHealth(true)}
        disabled={isManualChecking}
        style={{
          background: 'rgba(245, 158, 11, 0.18)',
          border: '1px solid rgba(245, 158, 11, 0.4)',
          borderRadius: '6px',
          color: '#fef3c7',
          padding: '4px 10px',
          fontSize: '11px',
          fontWeight: 600,
          cursor: isManualChecking ? 'not-allowed' : 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          flexShrink: 0,
          transition: 'all 0.15s ease',
        }}
      >
        <RefreshCw
          size={11}
          style={{
            animation: isManualChecking ? 'spin 1s linear infinite' : 'none',
          }}
        />
        <span>{isManualChecking ? 'Checking...' : 'Check Status'}</span>
      </button>
    </div>
  );
}
