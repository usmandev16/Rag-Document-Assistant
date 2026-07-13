import { useEffect, useState } from "react";
import Homepage from "./Homepage";
import App from "./App";
import { clearSession, clearSessionOnUnload } from "./api.js";

export default function Root() {
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    // Fires on reload, tab close, or navigating away — not just the
    // explicit "exit" button — so a refresh doesn't leave old chats and
    // documents sitting around for the same session to see again.
    window.addEventListener("pagehide", clearSessionOnUnload);
    return () => window.removeEventListener("pagehide", clearSessionOnUnload);
  }, []);

  function handleExit() {
    setShowChat(false);
    // Best-effort: wipe this session's chats/documents the moment they
    // leave, instead of waiting for the backend's stale-chat TTL sweep.
    clearSession().catch(() => {});
  }

  return showChat ? (
    <App onExit={handleExit} />
  ) : (
    <Homepage onGetStarted={() => setShowChat(true)} />
  );
}
