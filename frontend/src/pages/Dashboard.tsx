import { useLogout, useMe } from '@/hooks/useAuth';

const ROLE_LABEL = {
  admin: 'Administrator',
  institution: 'Institution',
  verifier: 'Verifier',
} as const;

export default function Dashboard() {
  const { data: user } = useMe();
  const logout = useLogout();

  // ProtectedRoute only renders this once the user has loaded.
  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
          <span className="font-semibold">Authenticity Validator</span>
          <button
            onClick={logout}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            Log out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="text-2xl font-semibold">Dashboard</h1>

        <dl className="mt-6 grid max-w-md grid-cols-[auto_1fr] gap-x-6 gap-y-2 rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <dt className="text-slate-500">Signed in as</dt>
          <dd className="font-medium">{user.email}</dd>
          <dt className="text-slate-500">Role</dt>
          <dd>
            <span className="rounded bg-slate-100 px-2 py-0.5 font-medium">{ROLE_LABEL[user.role]}</span>
          </dd>
          {user.institution && (
            <>
              <dt className="text-slate-500">Institution</dt>
              <dd>
                {user.institution.name} ({user.institution.code})
              </dd>
            </>
          )}
        </dl>

        <p className="mt-6 text-sm text-slate-500">
          Prototype — all data is synthetic. More features arrive with the rest of Tier 1.
        </p>
      </main>
    </div>
  );
}
