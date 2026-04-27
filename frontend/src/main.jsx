import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { SessionProvider } from "./context/SessionContext";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SessionProvider>
      <App />
    </SessionProvider>
  </React.StrictMode>
);
