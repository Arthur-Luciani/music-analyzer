import { useEffect, useRef, useState } from "react";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import "./DialogModal.css";

const FOCUSABLE_SELECTOR = 'button, input, [href], select, textarea, [tabindex]:not([tabindex="-1"])';

export default function DialogModal({ dialog, onConfirm, onCancel }) {
  const { kind, title, message, defaultValue = "", confirmLabel, cancelLabel = "Cancelar", danger = false } = dialog;
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef(null);
  const cancelButtonRef = useRef(null);
  const cardRef = useRef(null);

  useEffect(() => {
    if (kind === "prompt") {
      inputRef.current?.focus();
      inputRef.current?.select();
    } else {
      cancelButtonRef.current?.focus();
    }
  }, [kind]);

  useKeyboardShortcuts([{ key: "Escape", allowWhileTyping: true, handler: onCancel }]);

  // Prende o Tab dentro do modal — sem isso dá pra tabular pra elementos da
  // página por trás, que fica invisível atrás do overlay.
  useEffect(() => {
    const handleTabTrap = (event) => {
      if (event.key !== "Tab" || !cardRef.current) return;

      const focusable = Array.from(cardRef.current.querySelectorAll(FOCUSABLE_SELECTOR));
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleTabTrap);
    return () => document.removeEventListener("keydown", handleTabTrap);
  }, []);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (kind === "prompt") {
      const trimmed = value.trim();
      if (!trimmed) return;
      onConfirm(trimmed);
    } else {
      onConfirm(true);
    }
  };

  return (
    <div
      className="dialog-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <form className="dialog-card" onSubmit={handleSubmit} ref={cardRef}>
        {title && <h3 className="dialog-title">{title}</h3>}
        <p className="dialog-message">{message}</p>
        {kind === "prompt" && (
          <input
            ref={inputRef}
            className="dialog-input"
            type="text"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        )}
        <div className="dialog-actions">
          <button type="button" className="btn btn-subtle" onClick={onCancel} ref={cancelButtonRef}>
            {cancelLabel}
          </button>
          <button type="submit" className={`btn ${danger ? "btn-danger" : "btn-accent"}`}>
            {confirmLabel || (kind === "prompt" ? "Salvar" : "Confirmar")}
          </button>
        </div>
      </form>
    </div>
  );
}
