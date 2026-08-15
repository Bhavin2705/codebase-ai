export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// API key is injected at build time via VITE_API_KEY (set in Vercel env vars).
// Never stored in localStorage — no runtime UI for key entry.
const API_KEY = import.meta.env.VITE_API_KEY || '';

export const getAuthHeaders = (extraHeaders = {}) => {
  const headers = { ...extraHeaders };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
};
