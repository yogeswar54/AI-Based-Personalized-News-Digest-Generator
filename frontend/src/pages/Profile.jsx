import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { userService } from "../services/userService.js";

export default function Profile() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [profile, setProfile] = useState({
    full_name: "",
    email: "",
    created_at: "",
    interests: [],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const { data } = await userService.getProfile();
        const user = data.user ?? data;
        setProfile({
          full_name: user.full_name || "",
          email: user.email || "",
          created_at: user.created_at || "",
          interests: user.interests || [],
        });
      } catch (requestError) {
        setError("Unable to load your profile right now.");
      }
    };

    fetchProfile();
  }, []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setProfile((previous) => ({ ...previous, [name]: value }));
  };

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const { data } = await userService.updateProfile({ full_name: profile.full_name });
      setUser((previous) => ({ ...previous, full_name: data.user.full_name }));
      setSuccess("Profile updated successfully.");
    } catch (requestError) {
      const message =
        requestError.response?.data?.detail ||
        requestError.response?.data?.message ||
        "Your profile could not be saved.";
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="mx-auto max-w-3xl px-6 py-14 sm:px-10 lg:px-16">
      <div className="rounded-[2rem] border border-stone-200 bg-white p-8 shadow-sm sm:p-10">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.16em] text-green-800">Profile</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-900">Your account</h1>
          </div>
          <button
            type="button"
            onClick={() => navigate("/dashboard")}
            className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
          >
            Back to dashboard
          </button>
        </div>

        <form className="mt-8 space-y-5" onSubmit={handleSave}>
          <div>
            <label className="mb-2 block text-sm font-medium text-stone-700" htmlFor="full_name">
              Full name
            </label>
            <input
              id="full_name"
              name="full_name"
              type="text"
              value={profile.full_name}
              onChange={handleChange}
              className="w-full rounded-xl border border-stone-300 bg-stone-50 px-4 py-3 text-stone-900 outline-none transition focus:border-green-700 focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-stone-700" htmlFor="email">
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={profile.email}
              readOnly
              className="w-full rounded-xl border border-stone-200 bg-stone-100 px-4 py-3 text-stone-500"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-stone-700" htmlFor="created_at">
              Account created
            </label>
            <input
              id="created_at"
              name="created_at"
              type="text"
              value={profile.created_at ? new Date(profile.created_at).toLocaleString() : ""}
              readOnly
              className="w-full rounded-xl border border-stone-200 bg-stone-100 px-4 py-3 text-stone-500"
            />
          </div>

          <div>
            <p className="mb-2 block text-sm font-medium text-stone-700">Selected interests</p>
            <div className="flex flex-wrap gap-2">
              {profile.interests.length > 0 ? (
                profile.interests.map((interest) => (
                  <span
                    key={interest}
                    className="rounded-full border border-green-200 bg-green-50 px-3 py-2 text-sm font-medium text-green-900"
                  >
                    {interest}
                  </span>
                ))
              ) : (
                <span className="rounded-full border border-stone-200 bg-stone-100 px-3 py-2 text-sm text-stone-500">
                  No interests selected yet.
                </span>
              )}
            </div>
          </div>

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          {success ? (
            <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
              {success}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={saving}
            className="rounded-xl bg-green-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-green-900 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? "Saving..." : "Update profile"}
          </button>
        </form>
      </div>
    </section>
  );
}
