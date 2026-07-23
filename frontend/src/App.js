import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/lib/auth";
import Landing from "@/pages/Landing";
import Pricing from "@/pages/Pricing";
import Dashboard from "@/pages/Dashboard";
import ProjectWizard from "@/pages/ProjectWizard";
import ProjectView from "@/pages/ProjectView";
import Settings from "@/pages/Settings";
import AdminPanel from "@/pages/AdminPanel";
import AuthCallback from "@/pages/AuthCallback";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import PublicVideo from "@/pages/PublicVideo";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import ShortLinkRedirect from "@/pages/ShortLinkRedirect";
import UpgradeModal from "@/components/UpgradeModal";

function AppRouter() {
  const location = useLocation();
  // Synchronous check for OAuth callback fragment (prevents race conditions)
  if (location.hash?.includes("session_id=") || window.location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/v/:slug" element={<PublicVideo />} />
      <Route path="/l/:slug" element={<ShortLinkRedirect />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/new" element={<ProtectedRoute><ProjectWizard /></ProtectedRoute>} />
      <Route path="/project/:id" element={<ProtectedRoute><ProjectView /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute adminOnly><AdminPanel /></ProtectedRoute>} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <BrowserRouter>
          <AuthProvider>
            <AppRouter />
            <UpgradeModal />
            <Toaster position="top-right" richColors />
          </AuthProvider>
        </BrowserRouter>
      </ErrorBoundary>
    </div>
  );
}
