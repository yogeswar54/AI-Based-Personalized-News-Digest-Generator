import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import RecommendationCard from "../components/RecommendationCard.jsx";
import { fetchRecommendations } from "../services/personalizationService.js";

export default function RecommendationsPage() {
  const [result, setResult] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchRecommendations({ page, limit: 12 })
      .then((response) => {
        if (active) setResult(response);
      })
      .catch((requestError) => {
        if (active) setError(requestError?.response?.data?.detail || "Unable to load recommendations.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page]);

  return (
    <section className="mx-auto max-w-7xl px-6 py-12 sm:px-10 lg:px-16">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.16em] text-green-800">For you</p>
          <h1 className="mt-2 text-3xl font-semibold text-stone-950">Recommended news</h1>
          <p className="mt-2 text-sm text-stone-600">Ranked from your saved interests and shared news coverage.</p>
        </div>
        <Link to="/interest-selection" className="text-sm font-semibold text-green-900 underline">Manage interests</Link>
      </div>
      {loading ? (
        <p className="mt-8 rounded-2xl bg-stone-50 p-6 text-stone-600">Loading recommendations...</p>
      ) : error ? (
        <p role="alert" className="mt-8 rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800">{error}</p>
      ) : !result?.interests?.length ? (
        <div className="mt-8 rounded-2xl bg-stone-50 p-6 text-stone-700">
          <p>{result?.message || "Select interests to get recommendations."}</p>
          <Link to="/interest-selection" className="mt-3 inline-block font-semibold text-green-900 underline">Choose interests</Link>
        </div>
      ) : result.items?.length ? (
        <>
          <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {result.items.map((item) => <RecommendationCard key={item.article.id} item={item} />)}
          </div>
          <div className="mt-7 flex justify-between">
            <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="rounded-xl border px-4 py-2 disabled:opacity-40">Previous</button>
            <button type="button" disabled={page * result.limit >= result.total} onClick={() => setPage((value) => value + 1)} className="rounded-xl border px-4 py-2 disabled:opacity-40">Next</button>
          </div>
        </>
      ) : <p className="mt-8 rounded-2xl bg-stone-50 p-6 text-stone-600">No matching recommendations are available yet.</p>}
    </section>
  );
}
