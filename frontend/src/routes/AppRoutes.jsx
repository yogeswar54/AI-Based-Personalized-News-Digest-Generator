import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "../layouts/AppLayout.jsx";
import { GuestRoute, ProtectedRoute } from "../components/ProtectedRoute.jsx";
import Loading from "../components/Loading.jsx";

const Dashboard = lazy(() => import("../pages/Dashboard.jsx"));
const DailyDigestPage = lazy(() => import("../pages/DailyDigestPage.jsx"));
const DigestHistoryPage = lazy(() => import("../pages/DigestHistoryPage.jsx"));
const DigestSettingsPage = lazy(() => import("../pages/DigestSettingsPage.jsx"));
const HomePage = lazy(() => import("../pages/HomePage.jsx"));
const InterestSelection = lazy(() => import("../pages/InterestSelection.jsx"));
const Login = lazy(() => import("../pages/Login.jsx"));
const NewsArticlePage = lazy(() => import("../pages/NewsArticlePage.jsx"));
const NewsFeedPage = lazy(() => import("../pages/NewsFeedPage.jsx"));
const NewsGroupPage = lazy(() => import("../pages/NewsGroupPage.jsx"));
const Profile = lazy(() => import("../pages/Profile.jsx"));
const RecommendationsPage = lazy(() => import("../pages/RecommendationsPage.jsx"));
const Register = lazy(() => import("../pages/Register.jsx"));

export default function AppRoutes() {
  return (
    <Suspense fallback={<Loading message="Loading page..." />}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route
            path="/login"
            element={
              <GuestRoute>
                <Login />
              </GuestRoute>
            }
          />
          <Route
            path="/register"
            element={
              <GuestRoute>
                <Register />
              </GuestRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/news"
            element={
              <ProtectedRoute>
                <NewsFeedPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/recommendations"
            element={
              <ProtectedRoute>
                <RecommendationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/digests"
            element={
              <ProtectedRoute>
                <DailyDigestPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/digests/history"
            element={
              <ProtectedRoute>
                <DigestHistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/digests/:digestId"
            element={
              <ProtectedRoute>
                <DailyDigestPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/digest-settings"
            element={
              <ProtectedRoute>
                <DigestSettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/news/:articleId"
            element={
              <ProtectedRoute>
                <NewsArticlePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/news/groups/:groupId"
            element={
              <ProtectedRoute>
                <NewsGroupPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/interest-selection"
            element={
              <ProtectedRoute>
                <InterestSelection />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
