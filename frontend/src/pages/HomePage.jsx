import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function HomePage() {
  const { user } = useAuth();

  return (
    <section className="mx-auto grid min-h-[72vh] max-w-7xl items-center gap-12 px-6 py-16 sm:px-10 lg:grid-cols-[1.15fr_0.85fr] lg:px-16 lg:py-24">
      <div>
        <p className="mb-6 inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/70 px-4 py-2 text-xs font-medium uppercase tracking-[0.16em] text-stone-600">
          <span aria-hidden="true" className="size-2 rounded-full bg-lime-500" />
          AI-Based Personalized News Digest Generator
        </p>
        <h1 className="max-w-3xl text-5xl font-medium leading-[1.05] tracking-[-0.055em] sm:text-6xl lg:text-7xl">
          The news that matters,{" "}
          <span className="text-green-800">made personal.</span>
        </h1>
        <p className="mt-7 max-w-xl text-lg leading-8 text-stone-600">
          A thoughtful daily brief that brings the important stories together,
          cuts through the noise, and keeps your interests in focus.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Link
            className="rounded-full bg-green-950 px-6 py-3 text-sm font-medium text-white transition hover:bg-green-900"
            to={user ? "/dashboard" : "/login"}
          >
            {user ? "Open dashboard" : "Get started"}
          </Link>
          <Link
            className="rounded-full border border-stone-300 px-6 py-3 text-sm font-medium text-stone-700 transition hover:border-stone-500 hover:bg-white"
            to="/register"
          >
            Create account
          </Link>
        </div>
      </div>

      <aside
        aria-label="About your future daily brief"
        className="relative overflow-hidden rounded-[2rem] bg-green-950 p-8 text-white sm:p-10"
      >
        <div
          aria-hidden="true"
          className="absolute -right-14 -top-20 size-64 rounded-full border border-white/10"
        />
        <div
          aria-hidden="true"
          className="absolute -right-2 -top-8 size-40 rounded-full border border-white/10"
        />
        <p className="text-sm font-medium text-lime-200">A better daily read</p>
        <h2 className="mt-8 max-w-sm text-3xl font-medium leading-tight tracking-tight sm:text-4xl">
          Less scrolling. More understanding.
        </h2>
        <div className="mt-12 space-y-4">
          {[
            "Stories centered on your interests",
            "Clear, concise context",
            "One useful brief, every day",
          ].map((item, index) => (
            <div className="flex items-center gap-4" key={item}>
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white/10 text-xs text-lime-200">
                0{index + 1}
              </span>
              <span className="text-sm text-white/85">{item}</span>
            </div>
          ))}
        </div>
      </aside>
    </section>
  );
}
