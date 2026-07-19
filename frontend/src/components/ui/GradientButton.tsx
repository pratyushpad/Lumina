import { motion, HTMLMotionProps, useMotionValue, useReducedMotion, useSpring } from "framer-motion";
import { useRef } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "ghost" | "outline";

interface SharpButtonProps extends HTMLMotionProps<"button"> {
  variant?: Variant;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-textPrimary text-background hover:bg-textPrimary/90",
  outline:
    "bg-transparent text-textPrimary border border-lineStrong hover:border-textPrimary hover:bg-textPrimary/[0.05]",
  ghost: "bg-transparent text-textSecondary hover:text-textPrimary hover:bg-textPrimary/[0.05]",
};

/**
 * SharpButton — square edges, framer-style magnetic hover.
 * The original export name is kept (GradientButton) to avoid widespread import
 * renames; functionally it is now a sharp, no-gradient button.
 */
export function GradientButton({
  className,
  variant = "primary",
  children,
  ...props
}: SharpButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 200, damping: 18 });
  const sy = useSpring(y, { stiffness: 200, damping: 18 });

  const reduce = useReducedMotion();
  const onMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    const el = ref.current;
    if (!el || reduce) return;
    const r = el.getBoundingClientRect();
    const dx = e.clientX - (r.left + r.width / 2);
    const dy = e.clientY - (r.top + r.height / 2);
    x.set(dx * 0.18);
    y.set(dy * 0.18);
  };
  const onLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.button
      ref={ref}
      style={{ x: sx, y: sy }}
      whileTap={{ scale: 0.97 }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={cn(
        "relative inline-flex select-none items-center justify-center gap-2 px-5 py-2.5",
        "rounded-none text-sm font-medium tracking-tight transition-colors",
        VARIANTS[variant],
        className
      )}
      {...props}
    >
      {children}
    </motion.button>
  );
}
