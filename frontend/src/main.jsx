import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { SessionProvider } from "./context/SessionContext";
import { DialogProvider } from "./context/DialogContext";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <DialogProvider>
      <SessionProvider>
        <App />
      </SessionProvider>
    </DialogProvider>
  </React.StrictMode>
);
