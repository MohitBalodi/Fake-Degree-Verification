// Token storage. localStorage keeps the prototype simple; a production build
// would move the refresh token to an httpOnly cookie.

const ACCESS_KEY = 'ava.access_token';
const REFRESH_KEY = 'ava.refresh_token';

export interface Tokens {
  access_token: string;
  refresh_token: string;
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokenStore = {
  getAccess: () => read(ACCESS_KEY),
  getRefresh: () => read(REFRESH_KEY),
  set(tokens: Tokens) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      // storage unavailable — nothing to clear
    }
  },
};
