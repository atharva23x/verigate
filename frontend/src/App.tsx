import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import ApplicationDetail from "./pages/ApplicationDetail";
import ReviewQueue from "./pages/ReviewQueue";
import AuditLog from "./pages/AuditLog";
import Analytics from "./pages/Analytics";
import IssuerStatus from "./pages/IssuerStatus";

function Protected({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Dashboard />
          </Protected>
        }
      />
      <Route
        path="/upload"
        element={
          <Protected>
            <Upload />
          </Protected>
        }
      />
      <Route
        path="/applications/:id"
        element={
          <Protected>
            <ApplicationDetail />
          </Protected>
        }
      />
      <Route
        path="/queue"
        element={
          <Protected>
            <ReviewQueue />
          </Protected>
        }
      />
      <Route
        path="/audit"
        element={
          <Protected>
            <AuditLog />
          </Protected>
        }
      />
      <Route
        path="/analytics"
        element={
          <Protected>
            <Analytics />
          </Protected>
        }
      />
      <Route
        path="/issuers"
        element={
          <Protected>
            <IssuerStatus />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
