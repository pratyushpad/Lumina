import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import { gsap, ScrollTrigger } from "@/lib/gsapConfig";

interface CountUpProps {
  value: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}

/**
 * Scroll-triggered number ticker. Ties a plain object tween to a ScrollTrigger
 * (once) so the count only runs the first time it enters view. CLS-safe: the
 * final formatted string is measured up front and reserved via `min-width` in
 * ch units, so the layout never shifts as digits animate in.
 */
export function CountUp({ value, prefix = "", suffix = "", className }: CountUpProps) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = useState(reduce ? value : 0);
  const finalText = `${prefix}${value}${suffix}`;

  useEffect(() => {
    if (reduce || !ref.current) return;
    const el = ref.current;
    const proxy = { val: 0 };
    const tween = gsap.to(proxy, {
      val: value,
      duration: 1.1,
      ease: "power2.out",
      onUpdate: () => setDisplay(Math.round(proxy.val)),
      scrollTrigger: {
        trigger: el,
        start: "top 85%",
        once: true,
      },
    });
    return () => {
      tween.scrollTrigger?.kill();
      tween.kill();
      ScrollTrigger.getById(tween.scrollTrigger?.vars.id as string)?.kill();
    };
  }, [reduce, value]);

  return (
    <span ref={ref} className={className} style={{ minWidth: `${finalText.length}ch` }}>
      <span className="tabular-nums">
        {prefix}
        {display}
        {suffix}
      </span>
    </span>
  );
}
