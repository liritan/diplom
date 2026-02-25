import axios from 'axios';

function detectRuntimeBaseUrl() {
  const envBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
  if (envBase) return envBase;

  if (typeof window !== "undefined") {
    const { protocol, hostname, port, origin } = window.location;
    const isLocal = hostname === "localhost" || hostname === "127.0.0.1";
    if (isLocal && (port === "3000" || port === "3001")) {
      return `${protocol}//${hostname}:8000/api/v1`;
    }
    return `${origin}/api/v1`;
  }

  return "http://localhost:8000/api/v1";
}

const api = axios.create({
  baseURL: detectRuntimeBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
