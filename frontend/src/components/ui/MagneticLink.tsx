import { motion, useMotionValue, useReducedMotion, useSpring } from "framer-motion";
import { useRef, type ReactNode } from "react";

interface MagneticLinkProps {
  href?: string;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  strength?: number;
  external?: boolean;
}

export function MagneticLink({
  href,
  onClick,
  children,
  className,
  strength = 0.2,
  external,
}: MagneticLinkProps) {
  const ref = useRef<HTMLAnchorElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 250, damping: 18 });
  const sy = useSpring(y, { stiffness: 250, damping: 18 });

  const reduce = useReducedMotion();
  const onMove = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const el = ref.current;
    if (!el || reduce) return;
    const r = el.getBoundingClientRect();
    x.set((e.clientX - (r.left + r.width / 2)) * strength);
    y.set((e.clientY - (r.top + r.height / 2)) * strength);
  };
  const onLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.a
      ref={ref}
      href={href}
      onClick={onClick}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ x: sx, y: sy }}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
      className={`relative inline-block group ${className ?? ""}`}
    >
      <span className="relative">
        {children}
        <span className="absolute -bottom-1 left-0 h-px w-full origin-left scale-x-0 bg-accent transition-transform duration-300 ease-out group-hover:scale-x-100" />
      </span>
    </motion.a>
  );
}
