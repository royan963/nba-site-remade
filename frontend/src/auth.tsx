import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { apiGet, apiSend } from './api/client';
import type { Me } from './api/types';

interface AuthState {
  user: Me | null;
  ready: boolean;                        // false until we've asked the server who's signed in
  signIn: (email: string, password: string) => Promise<Me>;
  signUp: (body: { email: string; username: string; password: string; display_name?: string }) => Promise<Me>;
  signOut: () => Promise<void>;
  setUser: (u: Me | null) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    apiGet<Me | null>('/auth/me', { fresh: true }).then(setUser, () => setUser(null)).finally(() => setReady(true));
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const me = await apiSend<Me>('POST', '/auth/login', { email, password });
    setUser(me);
    return me;
  }, []);
  const signUp = useCallback(async (body: { email: string; username: string; password: string; display_name?: string }) => {
    const me = await apiSend<Me>('POST', '/auth/register', body);
    setUser(me);
    return me;
  }, []);
  const signOut = useCallback(async () => {
    await apiSend('POST', '/auth/logout');
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, ready, signIn, signUp, signOut, setUser }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
