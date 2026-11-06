import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDigestSettings, updateDigestSettings } from "../services/personalizationService.js";

const initialSettings = {
  digest_enabled: false,
  digest_frequency: "daily",
  digest_time: "08:00",
  timezone: "UTC",
  articles_per_digest: 10,
};

export default function DigestSettingsPage() {
  const [settings, setSettings] = useState(initialSettings);
  const [interests, setInterests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDigestSettings()
      .then((result) => {
        setSettings(result.settings);
        setInterests(result.interests || []);
      })
      .catch((requestError) => setError(requestError?.response?.data?.detail || "Unable to load digest settings."))
      .finally(() => setLoading(false));
  }, []);

  const update = (key, value) => setSettings((current) => ({ ...current, [key]: value }));
  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const result = await updateDigestSettings({ ...settings, articles_per_digest: Number(settings.articles_per_digest) });
      setSettings(result.settings);
      setMessage("Digest preferences saved.");
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || "Unable to save digest settings.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="mx-auto max-w-3xl px-6 py-12 text-stone-600">Loading digest settings...</p>;
  return (
    <section className="mx-auto max-w-3xl px-6 py-12 sm:px-10">
      <Link to="/digests" className="text-sm font-semibold text-green-900 underline">Back to digest</Link>
      <h1 className="mt-4 text-3xl font-semibold text-stone-950">Digest settings</h1>
      <p className="mt-2 text-sm text-stone-600">Recommendations and digests use your existing interests: {interests.length ? interests.join(", ") : "none selected"}.</p>
      <form onSubmit={save} className="mt-6 space-y-5 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
        <label className="flex items-center gap-3 text-sm font-medium text-stone-800">
          <input type="checkbox" checked={settings.digest_enabled} onChange={(event) => update("digest_enabled", event.target.checked)} />
          Enable scheduled daily digests
        </label>
        <label className="block text-sm font-medium text-stone-800">
          Preferred local time
          <input type="time" value={settings.digest_time} onChange={(event) => update("digest_time", event.target.value)} className="mt-2 block w-full rounded-xl border border-stone-300 px-3 py-2" required />
        </label>
        <label className="block text-sm font-medium text-stone-800">
          IANA timezone
          <input list="digest-timezones" value={settings.timezone} onChange={(event) => update("timezone", event.target.value)} placeholder="Asia/Kolkata" className="mt-2 block w-full rounded-xl border border-stone-300 px-3 py-2" required />
          <datalist id="digest-timezones">
            {["UTC", "Asia/Kolkata", "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney", "Europe/London", "Europe/Paris", "America/Los_Angeles", "America/Chicago", "America/New_York"].map((timezone) => (
              <option key={timezone} value={timezone} />
            ))}
          </datalist>
          <span className="mt-1 block font-normal text-stone-500">Example: Asia/Kolkata, America/New_York, or Europe/London.</span>
        </label>
        <label className="block text-sm font-medium text-stone-800">
          Stories per digest
          <input type="number" min="1" max="50" value={settings.articles_per_digest} onChange={(event) => update("articles_per_digest", event.target.value)} className="mt-2 block w-full rounded-xl border border-stone-300 px-3 py-2" required />
        </label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="text-sm text-green-800">{message}</p>}
        <button type="submit" disabled={saving} className="rounded-xl bg-green-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? "Saving..." : "Save preferences"}</button>
      </form>
    </section>
  );
}
