import { HTMLMotionProps, motion } from "framer-motion";
import { cn } from "@/lib/cn";

interface PanelProps extends HTMLMotionProps<"div"> {
  hover?: boolean;
}

/**
 * Panel — sharp-edged surface, hairline border. (Filename kept for
 * import continuity; no glass/blur anymore.)
 */
export function GlassCard({ className, hover, children, ...props }: PanelProps) {
  return (
    <motion.div
      className={cn(
        "relative bg-surface hairline p-6 transition-colors",
        hover && "hover:border-textPrimary/30",
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
