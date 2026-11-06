import { Outlet } from "react-router-dom";
import Navigation from "../components/Navigation.jsx";

export default function AppLayout() {
  return (
    <div className="min-h-screen">
      <Navigation />
      <main>
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-6 py-8 text-sm text-stone-500 sm:px-10 lg:px-16">
        A clearer view of the stories shaping your day.
      </footer>
    </div>
  );
}
