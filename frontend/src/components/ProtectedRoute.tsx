import { Navigate, Outlet, useLocation } from 'react-router-dom';

import type { components } from '@/api/schema';
import { useMe } from '@/hooks/useAuth';
import { tokenStore } from '@/lib/tokens';

type Role = components['schemas']['Role'];

interface Props {
  /** Restrict to these roles. Omit to allow any logged-in user. */
  roles?: Role[];
}

export default function ProtectedRoute({ roles }: Props) {
  const location = useLocation();
  const me = useMe();

  if (!tokenStore.getAccess() || me.isError) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (me.isPending) {
    return <p className="p-8 text-sm text-muted-foreground">Loading…</p>;
  }

  if (roles && !roles.includes(me.data.role)) {
    return (
      <main className="mx-auto max-w-xl p-8">
        <h1 className="text-xl font-semibold">Not allowed</h1>
        <p className="mt-2 text-sm text-muted-foreground">Your role ({me.data.role}) cannot open this page.</p>
      </main>
    );
  }

  return <Outlet />;
}
