import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { api, type LoginRequest, type TokenPair, type UserOut } from '@/api/client';
import { tokenStore } from '@/lib/tokens';

export const ME_QUERY_KEY = ['auth', 'me'] as const;

/** The logged-in user. Disabled (no request) when there is no token. */
export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => (await api.get<UserOut>('/auth/me')).data,
    enabled: tokenStore.getAccess() !== null,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: LoginRequest) => (await api.post<TokenPair>('/auth/login', body)).data,
    onSuccess: (tokens) => {
      tokenStore.set(tokens);
      return queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return () => {
    tokenStore.clear();
    queryClient.clear();
    navigate('/login', { replace: true });
  };
}
