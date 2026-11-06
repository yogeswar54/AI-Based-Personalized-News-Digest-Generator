import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchDigest, fetchTodayDigest, generateDigest } from "../services/personalizationService.js";

export default function DailyDigestPage() {
  const { digestId } = useParams();
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  async function loadDigest() {
    setLoading(true);
    setError("");
    try {
      setResponse(digestId ? await fetchDigest(digestId) : await fetchTodayDigest());
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || "Unable to load this digest.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDigest();
  }, [digestId]);

  const handleGenerate = async (regenerate = false) => {
    setGenerating(true);
    setError("");
    try {
      const generated = await generateDigest(regenerate);
      setResponse(generated);
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || "Digest generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <p className="mx-auto max-w-5xl px-6 py-12 text-stone-600">Loading digest...</p>;
  const digest = response?.digest;
  return (
    <section className="mx-auto max-w-5xl px-6 py-12 sm:px-10">
      <div className="flex flex-wrap justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-green-800">Daily Brief</p>
          <h1 className="mt-2 text-3xl font-semibold text-stone-950">{digest?.title || "Your daily digest"}</h1>
        </div>
        <div className="flex items-start gap-4 text-sm">
          <Link to="/digests/history" className="font-semibold text-green-900 underline">Digest history</Link>
          <Link to="/digest-settings" className="font-semibold text-green-900 underline">Settings</Link>
        </div>
      </div>
      {error && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>}
      {digest ? (
        <>
          <div className="mt-6 rounded-2xl bg-green-950 p-6 text-white">
            <p className="text-xs uppercase tracking-wide text-lime-200">{digest.digest_date} · {digest.timezone}</p>
            <p className="mt-3 leading-7 text-white/90">{digest.introduction}</p>
            <p className="mt-3 text-xs text-white/70">{digest.total_articles} stories</p>
          </div>
          {digest.sections?.length ? digest.sections.map((section) => (
            <section key={section.category} className="mt-8">
              <h2 className="text-xl font-semibold text-stone-900">{section.category}</h2>
              <div className="mt-3 space-y-4">
                {section.articles.map((article) => (
                  <article key={article.article_id} className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
                    <p className="text-xs text-stone-500">{article.source} · {article.published_at ? new Date(article.published_at).toLocaleString() : "Date unavailable"}</p>
                    <h3 className="mt-2 text-lg font-semibold text-stone-900">{article.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-stone-700">{article.summary}</p>
                    {article.url && <a className="mt-3 inline-block text-sm font-semibold text-green-900 underline" href={article.url} target="_blank" rel="noreferrer">Read original article</a>}
                  </article>
                ))}
              </div>
            </section>
          )) : <p className="mt-6 text-stone-600">No matching stories were available for this digest.</p>}
          {!digestId && (
            <button type="button" onClick={() => handleGenerate(true)} disabled={generating} className="mt-8 rounded-xl border border-stone-300 px-4 py-2 text-sm font-semibold text-stone-700 disabled:opacity-50">
              {generating ? "Regenerating..." : "Regenerate today's digest"}
            </button>
          )}
        </>
      ) : response?.status === "not_generated" || !response ? (
        <div className="mt-6 rounded-2xl bg-stone-50 p-6">
          <p className="text-stone-700">Today's digest has not been generated yet.</p>
          <button type="button" onClick={() => handleGenerate(false)} disabled={generating} className="mt-4 rounded-xl bg-green-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {generating ? "Generating..." : "Generate today's digest"}
          </button>
        </div>
      ) : response.status === "in_progress" ? <p className="mt-6 text-stone-600">Digest generation is in progress. Refresh shortly.</p>
        : <p className="mt-6 text-stone-600">{response.message || "Digest generation failed. Please try again."}</p>}
    </section>
  );
}
