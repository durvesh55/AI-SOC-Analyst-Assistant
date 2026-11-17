import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Spinner } from "./ui";

// Redirects anonymous visitors to /login. `adminOnly` also blocks Analysts (the backend enforces it too).
export default function ProtectedRoute({ children, adminOnly = false }) {
  const { user, loading, isAdmin } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner label="Restoring session..." />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (adminOnly && !isAdmin) {
    return (
      <div className="card"><h3>Access denied</h3><p>Administrator privileges are required to view this page.</p></div>
    );
  }
  return children;
}
