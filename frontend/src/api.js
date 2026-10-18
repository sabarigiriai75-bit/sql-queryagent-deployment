// Central API base URL — reads from VITE_API_BASE_URL env var (set at build time).
// Falls back to localhost:8000 for local development.
const raw = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Render exposes the host without a scheme; add https:// if needed.
export const API_BASE = raw.startsWith('http') ? raw : `https://${raw}`;
