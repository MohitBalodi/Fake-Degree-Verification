import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

const apiRoot = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export default function Home() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await axios.get<{ status: string; env: string }>(`${apiRoot}/health`);
      return response.data;
    },
  });

  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">Authenticity Validator for Academia</h1>
      <p className="mt-2 text-sm text-slate-600">
        Prototype. All data is synthetic — no real university or DigiLocker access.
      </p>

      <div className="mt-6 rounded border border-slate-200 p-4">
        <h2 className="font-medium">API status</h2>
        {isPending && <p className="text-sm text-slate-500">Checking…</p>}
        {isError && <p className="text-sm text-red-600">Cannot reach {apiRoot}/health</p>}
        {data && (
          <p className="text-sm text-green-700">
            {data.status} ({data.env})
          </p>
        )}
      </div>
    </main>
  );
}
