import { motion, useReducedMotion, useTransform, type MotionValue } from "framer-motion";
import { useEffect, useRef } from "react";
import { gsap } from "@/lib/gsapConfig";

/**
 * Hand-crafted knowledge-graph constellation for the hero.
 *
 * Reads as a live retrieval moment: a fixed "query" node in the middle, a
 * ring of highlighted "retrieved" nodes drawn-in and orbiting slowly around
 * it (the grounded chunks), and a much fainter, slower corpus ring behind it
 * (everything else in the index). Two independent rings rotate at very
 * different, very slow speeds so the whole thing feels alive without ever
 * feeling busy.
 *
 * All motion here is transform/opacity only. GSAP owns rotation + pulse
 * (ambient, constant -> linear ease); Framer owns the two-layer scroll
 * parallax passed in from the hero. Each library only ever touches its own
 * DOM node so their transforms never fight.
 */

const CENTER = { x: 460, y: 300 };

const DOC_NODES = [
  { id: "d1", x: 340, y: 180, r: 5, tone: "accent2" as const },
  { id: "d2", x: 566, y: 168, r: 4, tone: "accent" as const },
  { id: "d3", x: 592, y: 344, r: 5, tone: "accent" as const },
  { id: "d4", x: 498, y: 462, r: 4, tone: "accent2" as const },
  { id: "d5", x: 352, y: 432, r: 4, tone: "accent" as const },
  { id: "d6", x: 292, y: 292, r: 5, tone: "accent2" as const },
];

const CORPUS_NODES = [
  { id: "c1", x: 120, y: 90 },
  { id: "c2", x: 208, y: 226 },
  { id: "c3", x: 76, y: 268 },
  { id: "c4", x: 148, y: 408 },
  { id: "c5", x: 252, y: 512 },
  { id: "c6", x: 604, y: 486 },
  { id: "c7", x: 588, y: 54 },
  { id: "c8", x: 418, y: 66 },
  { id: "c9", x: 54, y: 148 },
  { id: "c10", x: 520, y: 566 },
  { id: "c11", x: 630, y: 236 },
  { id: "c12", x: 236, y: 60 },
];

const CORPUS_EDGES: Array<[string, string]> = [
  ["c1", "c9"],
  ["c1", "c12"],
  ["c2", "c3"],
  ["c2", "c12"],
  ["c3", "c9"],
  ["c3", "c4"],
  ["c4", "c5"],
  ["c6", "c10"],
  ["c6", "c11"],
  ["c7", "c8"],
  ["c7", "c11"],
  ["c8", "c12"],
];

const toneVar: Record<"accent" | "accent2", string> = {
  accent: "rgb(var(--accent))",
  accent2: "rgb(var(--accent2))",
};

interface KnowledgeGraphProps {
  /** 0 -> 1 hero scroll progress, shared with the headline parallax. */
  scrollProgress: MotionValue<number>;
  className?: string;
}

export function KnowledgeGraph({ scrollProgress, className }: KnowledgeGraphProps) {
  const reduce = useReducedMotion();
  const docRingRef = useRef<SVGGElement>(null);
  const corpusRingRef = useRef<SVGGElement>(null);
  const centerRef = useRef<SVGCircleElement>(null);
  const docEdgesRef = useRef<SVGGElement>(null);

  const docY = useTransform(scrollProgress, [0, 1], [0, reduce ? 0 : -50]);
  const corpusY = useTransform(scrollProgress, [0, 1], [0, reduce ? 0 : -18]);

  useEffect(() => {
    if (reduce) return;

    const ctx = gsap.context(() => {
      // Draw in the retrieval edges once, staggered.
      const edgePaths = docEdgesRef.current?.querySelectorAll<SVGPathElement>("path");
      edgePaths?.forEach((path, i) => {
        const length = path.getTotalLength();
        gsap.set(path, { strokeDasharray: length, strokeDashoffset: length });
        gsap.to(path, {
          strokeDashoffset: 0,
          duration: 0.9,
          delay: 0.3 + i * 0.12,
          ease: "house",
        });
        // Ambient "signal" breathing once drawn in.
        gsap.to(path, {
          opacity: 0.85,
          duration: 2.6 + i * 0.3,
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
          delay: 1.2 + i * 0.12,
        });
      });

      // Center query node: calm pulse, suggests "live" retrieval.
      if (centerRef.current) {
        gsap.to(centerRef.current, {
          scale: 1.18,
          transformOrigin: "50% 50%",
          duration: 1.8,
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
        });
      }

      // Two independent, very slow orbits — constant motion, linear ease.
      if (docRingRef.current) {
        gsap.to(docRingRef.current, {
          rotation: 360,
          transformOrigin: `${CENTER.x}px ${CENTER.y}px`,
          duration: 140,
          repeat: -1,
          ease: "none",
        });
      }
      if (corpusRingRef.current) {
        gsap.to(corpusRingRef.current, {
          rotation: -360,
          transformOrigin: `${CENTER.x}px ${CENTER.y}px`,
          duration: 220,
          repeat: -1,
          ease: "none",
        });
      }
    });

    return () => ctx.revert();
  }, [reduce]);

  return (
    <svg
      viewBox="0 0 640 640"
      className={className}
      aria-hidden="true"
      focusable="false"
      preserveAspectRatio="xMidYMid slice"
    >
      {/* Corpus ring: everything in the index, faint and distant. */}
      <motion.g style={{ y: corpusY }}>
        <g ref={corpusRingRef}>
          {CORPUS_EDGES.map(([a, b]) => {
            const from = CORPUS_NODES.find((n) => n.id === a)!;
            const to = CORPUS_NODES.find((n) => n.id === b)!;
            return (
              <line
                key={`${a}-${b}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="rgb(var(--ink))"
                strokeOpacity={0.08}
                strokeWidth={1}
              />
            );
          })}
          {CORPUS_NODES.map((n) => (
            <circle key={n.id} cx={n.x} cy={n.y} r={2} fill="rgb(var(--ink))" opacity={0.22} />
          ))}
        </g>
      </motion.g>

      {/* Doc ring: the chunks actually retrieved for this query. */}
      <motion.g style={{ y: docY }}>
        <g ref={docRingRef}>
          <g ref={docEdgesRef}>
            {DOC_NODES.map((n) => (
              <path
                key={n.id}
                d={`M${CENTER.x},${CENTER.y} L${n.x},${n.y}`}
                fill="none"
                stroke={toneVar[n.tone]}
                strokeWidth={1.25}
                opacity={0.55}
              />
            ))}
          </g>
          {DOC_NODES.map((n) => (
            <circle key={n.id} cx={n.x} cy={n.y} r={n.r} fill={toneVar[n.tone]} />
          ))}
        </g>
      </motion.g>

      {/* Query node: fixed anchor, does not rotate with either ring. */}
      <circle ref={centerRef} cx={CENTER.x} cy={CENTER.y} r={7} fill="rgb(var(--ink))" />
      <circle
        cx={CENTER.x}
        cy={CENTER.y}
        r={13}
        fill="none"
        stroke="rgb(var(--ink))"
        strokeOpacity={0.25}
      />
    </svg>
  );
}
