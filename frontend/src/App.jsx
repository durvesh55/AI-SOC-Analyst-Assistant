import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import AdminUsers from "./pages/AdminUsers";
import AlertDetail from "./pages/AlertDetail";
import Alerts from "./pages/Alerts";
import AuditLogs from "./pages/AuditLogs";
import CaseDetail from "./pages/CaseDetail";
import Cases from "./pages/Cases";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Register from "./pages/Register";

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to="/dashboard" replace /> : <Register />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="alerts/:id" element={<AlertDetail />} />
        <Route path="cases" element={<Cases />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="audit" element={<AuditLogs />} />
        <Route path="profile" element={<Profile />} />
        <Route path="admin/users" element={<ProtectedRoute adminOnly><AdminUsers /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
