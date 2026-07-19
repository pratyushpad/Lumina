import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, ArrowUpRight, Command, FileSearch, Quote, Zap } from "lucide-react";
import { useRef } from "react";
import { Link } from "react-router-dom";
import { GradientButton } from "@/components/ui/GradientButton";
import { MagneticLink } from "@/components/ui/MagneticLink";
import { ScrollProgress } from "@/components/ui/ScrollProgress";
import { SplitText } from "@/components/ui/SplitText";

const features = [
  {
    n: "01",
    icon: FileSearch,
    title: "Multimodal indexing",
    desc: "PDFs, images, tables, charts. Indexed with semantic embeddings and described with vision when needed.",
  },
  {
    n: "02",
    icon: Quote,
    title: "Cited by default",
    desc: "Every claim is grounded in a chunk from your documents. One click opens the source passage.",
  },
  {
    n: "03",
    icon: Zap,
    title: "Cross-encoder reranking",
    desc: "Bi-encoder recall, cross-encoder precision. The model sees the five most relevant chunks, not fifty.",
  },
];

const steps = [
  { n: "01", t: "Upload", d: "Drop a PDF, image, or text file." },
  { n: "02", t: "Index", d: "Parse, chunk, embed, store." },
  { n: "03", t: "Retrieve", d: "Top-15 candidates, top-5 reranked." },
  { n: "04", t: "Answer", d: "Streamed, grounded, cited." },
];

function Marquee() {
  const items = [
    "MULTIMODAL",
    "RAG",
    "GROUNDED",
    "CITED",
    "OPEN SOURCE",
    "MULTIMODAL",
    "RAG",
    "GROUNDED",
    "CITED",
    "OPEN SOURCE",
  ];
  return (
    <div className="overflow-hidden border-y border-line py-4">
      <div className="marquee-track flex gap-12 whitespace-nowrap text-2xl font-display font-bold tracking-tight3 text-textMuted">
        {[...items, ...items].map((t, i) => (
          <span key={i} className="inline-flex items-center">
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const reduce = useReducedMotion();
  const heroY = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : -80]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, reduce ? 1 : 0]);

  return (
    <div className="min-h-screen overflow-x-hidden bg-background text-textPrimary">
      <ScrollProgress />

      {/* Top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-background/80 backdrop-blur px-6 py-4">
        <Link to="/" className="font-display text-base font-bold tracking-tight3">
          LUMINA<span className="text-accent">.</span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-[11px] uppercase tracking-tight2 font-mono text-textSecondary">
          <MagneticLink href="#features" className="hover:text-textPrimary transition-colors">
            Features
          </MagneticLink>
          <MagneticLink href="#how" className="hover:text-textPrimary transition-colors">
            How it works
          </MagneticLink>
          <MagneticLink
            href="https://github.com/pratyushpad/Lumina"
            external
            className="hover:text-textPrimary transition-colors"
          >
            <span className="inline-flex items-center gap-1">
              Github <ArrowUpRight size={11} />
            </span>
          </MagneticLink>
        </nav>
        <Link to="/app">
          <GradientButton variant="primary">
            Open app <ArrowRight size={14} />
          </GradientButton>
        </Link>
      </header>

      {/* Hero */}
      <section
        ref={heroRef}
        className="relative flex min-h-[88vh] items-center justify-center px-6 noise"
      >
          <motion.div
            style={{ y: heroY, opacity: heroOpacity }}
            className="relative z-10 mx-auto w-full max-w-6xl"
          >

            <h1 className="font-display text-[clamp(3rem,9vw,9rem)] font-bold leading-[0.92] tracking-tight3">
              <SplitText text="Talk to your" />
              <br />
              <span className="text-accent"><SplitText text="documents." stagger={0.07} /></span>
            </h1>

            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.6 }}
              className="mt-6 max-w-xl text-base text-textSecondary leading-relaxed"
            >
              A grounded, multimodal RAG workbench. Upload PDFs, images, and text.
              Get cited answers backed by your own context.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.65, duration: 0.6 }}
              className="mt-10 flex flex-wrap items-center gap-3"
            >
              <Link to="/app?session=demo">
                <GradientButton variant="primary">
                  Try the live demo <ArrowRight size={14} />
                </GradientButton>
              </Link>
              <Link to="/app">
                <GradientButton variant="outline">Open Lumina</GradientButton>
              </Link>
            </motion.div>
          </motion.div>
      </section>

      <Marquee />

      {/* Features */}
      <section id="features" className="border-b border-line px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-16"
          >
            <div>
              <h2 className="mt-3 font-display text-5xl md:text-6xl font-bold tracking-tight3 max-w-2xl">
                <SplitText text="Built for grounded answers." inView />
              </h2>
              <p className="mt-4 max-w-xl text-sm text-textSecondary">
                Three things matter in a RAG system: how it indexes, how it retrieves, and how
                it cites. Lumina does each well.
              </p>
            </div>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-12 border border-line">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08, duration: 0.5 }}
                whileHover={{ backgroundColor: "rgba(255,255,255,0.02)" }}
                className={`p-8 ${i === 0 ? "md:col-span-6 md:py-14" : "md:col-span-3"} ${i < features.length - 1 ? "md:border-r border-line" : ""}`}
              >
                <f.icon size={18} className="text-accent" />
                <h3 className="mt-8 font-display text-xl font-bold tracking-tight2">
                  {f.title}
                </h3>
                <p className="mt-3 text-sm text-textSecondary leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="border-b border-line px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-16"
          >
            <h2 className="mt-3 font-display text-5xl md:text-6xl font-bold tracking-tight3">
              <SplitText text="Four stages." inView />
              <br />
              <SplitText text="Zero magic." inView stagger={0.07} />
            </h2>
          </motion.div>

          <div className="border-t border-line">
            {steps.map((s, i) => (
              <motion.div
                key={s.n}
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                whileHover={{ x: 4 }}
                className="grid grid-cols-12 items-center border-b border-line py-8 group transition-colors hover:bg-textPrimary/[0.03]"
              >
                <span className="col-span-5 md:col-span-4 font-display text-2xl md:text-3xl font-bold tracking-tight2 text-textPrimary">
                  {s.t}
                </span>
                <span className="col-span-6 md:col-span-7 text-sm text-textSecondary">
                  {s.d}
                </span>
                <ArrowUpRight
                  size={20}
                  className="col-span-12 md:col-span-1 ml-auto text-textMuted group-hover:text-accent transition-colors"
                />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-b border-line px-6 py-32">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl text-center"
        >
          <h2 className="mt-4 font-display text-6xl md:text-7xl font-bold tracking-tight3">
            <SplitText text="Drop a file." inView />
            <br />
            <SplitText text="Ask anything." inView stagger={0.07} />
          </h2>
          <p className="mx-auto mt-6 max-w-lg text-textSecondary">
            No signup. Open source, self-hostable. The demo session comes pre-loaded with two
            classic papers, so a cited answer is one click away.
          </p>
          <div className="mt-10 inline-flex flex-wrap justify-center gap-3">
            <Link to="/app?session=demo">
              <GradientButton variant="primary">
                Try the live demo <ArrowRight size={14} />
              </GradientButton>
            </Link>
            <Link to="/app">
              <GradientButton variant="outline">Upload your own</GradientButton>
            </Link>
          </div>
        </motion.div>
      </section>

      <footer className="px-6 py-8 flex flex-wrap items-center justify-between gap-3 text-[10px] uppercase tracking-tight2 font-mono text-textMuted">
        <span>Lumina, an open-source multimodal RAG workbench</span>
        <span>Self-hostable. No signup.</span>
      </footer>
    </div>
  );
}
