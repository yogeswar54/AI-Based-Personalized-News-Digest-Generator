import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchNewsGroup } from "../services/newsService.js";

export default function NewsGroupPage() {
  const { groupId } = useParams();
  const [group, setGroup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchNewsGroup(groupId)
      .then((result) => {
        if (active) setGroup(result);
      })
      .catch((loadError) => {
        if (active) setError(loadError?.response?.data?.detail || "Unable to load related coverage.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [groupId]);

  if (loading) return <p className="mx-auto max-w-5xl px-6 py-12 text-stone-600">Loading related coverage...</p>;

  if (error || !group) {
    return (
      <section className="mx-auto max-w-5xl px-6 py-12">
        <p className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800">{error || "Event group not found."}</p>
        <Link to="/news" className="mt-5 inline-block text-sm font-medium text-green-900 underline">Back to news</Link>
      </section>
    );
  }

  const representative = group.articles?.find((article) => article.id === group.representative_article_id);

  return (
    <section className="mx-auto max-w-5xl px-6 py-12 sm:px-10">
      <Link to="/news" className="text-sm font-medium text-green-900 underline">Back to news</Link>
      <div className="mt-6 rounded-[2rem] border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-green-800">
          {group.category} · {group.article_count} sources reporting
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">{group.event_title}</h1>
        {representative?.summarization?.status === "completed" && (
          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-green-800">AI-generated summary</p>
            <p className="mt-2 text-base leading-7 text-stone-700">{representative.summarization.short_summary}</p>
          </div>
        )}
        {group.keywords?.length > 0 && (
          <p className="mt-5 text-sm text-stone-500">Keywords: {group.keywords.join(", ")}</p>
        )}
      </div>

      <h2 className="mt-10 text-xl font-semibold text-stone-900">Coverage by publisher</h2>
      {group.articles?.length ? (
        <div className="mt-4 space-y-4">
          {group.articles.map((article) => (
            <article key={article.id} className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide text-stone-500">
                <span>{article.source?.name || "Unknown source"}</span>
                {article.published_at && (
                  <>
                    <span aria-hidden="true">•</span>
                    <time dateTime={article.published_at}>{new Date(article.published_at).toLocaleString()}</time>
                  </>
                )}
              </div>
              <h3 className="mt-2 text-lg font-semibold text-stone-900">{article.title}</h3>
              {article.description && <p className="mt-2 text-sm leading-6 text-stone-600">{article.description}</p>}
              <a
                href={article.url}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-flex rounded-xl border border-green-900 px-4 py-2 text-sm font-medium text-green-950 hover:bg-green-50"
              >
                Read original at {article.source?.name || "publisher"}
              </a>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 rounded-2xl bg-stone-50 p-5 text-sm text-stone-600">No articles are currently available in this group.</p>
      )}
    </section>
  );
}
