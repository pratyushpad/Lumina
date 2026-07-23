import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { duration, ease, overlayIn } from "@/lib/motion";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Styles the confirm action with the `error` semantic token. */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Styled replacement for the native `confirm()`. Rendered via `createPortal`
 * to `document.body` for the same reason as `TraceInspector`: this dialog is
 * `position: fixed`, but callers mount it inside elements Framer Motion
 * animates with a transform, and a transformed ancestor becomes the
 * containing block for fixed descendants — which would pin the dialog to
 * that ancestor instead of the viewport.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const reduceMotion = useReducedMotion();
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    // Land keyboard focus somewhere deliberate. For destructive actions the
    // safe default is Cancel, so an accidental Enter doesn't delete anything;
    // for non-destructive confirms, focus the primary action.
    if (destructive) {
      cancelRef.current?.focus();
    } else {
      confirmRef.current?.focus();
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
        return;
      }
      if (e.key !== "Tab") return;
      // Minimal focus trap: this dialog only ever has two buttons.
      const focusables = dialogRef.current?.querySelectorAll<HTMLElement>("button");
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onCancel, destructive]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: duration.slow, ease }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-textPrimary/35 px-4"
          onClick={onCancel}
        >
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby={description ? "confirm-dialog-description" : undefined}
            // Modals are the documented exception to origin-aware popovers:
            // they are not anchored to a trigger, so they scale from center.
            initial={reduceMotion ? { opacity: 0 } : overlayIn.initial}
            animate={reduceMotion ? { opacity: 1 } : overlayIn.animate}
            exit={reduceMotion ? { opacity: 0 } : overlayIn.exit}
            transition={{ duration: duration.slow, ease }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm hairline-strong bg-surface p-5"
          >
            <h2
              id="confirm-dialog-title"
              className="font-display text-lg font-bold tracking-tight2"
            >
              {title}
            </h2>
            {description && (
              <p id="confirm-dialog-description" className="mt-2 text-sm text-textSecondary">
                {description}
              </p>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                ref={cancelRef}
                onClick={onCancel}
                className="hairline bg-card px-3 py-2 text-xs font-mono uppercase tracking-tight2 text-textSecondary transition-colors hover:text-textPrimary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                {cancelLabel}
              </button>
              <button
                ref={confirmRef}
                onClick={onConfirm}
                className={`hairline-strong px-3 py-2 text-xs font-mono uppercase tracking-tight2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                  destructive
                    ? "bg-error text-background hover:bg-error/90"
                    : "bg-textPrimary text-background hover:bg-textPrimary/90"
                }`}
              >
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
