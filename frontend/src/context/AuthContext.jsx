import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));
  const [notice, setNotice] = useState("");

  // On first load, restore the session if a token is stored.
  useEffect(() => {
    if (!tokenStore.get()) return;
    api
      .get("/auth/me")
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  // The API client fires this when any request comes back 401 (expired / revoked token).
  useEffect(() => {
    const onExpired = () => {
      setUser(null);
      setNotice("Your session has expired. Please log in again.");
    };
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  const login = useCallback(async (identifier, password) => {
    const data = await api.post("/auth/login", { identifier, password }, { auth: false });
    tokenStore.set(data.access_token);
    setNotice("");
    setUser(data.user);
  }, []);

  const logout = useCallback(async (message = "") => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* token may already be invalid - still clear locally */
    }
    tokenStore.clear();
    setUser(null);
    setNotice(message);
  }, []);

  const value = {
    user,
    setUser,
    loading,
    notice,
    clearNotice: () => setNotice(""),
    login,
    logout,
    isAdmin: user?.role === "Admin",
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
