import { Link } from "react-router-dom";

export default function RecommendationCard({ item }) {
  const article = item.article;
  return (
    <article className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
      {article.image_url && <img src={article.image_url} alt="" loading="lazy" decoding="async" className="h-44 w-full object-cover" />}
      <div className="p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-stone-500">
          {article.category} · {article.source?.name || "Unknown source"}
        </p>
        <h3 className="mt-2 text-lg font-semibold text-stone-900">{article.title}</h3>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          {article.summarization?.status === "completed" && article.summarization.short_summary
            ? article.summarization.short_summary
            : article.processed_description || article.description || "Open the original report for details."}
        </p>
        {item.reasons?.length > 0 && (
          <p className="mt-3 text-xs font-medium text-green-800">{item.reasons.join(" · ")}</p>
        )}
        <div className="mt-4 flex flex-wrap gap-3">
          <Link to={`/news/${encodeURIComponent(article.id)}`} className="text-sm font-semibold text-green-900 underline">
            Article details
          </Link>
          {item.event_group && (
            <Link to={`/news/groups/${encodeURIComponent(item.event_group.id)}`} className="text-sm font-semibold text-green-900 underline">
              {item.event_group.article_count} related sources
            </Link>
          )}
        </div>
      </div>
    </article>
  );
}
