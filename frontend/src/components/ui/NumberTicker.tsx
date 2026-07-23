import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";
import { duration, ease } from "@/lib/motion";

interface NumberTickerProps {
  /** The real, already-measured value to reveal. Never a fabricated number. */
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}

/**
 * Counts up to a real numeric value using the house ease-out curve. This only
 * animates the *reveal* of a value the caller already has — it never
 * interpolates toward a guess, and under reduced motion it renders the final
 * value immediately.
 *
 * Reserves its own final width in `ch` units so the digit count-up cannot
 * shift surrounding layout (CLS guard).
 */
export function NumberTicker({
  value,
  decimals = 0,
  suffix = "",
  className = "",
}: NumberTickerProps) {
  const reduceMotion = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const finalText = `${value.toFixed(decimals)}${suffix}`;

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (reduceMotion) {
      node.textContent = finalText;
      return;
    }
    node.textContent = `${(0).toFixed(decimals)}${suffix}`;
    const controls = animate(0, value, {
      duration: duration.slow,
      ease,
      onUpdate: (v) => {
        node.textContent = `${v.toFixed(decimals)}${suffix}`;
      },
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, decimals, suffix, reduceMotion]);

  return (
    <span
      ref={ref}
      className={`tabular-nums ${className}`}
      style={{ display: "inline-block", minWidth: `${finalText.length}ch` }}
    >
      {finalText}
    </span>
  );
}
