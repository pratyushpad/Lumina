import { motion, useReducedMotion } from "framer-motion";
import { useMemo } from "react";

interface SplitTextProps {
  text: string;
  className?: string;
  /** Stagger per word, in seconds. */
  stagger?: number;
  /** Initial Y offset in px. */
  yFrom?: number;
  /** Animate when in viewport (true) or on mount (false). */
  inView?: boolean;
}

/**
 * Word-by-word reveal with spring physics. Renders one motion.span per word.
 */
export function SplitText({
  text,
  className,
  stagger = 0.05,
  yFrom = 24,
  inView = false,
}: SplitTextProps) {
  const words = useMemo(() => text.split(" "), [text]);
  const reduce = useReducedMotion();
  if (reduce) return <span className={className}>{text}</span>;

  const container = {
    hidden: {},
    show: { transition: { staggerChildren: stagger, delayChildren: 0.05 } },
  };
  const word = {
    hidden: { opacity: 0, y: yFrom },
    show: {
      opacity: 1,
      y: 0,
      transition: { type: "spring" as const, stiffness: 280, damping: 26 },
    },
  };

  const motionProps = inView
    ? { initial: "hidden", whileInView: "show", viewport: { once: true, margin: "-10%" } }
    : { initial: "hidden", animate: "show" };

  return (
    <motion.span variants={container} {...motionProps} className={className}>
      {words.map((w, i) => (
        <span key={i} className="inline-block overflow-hidden align-baseline pb-[0.08em]">
          <motion.span variants={word} className="inline-block">
            {w}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </motion.span>
  );
}
