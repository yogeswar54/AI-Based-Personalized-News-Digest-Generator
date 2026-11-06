import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDigestHistory } from "../services/personalizationService.js";

export default function DigestHistoryPage() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDigestHistory({ page: 1, limit: 30 })
      .then(setResult)
      .catch((requestError) => setError(requestError?.response?.data?.detail || "Unable to load digest history."));
  }, []);

  return (
    <section className="mx-auto max-w-5xl px-6 py-12 sm:px-10">
      <Link to="/digests" className="text-sm font-semibold text-green-900 underline">Today's digest</Link>
      <h1 className="mt-4 text-3xl font-semibold text-stone-950">Digest history</h1>
      {error && <p role="alert" className="mt-6 rounded-xl bg-red-50 p-4 text-red-800">{error}</p>}
      {!result && !error ? <p className="mt-6 text-stone-600">Loading digest history...</p>
        : result?.items?.length ? (
          <div className="mt-6 space-y-3">
            {result.items.map((digest) => (
              <Link key={digest.id} to={`/digests/${digest.id}`} className="block rounded-2xl border border-stone-200 bg-white p-5 hover:bg-stone-50">
                <p className="font-semibold text-stone-900">{digest.digest_date} · {digest.total_articles} stories</p>
                <p className="mt-1 text-sm text-stone-600">{digest.introduction}</p>
              </Link>
            ))}
          </div>
        ) : <p className="mt-6 rounded-2xl bg-stone-50 p-6 text-stone-600">No generated digests yet.</p>}
    </section>
  );
}
