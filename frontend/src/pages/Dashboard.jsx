import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import RecommendationCard from "../components/RecommendationCard.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { fetchRecommendations, fetchTodayDigest } from "../services/personalizationService.js";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [recommendations, setRecommendations] = useState([]);
  const [digestStatus, setDigestStatus] = useState("loading");

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const interests = user?.interests ?? [];

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      fetchRecommendations({ page: 1, limit: 3 }),
      fetchTodayDigest(),
    ]).then(([recommendationResult, digestResult]) => {
      if (!active) return;
      if (recommendationResult.status === "fulfilled") {
        setRecommendations(recommendationResult.value.items || []);
      }
      if (digestResult.status === "fulfilled") {
        setDigestStatus(digestResult.value.status);
      } else {
        setDigestStatus("unavailable");
      }
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="mx-auto max-w-6xl px-6 py-14 sm:px-10 lg:px-16">
      <div className="rounded-[2rem] border border-stone-200 bg-white p-8 shadow-sm sm:p-10">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.16em] text-green-800">Dashboard</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-900">
              Welcome, {user?.full_name || "there"}
            </h1>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              to="/profile"
            >
              Profile
            </Link>
            <Link
              className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              to="/news"
            >
              News Feed
            </Link>
            <Link
              className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              to="/digests"
            >
              Daily digest
            </Link>
            <Link
              className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              to="/digest-settings"
            >
              Digest settings
            </Link>
            <Link
              className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              to="/interest-selection"
            >
              Update interests
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-xl bg-green-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-green-900"
            >
              Logout
            </button>
          </div>
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-2xl bg-stone-50 p-5">
            <h2 className="text-xl font-semibold text-stone-900">Your news interests</h2>
            <div className="mt-5 flex flex-wrap gap-2">
              {interests.length > 0 ? (
                interests.map((interest) => (
                  <span
                    key={interest}
                    className="rounded-full border border-green-200 bg-green-50 px-3 py-2 text-sm font-medium text-green-900"
                  >
                    {interest}
                  </span>
                ))
              ) : (
                <span className="rounded-full border border-stone-200 bg-white px-3 py-2 text-sm text-stone-500">
                  No interests selected yet.
                </span>
              )}
            </div>
          </div>

          <div className="rounded-2xl bg-green-950 p-5 text-white">
            <p className="text-sm uppercase tracking-[0.16em] text-lime-200">Status</p>
            <p className="mt-4 text-2xl font-semibold">Authenticated</p>
            <p className="mt-3 text-sm text-white/80">
              {digestStatus === "completed" ? "Today's personalized digest is ready."
                : digestStatus === "not_generated" ? "Today's digest is ready to generate."
                  : digestStatus === "loading" ? "Checking today's digest..."
                    : "Digest status is currently unavailable."}
            </p>
            <Link to="/digests" className="mt-4 inline-block text-sm font-semibold text-lime-200 underline">Open daily digest</Link>
          </div>
        </div>
        <div className="mt-8">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold text-stone-900">Recommended for you</h2>
            <Link to="/recommendations" className="text-sm font-semibold text-green-900 underline">See all</Link>
          </div>
          {recommendations.length ? (
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {recommendations.map((item) => <RecommendationCard key={item.article.id} item={item} />)}
            </div>
          ) : (
            <p className="mt-4 rounded-xl bg-stone-50 p-4 text-sm text-stone-600">
              Choose interests or wait for matching news to appear.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
