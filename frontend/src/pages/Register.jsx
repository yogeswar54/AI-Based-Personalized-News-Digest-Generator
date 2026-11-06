import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const initialForm = {
  full_name: "",
  email: "",
  password: "",
  confirm_password: "",
};

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (form.password !== form.confirm_password) {
      setError("Passwords do not match.");
      return;
    }
    setIsSubmitting(true);

    try {
      const { data } = await register(form);
      setSuccess(data.message || "Registration successful.");
      setForm(initialForm);
      setTimeout(() => navigate("/login"), 900);
    } catch (requestError) {
      const message =
        requestError.response?.data?.detail ||
        requestError.response?.data?.message ||
        "Unable to create your account.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="mx-auto max-w-xl px-6 py-14 sm:px-10 lg:px-16">
      <div className="rounded-[2rem] border border-stone-200 bg-white p-8 shadow-sm sm:p-10">
        <div className="mb-8">
          <p className="text-sm font-medium uppercase tracking-[0.16em] text-green-800">New account</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-900">Create your profile</h1>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-stone-700" htmlFor="full_name">
              Full name
            </label>
            <input
              id="full_name"
              name="full_name"
              type="text"
              value={form.full_name}
              onChange={handleChange}
              autoComplete="name"
              className="w-full rounded-xl border border-stone-300 bg-stone-50 px-4 py-3 text-stone-900 outline-none transition focus:border-green-700 focus:bg-white"
              placeholder="Ashley Hart"
              required
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
              value={form.email}
              onChange={handleChange}
              autoComplete="email"
              className="w-full rounded-xl border border-stone-300 bg-stone-50 px-4 py-3 text-stone-900 outline-none transition focus:border-green-700 focus:bg-white"
              placeholder="you@example.com"
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-stone-700" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              autoComplete="new-password"
              minLength={8}
              maxLength={72}
              className="w-full rounded-xl border border-stone-300 bg-stone-50 px-4 py-3 text-stone-900 outline-none transition focus:border-green-700 focus:bg-white"
              placeholder="At least 8 characters"
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-stone-700" htmlFor="confirm_password">
              Confirm password
            </label>
            <input
              id="confirm_password"
              name="confirm_password"
              type="password"
              value={form.confirm_password}
              onChange={handleChange}
              autoComplete="new-password"
              minLength={8}
              maxLength={72}
              className="w-full rounded-xl border border-stone-300 bg-stone-50 px-4 py-3 text-stone-900 outline-none transition focus:border-green-700 focus:bg-white"
              placeholder="Re-enter your password"
              required
            />
          </div>

          {error ? (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          {success ? (
            <div role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
              {success}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center rounded-xl bg-green-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-green-900 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Creating account..." : "Register"}
          </button>
        </form>

        <p className="mt-6 text-sm text-stone-600">
          Already have an account?{" "}
          <Link className="font-semibold text-green-800 hover:text-green-700" to="/login">
            Sign in here
          </Link>
        </p>
      </div>
    </section>
  );
}
