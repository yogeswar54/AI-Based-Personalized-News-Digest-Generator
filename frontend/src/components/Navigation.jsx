import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Navigation() {
  const { user, logout } = useAuth();

  return (
    <header className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-6 py-6 sm:px-10 lg:px-16">
      <Link
        className="flex items-center gap-3 text-lg font-semibold tracking-tight text-stone-900"
        to="/"
        aria-label="Daily Brief home"
      >
        <span
          aria-hidden="true"
          className="grid size-9 place-items-center rounded-full bg-lime-200 text-sm text-green-950"
        >
          db
        </span>
        Daily Brief
      </Link>

      <nav aria-label="Main navigation" className="flex items-center gap-3">
        <Link className="text-sm font-medium text-stone-600 hover:text-stone-900" to="/">
          Home
        </Link>
        {user ? (
          <>
            <Link className="text-sm font-medium text-stone-600 hover:text-stone-900" to="/dashboard">
              Dashboard
            </Link>
            <Link className="text-sm font-medium text-stone-600 hover:text-stone-900" to="/news">
              News Feed
            </Link>
            <Link className="text-sm font-medium text-stone-600 hover:text-stone-900" to="/recommendations">
              For You
            </Link>
            <Link className="text-sm font-medium text-stone-600 hover:text-stone-900" to="/digests">
              Daily Digest
            </Link>
            <Link className="text-sm font-medium text-stone-600 hover:text-stone-900" to="/profile">
              Profile
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-500 hover:bg-white"
            >
              Logout
            </button>
          </>
        ) : (
          <>
            <Link
              className="rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-500 hover:bg-white"
              to="/login"
            >
              Login
            </Link>
            <Link
              className="rounded-full bg-green-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-900"
              to="/register"
            >
              Register
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
