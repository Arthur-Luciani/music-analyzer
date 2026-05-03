import { createContext, useContext, useMemo } from "react";
import { useProcessing } from "../hooks/useProcessing";

const ProcessingContext = createContext(null);

export function ProcessingProvider({ children }) {
  const processing = useProcessing();

  const value = useMemo(() => processing, [processing]);

  return (
    <ProcessingContext.Provider value={value}>
      {children}
    </ProcessingContext.Provider>
  );
}

export function useProcessingContext() {
  const context = useContext(ProcessingContext);
  if (!context) {
    throw new Error("useProcessingContext must be used inside ProcessingProvider");
  }
  return context;
}
