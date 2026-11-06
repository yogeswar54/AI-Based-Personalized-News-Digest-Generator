import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchArticleSummary, fetchNewsArticle } from "../services/newsService.js";

const summaryOptions = [
  { label: "Short", field: "short_summary" },
  { label: "Medium", field: "medium_summary" },
  { label: "Detailed", field: "detailed_summary" },
];

export default function NewsArticlePage() {
  const { articleId } = useParams();
  const [article, setArticle] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [selectedLength, setSelectedLength] = useState("short_summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadArticle() {
      try {
        setLoading(true);
        setError("");
        const articleResponse = await fetchNewsArticle(articleId);
        let summaryResponse;
        try {
          summaryResponse = await fetchArticleSummary(articleId);
        } catch (summaryError) {
          summaryResponse = {
            status: "unavailable",
            error: summaryError?.response?.data?.detail || "Unable to load the AI summary.",
          };
        }
        if (!active) return;
        setArticle(articleResponse);
        setSummaryData(summaryResponse);
      } catch (loadError) {
        if (!active) return;
        setError(loadError?.response?.data?.detail || "Unable to load this article.");
      } finally {
        if (active) setLoading(false);
      }
    }

    loadArticle();
    return () => {
      active = false;
    };
  }, [articleId]);

  if (loading) {
    return <p className="mx-auto max-w-4xl px-6 py-12 text-stone-600">Loading article and summary...</p>;
  }

  if (error || !article) {
    return (
      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800">
          {error || "Article not found."}
        </p>
        <Link to="/news" className="mt-5 inline-block text-sm font-medium text-green-900 underline">
          Back to news
        </Link>
      </section>
    );
  }

  const status = summaryData?.status || "missing";
  const summary = summaryData?.summary;
  const selectedSummary = summary?.[selectedLength];
  const facts = summary?.important_facts;

  return (
    <article className="mx-auto max-w-4xl px-6 py-12 sm:px-10">
      <Link to="/news" className="text-sm font-medium text-green-900 underline">
        Back to news
      </Link>
      {article.image_url && (
        <img src={article.image_url} alt="" loading="lazy" decoding="async" className="mt-6 max-h-[28rem] w-full rounded-3xl object-cover" />
      )}
      <div className="mt-8 flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide text-stone-500">
        <span>{article.source?.name || "Unknown source"}</span>
        <span aria-hidden="true">•</span>
        <span>{article.category || "World News"}</span>
        {article.published_at && (
          <>
            <span aria-hidden="true">•</span>
            <time dateTime={article.published_at}>{new Date(article.published_at).toLocaleDateString()}</time>
          </>
        )}
      </div>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950 sm:text-4xl">{article.title}</h1>

      <section className="mt-8 rounded-3xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-green-800">AI-generated summary</p>
        {status === "completed" && summary ? (
          <>
            <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Summary length">
              {summaryOptions.map((option) => (
                <button
                  key={option.field}
                  type="button"
                  aria-pressed={selectedLength === option.field}
                  onClick={() => setSelectedLength(option.field)}
                  className={[
                    "rounded-full border px-4 py-2 text-sm font-medium transition",
                    selectedLength === option.field
                      ? "border-green-800 bg-green-800 text-white"
                      : "border-stone-300 bg-white text-stone-700 hover:border-stone-500",
                  ].join(" ")}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="mt-5 whitespace-pre-line text-base leading-7 text-stone-700">{selectedSummary}</p>

            {summary.key_points?.length > 0 && (
              <div className="mt-7">
                <h2 className="font-semibold text-stone-900">Key points</h2>
                <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-stone-700">
                  {summary.key_points.map((point, index) => <li key={`${index}-${point}`}>{point}</li>)}
                </ul>
              </div>
            )}

            {facts && Object.values(facts).some((items) => items?.length) && (
              <div className="mt-7">
                <h2 className="font-semibold text-stone-900">Important facts</h2>
                <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                  {Object.entries(facts).filter(([, items]) => items?.length).map(([label, items]) => (
                    <div key={label} className="rounded-xl bg-stone-50 p-4">
                      <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</dt>
                      <dd className="mt-2 text-sm text-stone-700">{items.join(", ")}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
            {summary.source_used && (
              <p className="mt-6 text-xs text-stone-500">
                Generated from article {summary.source_used === "full_content" ? "content" : "description"}.
              </p>
            )}
          </>
        ) : (
          <p className="mt-4 text-sm leading-6 text-stone-600">
            {status === "processing" || status === "pending"
              ? "A summary is being prepared."
              : status === "failed"
                ? `Summary generation failed${summary?.error ? `: ${summary.error}` : ". Please try again later."}`
                : status === "skipped"
                  ? "A summary is unavailable because this article does not contain enough source text."
                      : status === "unavailable"
                        ? `${summaryData.error} The original article is still available below.`
                      : "A summary has not been generated for this article yet."}
          </p>
        )}
      </section>

      <div className="mt-7 rounded-3xl border border-stone-200 bg-stone-50 p-6">
        <h2 className="text-lg font-semibold text-stone-900">Original article</h2>
        {article.description && <p className="mt-3 text-sm leading-6 text-stone-700">{article.description}</p>}
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="mt-5 inline-flex rounded-xl bg-green-950 px-4 py-2.5 text-sm font-medium text-white hover:bg-green-900"
        >
          Read at {article.source?.name || "publisher"}
        </a>
      </div>
    </article>
  );
}
