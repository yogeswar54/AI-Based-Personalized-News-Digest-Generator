import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Loading from "./Loading.jsx";

export function GuestRoute({ children, redirectTo = "/dashboard" }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <Loading message="Checking your session..." />;
  }

  if (user) {
    return <Navigate to={redirectTo} replace />;
  }

  return children;
}

export function ProtectedRoute({ children, redirectTo = "/login" }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <Loading message="Loading your account..." />;
  }

  if (!user) {
    return <Navigate to={redirectTo} replace />;
  }

  return children;
}
