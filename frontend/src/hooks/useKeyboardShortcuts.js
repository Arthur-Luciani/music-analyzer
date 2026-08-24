import { useEffect } from "react";

function isTypingTarget(target) {
  return !!(
    target &&
    (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)
  );
}

function matchesShortcut(event, shortcut) {
  if (shortcut.code && event.code !== shortcut.code) return false;
  if (shortcut.key && event.key.toLowerCase() !== shortcut.key.toLowerCase()) return false;

  const wantsCtrl = shortcut.ctrl ?? false;
  const hasCtrl = event.ctrlKey || event.metaKey; // trata Cmd no Mac como o "ctrl" do Windows/Linux
  if (wantsCtrl !== hasCtrl) return false;

  return true;
}

/**
 * Registra atalhos de teclado globais (`keydown` na window) enquanto o
 * componente estiver montado. Por padrão ignora o evento se o foco estiver
 * num campo de texto (input/textarea/contenteditable) — passe
 * `allowWhileTyping: true` num atalho pra ele funcionar mesmo digitando
 * (ex: Escape fechando um modal).
 *
 * shortcuts: Array<{
 *   code?: string,        // ex: "Space", "ArrowRight" (KeyboardEvent.code)
 *   key?: string,         // ex: "s", "Escape" (KeyboardEvent.key, case-insensitive)
 *   ctrl?: boolean,       // exige Ctrl (ou Cmd no Mac) pressionado
 *   allowWhileTyping?: boolean,
 *   preventDefault?: boolean, // default true
 *   handler: (event) => void,
 * }>
 */
export function useKeyboardShortcuts(shortcuts, { enabled = true } = {}) {
  useEffect(() => {
    if (!enabled || !shortcuts || shortcuts.length === 0) return undefined;

    const handleKeyDown = (event) => {
      for (const shortcut of shortcuts) {
        if (!matchesShortcut(event, shortcut)) continue;
        if (!shortcut.allowWhileTyping && isTypingTarget(event.target)) continue;

        if (shortcut.preventDefault !== false) {
          event.preventDefault();
        }
        shortcut.handler(event);
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [shortcuts, enabled]);
}
