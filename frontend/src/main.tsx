import React from "react";
import ReactDOM from "react-dom/client";
import { MotionConfig } from "framer-motion";
import App from "./App";
import "./index.css";

// MotionConfig reducedMotion="user" makes every framer-motion animation honour
// the OS "reduce motion" setting — the JS-driven springs/AnimatePresence that the
// CSS @media (prefers-reduced-motion) block in index.css cannot reach.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </React.StrictMode>
);
