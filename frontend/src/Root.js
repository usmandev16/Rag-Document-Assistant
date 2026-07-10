import { useState } from "react";
import Homepage from "./Homepage";
import App from "./App";
import { clearSession } from "./api.js";

export default function Root() {
  const [showChat, setShowChat] = useState(false);

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
