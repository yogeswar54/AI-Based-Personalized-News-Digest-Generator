import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchNews, fetchNewsCategories, fetchNewsGroups } from "../services/newsService.js";

const defaultCategory = "All categories";

export default function NewsFeedPage() {
  const [articles, setArticles] = useState([]);
  const [groups, setGroups] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(defaultCategory);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [totalPages, setTotalPages] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;

    async function loadNews() {
      try {
        setLoading(true);
        setError("");

        const [newsResponse, categoriesResponse, groupsResponse] = await Promise.all([
          fetchNews({
            category: selectedCategory === defaultCategory ? undefined : selectedCategory,
            keyword: search || undefined,
            page,
            limit: 6,
          }),
          fetchNewsCategories(),
          fetchNewsGroups({
            category: selectedCategory === defaultCategory ? undefined : selectedCategory,
            keyword: search || undefined,
            page: 1,
            limit: 100,
          }).catch(() => ({ items: [] })),
        ]);

        if (!active) return;

        setArticles(newsResponse.items ?? []);
        setGroups(groupsResponse.items ?? []);
        setTotalPages(newsResponse.total_pages ?? 1);
        setCategories(categoriesResponse.categories ?? []);
      } catch (loadError) {
        if (!active) return;
        setError(loadError?.response?.data?.detail || "Unable to load news right now.");
        setArticles([]);
        setGroups([]);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadNews();
    return () => {
      active = false;
    };
  }, [page, search, selectedCategory, refreshKey]);

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    setPage(1);
  };
  const visibleGroups = groups.filter((group) => group.article_count > 1 && group.representative_article);
  const groupById = new Map(visibleGroups.map((group) => [group.id, group]));
  const ungroupedArticles = articles.filter((article) => !groupById.has(article.event_group_id));

  return (
    <section className="mx-auto max-w-7xl px-6 py-12 sm:px-10 lg:px-16">
      <div className="mb-8 flex flex-col gap-6 rounded-[2rem] border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-green-800">News Feed</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-900">Latest collected stories</h1>
          </div>

          <form onSubmit={handleSearchSubmit} className="flex w-full max-w-md gap-3">
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search articles"
              className="w-full rounded-xl border border-stone-300 bg-stone-50 px-4 py-2.5 text-sm text-stone-900 outline-none ring-0 transition focus:border-green-700 focus:bg-white"
            />
            <button
              type="submit"
              className="rounded-xl bg-green-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-green-900"
            >
              Search
            </button>
          </form>
        </div>

        <div className="flex flex-wrap gap-2">
          {[defaultCategory, ...categories].map((category) => (
            <button
              key={category}
              type="button"
              onClick={() => {
                setSelectedCategory(category);
                setPage(1);
              }}
              className={[
                "rounded-full border px-3 py-2 text-sm font-medium transition",
                selectedCategory === category
                  ? "border-green-700 bg-green-700 text-white"
                  : "border-stone-300 bg-white text-stone-700 hover:border-stone-500",
              ].join(" ")}
            >
              {category}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-stone-200 bg-stone-50 p-8 text-center text-stone-600">
          Loading news articles...
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800">
          <p className="font-medium">Unable to load the news feed.</p>
          <p className="mt-2 text-sm">{error}</p>
          <button
            type="button"
            onClick={() => setRefreshKey((currentKey) => currentKey + 1)}
            className="mt-4 rounded-xl border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-700"
          >
            Retry
          </button>
        </div>
      ) : groups.length === 0 && ungroupedArticles.length === 0 ? (
        <div className="rounded-2xl border border-stone-200 bg-stone-50 p-8 text-center text-stone-600">
          No articles match the selected filters.
        </div>
      ) : (
        <div className="space-y-6">
          {visibleGroups.map((group) => {
            const representative = group.representative_article;
            return (
            <article
              key={`group-${group.id}`}
              className="overflow-hidden rounded-[2rem] border border-stone-200 bg-white shadow-sm"
            >
              <div className="grid gap-0 md:grid-cols-[220px_1fr]">
                {representative.image_url ? (
                  <img src={representative.image_url} alt="" loading="lazy" decoding="async" className="h-52 w-full object-cover md:h-full" />
                ) : (
                  <div className="flex h-52 items-center justify-center bg-stone-100 text-sm font-medium text-stone-500 md:h-full">
                    Multiple sources
                  </div>
                )}
                <div className="p-6 sm:p-7">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide text-stone-500">
                    <span>{group.category}</span>
                    <span aria-hidden="true">•</span>
                    <span>{group.article_count} sources reporting</span>
                  </div>
                  <h2 className="mt-4 text-2xl font-semibold tracking-tight text-stone-900">
                    {group.event_title || representative.title}
                  </h2>
                  {representative.summarization?.status === "completed" ? (
                    <div className="mt-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-green-800">AI-generated summary</p>
                      <p className="mt-1 text-sm leading-6 text-stone-700">{representative.summarization.short_summary}</p>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm leading-6 text-stone-600">
                      {representative.description || "Related coverage from multiple publishers."}
                    </p>
                  )}
                  <Link
                    to={`/news/groups/${encodeURIComponent(group.id)}`}
                    className="mt-6 inline-flex rounded-xl bg-green-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-900"
                  >
                    View related coverage
                  </Link>
                </div>
              </div>
            </article>
          );})}
          {ungroupedArticles.map((article) => (
            <article
              key={article.id}
              className="overflow-hidden rounded-[2rem] border border-stone-200 bg-white shadow-sm"
            >
              <div className="grid gap-0 md:grid-cols-[220px_1fr]">
                {article.image_url ? (
                  <img src={article.image_url} alt={article.title} loading="lazy" decoding="async" className="h-52 w-full object-cover md:h-full" />
                ) : (
                  <div className="flex h-52 items-center justify-center bg-stone-100 text-sm font-medium text-stone-500 md:h-full">
                    No image
                  </div>
                )}

                <div className="p-6 sm:p-7">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-stone-500">
                    <span>{article.source?.name || "Unknown source"}</span>
                    <span>•</span>
                    <span>{article.category || "World News"}</span>
                  </div>

                  <h2 className="mt-4 text-2xl font-semibold tracking-tight text-stone-900">{article.title}</h2>

                  {article.summarization?.status === "completed" && article.summarization.short_summary ? (
                    <div className="mt-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-green-800">AI-generated summary</p>
                      <p className="mt-1 text-sm leading-6 text-stone-700">{article.summarization.short_summary}</p>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm leading-6 text-stone-600">
                      {article.description || "No preview available for this article."}
                    </p>
                  )}

                  <div className="mt-5 flex flex-wrap items-center gap-4 text-sm text-stone-500">
                    <span>{article.author || "Unknown author"}</span>
                    <span>{new Date(article.published_at).toLocaleDateString()}</span>
                  </div>

                  <div className="mt-6 flex flex-wrap items-center gap-3">
                    <Link
                      to={`/news/${encodeURIComponent(article.id)}`}
                      className="inline-flex items-center rounded-xl border border-green-900 px-4 py-2 text-sm font-medium text-green-950 transition hover:bg-green-50"
                    >
                      Summary and details
                    </Link>
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center rounded-xl bg-green-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-900"
                    >
                      Read original article
                    </a>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {!loading && !error && (articles.length > 0 || groups.length > 0) && (
        <div className="mt-8 flex items-center justify-between gap-4 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <button
            type="button"
            onClick={() => setPage((currentPage) => Math.max(currentPage - 1, 1))}
            disabled={page === 1}
            className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>

          <p className="text-sm text-stone-600">
            Page {page} of {totalPages}
          </p>

          <button
            type="button"
            onClick={() => setPage((currentPage) => currentPage + 1)}
            disabled={page >= totalPages}
            className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
}
