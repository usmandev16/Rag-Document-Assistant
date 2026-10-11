import { useEffect } from "react";
import App from "./App";
import { clearSession, clearSessionOnUnload } from "./api.js";

export default function Root() {
  useEffect(() => {
    // Fires on reload, tab close, or navigating away — not just the
    // explicit "sign out" button — so a refresh doesn't leave old chats and
    // documents sitting around for the same session to see again.
    window.addEventListener("pagehide", clearSessionOnUnload);
    return () => window.removeEventListener("pagehide", clearSessionOnUnload);
  }, []);

  function handleExit() {
    // Wipe this session's chats/documents right away instead of waiting for
    // the backend's stale-chat sweep, then start over with an empty chat.
    clearSession().catch(() => {}).finally(() => window.location.reload());
  }

  return <App onExit={handleExit} />;
}
