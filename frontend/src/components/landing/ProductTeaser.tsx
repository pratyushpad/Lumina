import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { duration, ease } from "@/lib/motion";

/**
 * Self-playing, looping product vignette: a question appears, a grounded
 * answer streams in token-by-token, then a citation chip lands with a score
 * dot. Presentational only — mimics the real chat surface's look (hairline
 * surface bubble, serif answer body, mono citation chip) without importing
 * from `components/chat`.
 *
 * Every phase transition is opacity/transform. The token reveal itself is a
 * text-content change (not a transform), but it's a slow, occasional,
 * decorative marketing loop — not a repeated-hundreds-of-times-a-day
 * interaction — so it's exempt from the transform-only rule the same way a
 * hero video caption would be.
 *
 * Reduced motion: skip the loop entirely, render the final grounded answer +
 * citation in place, static.
 */

const QUESTION = "What's the eval methodology in the RAPTOR paper?";
const ANSWER =
  "RAPTOR builds a recursive tree of summaries, clustering chunks bottom-up with GMM soft clustering, then evaluates retrieval quality by comparing answer accuracy on QuALITY and QASPER against flat-chunk baselines.";
const CITATION = { doc: "raptor-2024.pdf", loc: "p. 4, §2.3", score: 0.87 };

type Phase = "question" | "answering" | "cited" | "hold" | "resetting";

const CHAR_MS = 14; // token-reveal cadence, not a UI motion duration — see file header

export function ProductTeaser() {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState<Phase>(reduce ? "cited" : "question");
  const [shown, setShown] = useState(reduce ? ANSWER.length : 0);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (reduce) return;

    const schedule = (fn: () => void, ms: number) => {
      const id = window.setTimeout(fn, ms);
      timers.current.push(id);
    };

    function run() {
      setPhase("question");
      setShown(0);
      schedule(() => setPhase("answering"), 1400);
    }

    run();
    return () => {
      timers.current.forEach((id) => window.clearTimeout(id));
      timers.current = [];
    };
  }, [reduce]);

  // Typewriter reveal, driven by phase.
  useEffect(() => {
    if (reduce || phase !== "answering") return;
    let i = 0;
    const id = window.setInterval(() => {
      i += 1;
      setShown(i);
      if (i >= ANSWER.length) {
        window.clearInterval(id);
        const t1 = window.setTimeout(() => setPhase("cited"), 350);
        const t2 = window.setTimeout(() => setPhase("hold"), 350 + 900);
        const t3 = window.setTimeout(() => setPhase("resetting"), 350 + 900 + 3200);
        const t4 = window.setTimeout(() => setPhase("question"), 350 + 900 + 3200 + 500);
        const t5 = window.setTimeout(
          () => {
            setShown(0);
            setPhase("answering");
          },
          350 + 900 + 3200 + 500 + 1400,
        );
        timers.current.push(t1, t2, t3, t4, t5);
      }
    }, CHAR_MS);
    timers.current.push(id as unknown as number);
    return () => window.clearInterval(id);
  }, [phase, reduce]);

  const answerText = ANSWER.slice(0, shown);
  const showCitation = phase === "cited" || phase === "hold";
  const visible = phase !== "resetting";

  return (
    <div className="mx-auto max-w-2xl border border-line bg-surface p-6 sm:p-8">
      <div className="mb-4 flex items-center gap-2 font-mono text-[10px] uppercase tracking-tight2 text-textMuted">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-textMuted" />
        Illustrative example
      </div>

      <AnimatePresence mode="wait">
        {visible && (
          <motion.div
            key="vignette"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: duration.slow, ease }}
            className="space-y-5"
          >
            {/* Question */}
            <div className="flex justify-end">
              <motion.div
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: duration.slow, ease }}
                className="max-w-[85%] border border-lineStrong bg-background px-4 py-3"
              >
                <p className="font-sans text-sm text-textPrimary">{QUESTION}</p>
              </motion.div>
            </div>

            {/* Answer */}
            {(phase === "answering" || phase === "cited" || phase === "hold") && (
              <motion.div
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: duration.slow, ease }}
                className="max-w-[92%] border border-line bg-card px-4 py-4"
              >
                <p className="font-serif text-[15px] leading-relaxed text-textPrimary">
                  {answerText}
                  {phase === "answering" && (
                    <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-[3px] animate-pulse bg-accent" />
                  )}
                </p>

                <AnimatePresence>
                  {showCitation && (
                    <motion.div
                      initial={reduce ? false : { opacity: 0, y: 6, scale: 0.97 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={reduce ? undefined : { opacity: 0 }}
                      transition={{ duration: duration.slow, ease }}
                      className="mt-4 inline-flex items-center gap-2 border border-line bg-surface px-3 py-1.5"
                    >
                      <FileText size={12} className="text-accent2" />
                      <span className="font-mono text-[11px] text-textSecondary">
                        {CITATION.doc}
                      </span>
                      <span className="font-mono text-[11px] text-textMuted">{CITATION.loc}</span>
                      <span className="inline-flex items-center gap-1 border-l border-line pl-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-ok" />
                        <span className="font-mono text-[11px] text-ok">{CITATION.score}</span>
                      </span>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
