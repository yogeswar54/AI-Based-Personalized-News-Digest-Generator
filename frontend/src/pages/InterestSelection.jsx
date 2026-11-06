import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { interestService } from "../services/interestService.js";

export default function InterestSelection() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [categories, setCategories] = useState([]);
  const [selected, setSelected] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPreferences = async () => {
      try {
        const [categoriesResponse, interestsResponse] = await Promise.all([
          interestService.getCategories(),
          interestService.getUserInterests(),
        ]);
        setCategories(categoriesResponse.data.categories || []);
        setSelected(interestsResponse.data.interests || []);
      } catch (requestError) {
        setError("Unable to load your preferences right now.");
      } finally {
        setLoading(false);
      }
    };

    fetchPreferences();
  }, []);

  const toggleSelection = (category) => {
    setSelected((previous) =>
      previous.includes(category)
        ? previous.filter((item) => item !== category)
        : [...previous, category],
    );
  };

  const handleSave = async () => {
    if (selected.length === 0) {
      setError("Select at least one category to continue.");
      return;
    }

    try {
      const { data } = await interestService.updateUserInterests({ interests: selected });
      setUser((previous) => ({ ...previous, interests: data.interests || selected }));
      navigate("/dashboard");
    } catch (requestError) {
      const message =
        requestError.response?.data?.detail ||
        requestError.response?.data?.message ||
        "Your preferences could not be saved.";
      setError(message);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center px-6 text-stone-600">
        Loading your interests...
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-6 py-14 sm:px-10 lg:px-16">
      <div className="mb-8 max-w-2xl">
        <p className="text-sm font-medium uppercase tracking-[0.16em] text-green-800">Onboarding</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-900">
          Choose the topics you care about
        </h1>
        <p className="mt-3 text-stone-600">
          Select your preferred news categories to personalize your digest.
        </p>
      </div>

      {error ? (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((category) => {
          const active = selected.includes(category);
          return (
            <button
              key={category}
              onClick={() => toggleSelection(category)}
              type="button"
              className={[
                "rounded-2xl border px-4 py-4 text-left transition",
                active
                  ? "border-green-700 bg-green-950 text-white shadow-md"
                  : "border-stone-200 bg-white text-stone-800 hover:border-stone-300 hover:bg-stone-50",
              ].join(" ")}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="font-medium">{category}</span>
                <span
                  className={[
                    "inline-flex size-7 items-center justify-center rounded-full text-xs font-semibold",
                    active ? "bg-white text-green-900" : "bg-stone-100 text-stone-700",
                  ].join(" ")}
                >
                  {active ? "✓" : "+"}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-stone-600">
          Selected: <span className="font-semibold text-stone-900">{selected.length}</span>
        </p>
        <button
          type="button"
          onClick={handleSave}
          className="rounded-xl bg-green-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-green-900"
        >
          Save preferences
        </button>
      </div>
    </section>
  );
}
