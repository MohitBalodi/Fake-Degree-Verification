import axios from 'axios';

export const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}/api/v1`,
  withCredentials: false,
});

// Auth interceptors (access token + refresh on 401) are added with Tier 1 auth.
