import { createContext, useCallback, useContext, useRef, useState } from "react";
import DialogModal from "../components/DialogModal";

const DialogContext = createContext(null);

export function DialogProvider({ children }) {
  const [dialog, setDialog] = useState(null);
  const resolverRef = useRef(null);

  const settle = useCallback((value) => {
    resolverRef.current?.(value);
    resolverRef.current = null;
    setDialog(null);
  }, []);

  const confirm = useCallback((message, options = {}) => {
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setDialog({ kind: "confirm", message, ...options });
    });
  }, []);

  const prompt = useCallback((message, defaultValue = "", options = {}) => {
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setDialog({ kind: "prompt", message, defaultValue, ...options });
    });
  }, []);

  const handleCancel = useCallback(() => {
    settle(dialog?.kind === "prompt" ? null : false);
  }, [dialog, settle]);

  const handleConfirm = useCallback(
    (value) => {
      settle(dialog?.kind === "prompt" ? value : true);
    },
    [dialog, settle]
  );

  return (
    <DialogContext.Provider value={{ confirm, prompt }}>
      {children}
      {dialog && <DialogModal dialog={dialog} onConfirm={handleConfirm} onCancel={handleCancel} />}
    </DialogContext.Provider>
  );
}

export function useDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) {
    throw new Error("useDialog must be used inside DialogProvider");
  }
  return ctx;
}
