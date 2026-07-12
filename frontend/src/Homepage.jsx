import React, { useState } from "react";
import {
  ArrowRight,
  FileText,
  FileSpreadsheet,
  FileType,
  Link2,
  ShieldCheck,
  MessageSquareText,
  History,
  RotateCcw,
  Globe,
  ServerCog,
  Building2,
  Users,
  UserSearch,
  Code2,
  Layers,
  Cpu,
  Database,
  Zap,
} from "lucide-react";
import "./homepage.css";
import TechnicalOverview from "./TechnicalOverview";

function GithubMark(props) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M12 0C5.37 0 0 5.373 0 12c0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.333-1.755-1.333-1.755-1.09-.744.084-.729.084-.729 1.205.084 1.84 1.236 1.84 1.236 1.07 1.835 2.807 1.305 3.492.997.108-.775.42-1.305.762-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.435.375.81 1.11.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.627-5.373-12-12-12" />
    </svg>
  );
}

function LinkedinMark(props) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 1 1 0-4.124 2.062 2.062 0 0 1 0 4.124zM7.114 20.452H3.558V9h3.556v11.452z" />
    </svg>
  );
}

function Cite({ n }) {
  return <sup className="hp-cite ml-0.5 text-[0.65em] font-medium text-coral-600">{n}</sup>;
}

function Eyebrow({ children }) {
  return (
    <span className="inline-flex items-center rounded-full border border-coral-200 bg-coral-50 px-3 py-1 font-mono text-xs uppercase tracking-[0.14em] text-coral-600">
      {children}
    </span>
  );
}

function Badge({ children }) {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-coral-500 font-mono text-sm text-white">
      {children}
    </span>
  );
}

function IconChip({ icon: Icon, tone = "coral" }) {
  const tones = {
    coral: "bg-coral-50 text-coral-600",
    sage: "bg-sage-100 text-sage-600",
  };
  return (
    <span className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${tones[tone]}`}>
      <Icon size={20} strokeWidth={1.75} />
    </span>
  );
}

function SectionHeading({ eyebrow, title, lede }) {
  return (
    <div className="max-w-2xl">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="mt-3 font-serif text-3xl font-semibold text-ink sm:text-4xl">{title}</h2>
      {lede && <p className="mt-4 text-base leading-relaxed text-muted">{lede}</p>}
    </div>
  );
}

export default function Homepage({ onGetStarted }) {
  const openChat = onGetStarted || (() => {});
  const [showTechnical, setShowTechnical] = useState(false);

  if (showTechnical) {
    return <TechnicalOverview onBack={() => setShowTechnical(false)} />;
  }

  return (
    <div className="homepage min-h-screen bg-paper font-sans text-ink">
      {/* Nav */}
      <header className="sticky top-0 z-20 border-b border-white/60 bg-surface/70 shadow-[0_1px_2px_rgba(0,0,0,0.03),0_8px_24px_-18px_rgba(16,163,127,0.35)] backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-3 sm:flex-row sm:items-center sm:justify-between sm:py-4">
          <div className="flex items-center justify-between gap-2.5 sm:justify-start">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <span className="hp-logo-ring relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-coral-400 to-coral-600 font-serif text-sm font-semibold text-white shadow-[0_4px_12px_-2px_rgba(16,163,127,0.55)] sm:h-9 sm:w-9">
                D
              </span>
              <span className="truncate font-serif text-base font-semibold sm:text-lg">RAG Document Assistant</span>
              <span className="hidden shrink-0 rounded-full bg-coral-50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-coral-600 sm:inline-block">
                RAG
              </span>
            </div>
          </div>
          <nav className="hidden items-center gap-1 rounded-full border border-rule bg-paper/80 p-1 text-sm text-muted md:flex">
            {[
              ["#what-it-is", "What it is"],
              ["#features", "Features"],
              ["#examples", "Examples"],
              ["#privacy", "Privacy"],
            ].map(([href, label]) => (
              <a key={href} href={href} className="hp-navlink relative rounded-full px-3 py-1.5 transition hover:bg-surface hover:text-coral-600 hover:shadow-sm">
                {label}
              </a>
            ))}
          </nav>
          <div className="flex flex-nowrap items-center gap-1.5 sm:gap-3 sm:justify-end">
            <button onClick={openChat} className="hp-btn-glass inline-flex shrink-0 items-center gap-0.5 rounded-full px-2 py-1 text-[11px] font-medium text-white transition hover:-translate-y-0.5 sm:gap-1.5 sm:px-4 sm:py-2 sm:text-sm">
              <span className="relative z-10 inline-flex items-center gap-0.5 sm:gap-1.5">
                Get Started <ArrowRight size={11} className="sm:hidden" /><ArrowRight size={14} className="hidden sm:inline" />
              </span>
            </button>
            <button
              onClick={() => setShowTechnical(true)}
              title="Technical overview"
              className="inline-flex shrink-0 items-center gap-1 rounded-full bg-ink px-2 py-1 text-[11px] font-semibold text-white shadow-[0_6px_16px_-6px_rgba(26,29,31,0.5)] transition hover:-translate-y-0.5 hover:bg-black sm:gap-1.5 sm:px-4 sm:py-2 sm:text-sm"
            >
              <Code2 size={11} className="sm:hidden" />
              <Code2 size={15} className="hidden sm:inline" />
              Technical overview
            </button>
            <a
              href="https://github.com/usmandev16/Rag-Document-Assistant"
              target="_blank"
              rel="noopener noreferrer"
              title="View source on GitHub"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-rule text-black transition hover:border-coral-500 sm:h-9 sm:w-9"
            >
              <GithubMark className="h-4 w-4 sm:h-5 sm:w-5" />
            </a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-20 pt-16 sm:pt-24">
        <div className="hp-glow" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-6xl gap-14 lg:grid-cols-[1.1fr_1fr] lg:items-center">
          <div className="hp-rise">
            <Eyebrow>RAG-powered · answers with the receipts</Eyebrow>
            <h1 className="mt-4 font-serif text-4xl font-semibold leading-[1.1] text-ink sm:text-5xl">
              An AI assistant that answers from your documents, and shows its work.
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted">
              Built on RAG (Retrieval-Augmented Generation): it reads your business's own files, finds
              the relevant information, and answers from that, instead of relying on general knowledge
              like a normal chatbot. It can also pull live information from the internet to compare
              your data against the current market.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <button
                onClick={openChat}
                className="hp-btn-glass inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-medium text-white transition hover:-translate-y-0.5"
              >
                <span className="relative z-10 inline-flex items-center gap-2">
                  Get Started <ArrowRight size={16} />
                </span>
              </button>
              <a href="#what-it-is" className="text-sm font-medium text-ink underline decoration-rule underline-offset-4 hover:decoration-coral-500">
                See what it is
              </a>
            </div>
          </div>

          {/* Signature: a real answer card, cited like a footnoted brief */}
          <div
            className="hp-rise hp-tilt rounded-3xl border border-rule bg-surface p-6 shadow-[0_1px_2px_rgba(26,29,31,0.05),0_20px_44px_-18px_rgba(16,163,127,0.28)]"
            style={{ "--hp-delay": "120ms" }}
          >
            <p className="font-mono text-[11px] uppercase tracking-wide text-faint">Question</p>
            <p className="mt-2 font-serif text-lg text-ink">
              “What's our refund policy for damaged items?”
            </p>
            <div className="mt-5 rounded-2xl bg-coral-50 p-4">
              <p className="font-mono text-[11px] uppercase tracking-wide text-coral-600">Answer</p>
              <p className="mt-2 text-[15px] leading-relaxed text-ink">
                Damaged items are eligible for a refund within 14 days of delivery, no receipt
                required.<Cite n={1} />
              </p>
            </div>
            <div className="hp-footnotes mt-5 space-y-1.5 pt-4 font-mono text-xs text-muted">
              <p><span className="text-faint">1</span>&nbsp;&nbsp;refund-policy.pdf: “Damaged items are eligible for refund within 14 days...”</p>
            </div>
          </div>
        </div>
      </section>

      {/* What It Is */}
      <section id="what-it-is" className="border-t border-rule bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading
            eyebrow="What it is"
            title="An assistant that reads your documents in plain language."
            lede="It lets a business ask questions about its own documents and get accurate, sourced answers.
            It reads the company's files, finds the relevant information, and answers from that, instead
            of relying on general knowledge like a normal chatbot. It can also pull live information from
            the internet to compare the company's data against the current market."
          />
        </div>
      </section>

      {/* Built With */}
      <section className="border-t border-rule bg-paper">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading eyebrow="Under the hood" title="Built with" />
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              [Code2, "Python", "Core of the application."],
              [Layers, "RAG", "Grounds every answer in the actual documents."],
              [Cpu, "all-MiniLM-L6-v2", "Turns documents into vectors on the server, in-house."],
              [Database, "Chroma", "Stores the vectors and finds the most relevant pieces."],
              [Zap, "Groq (Llama)", "Fast answer generation."],
              [Globe, "Internet search", "For live market comparison."],
            ].map(([Icon, name, desc], i) => (
              <div
                key={name}
                className="flex items-start gap-3 rounded-2xl border border-rule bg-surface p-4 transition hover:-translate-y-0.5 hover:shadow-[0_12px_24px_-18px_rgba(16,163,127,0.4)]"
              >
                <IconChip icon={Icon} tone={i % 3 === 1 ? "sage" : "coral"} />
                <div>
                  <p className="font-mono text-sm font-medium text-ink">{name}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-muted">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="border-t border-rule bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading eyebrow="Process" title="How it works" />
          <div className="mt-10 grid gap-8 sm:grid-cols-3">
            {[
              ["01", "Upload", "Upload your documents: PDF, Word, spreadsheets."],
              ["02", "Index", "The assistant reads them, splits them into pieces, and stores them so it can search by meaning."],
              ["03", "Ask", "Ask a question. It finds the relevant pieces, answers from them, and shows the source."],
            ].map(([n, title, desc]) => (
              <div key={n}>
                <Badge>{n.replace("0", "")}</Badge>
                <h3 className="mt-4 font-serif text-xl font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Key Features */}
      <section id="features" className="border-t border-rule bg-paper">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading eyebrow="Key features" title="Everything the assistant does" />
          <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-3">
            {[
              [FileType, "Upload your own documents", "Add files through the interface and ask questions right away."],
              [FileSpreadsheet, "Works with many file types", "PDFs, Word documents, and spreadsheets."],
              [Link2, "Connects information across files", "Pulls from several documents at once and relates them, not one file at a time."],
              [MessageSquareText, "Document question answering", "Ask in plain language, get answers from your content."],
              [FileText, "Source citations", "Every answer shows the document and section it came from."],
              [Globe, "Market comparison with visible sources", "Searches the internet and shows which sources it used and when."],
              [ShieldCheck, "“I don’t know” honesty", "Refuses to answer when the information isn’t in your documents or the search, instead of inventing something."],
              [History, "Chat history", "Keeps the conversation, so you can follow up where you left off."],
              [RotateCcw, "Clean chat interface", "Visible history, loading indicators while it thinks, and one click to start fresh."],
            ].map(([Icon, title, desc], i) => (
              <div key={title} className="group bg-surface p-6 transition hover:bg-coral-50/60">
                <IconChip icon={Icon} tone={i % 3 === 1 ? "sage" : "coral"} />
                <h3 className="mt-4 text-[15px] font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Real-World Examples */}
      <section id="examples" className="border-t border-rule bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading eyebrow="Real-world examples" title="Where it earns its keep" />
          <div className="mt-10 grid gap-6 sm:grid-cols-2">
            {[
              [
                "Compliance and contract checks",
                "Before a staff member approves a large refund, discount, or commitment, they need to confirm it is allowed under the client's contract or company policy. The assistant finds the exact clause, shows the document and section it came from, and if the documents don't cover it, it says so instead of guessing. Acting on a wrong answer here can breach a contract or cost real money, so the citation and the refusal to invent an answer are what make it safe to rely on.",
              ],
              [
                "Client vs. market analysis",
                "An agency uploads a client's performance report and a market data spreadsheet and asks how the client compares. The assistant pulls the ranking from the report, the figures from the sheet, and current benchmarks from the web, then ties them together with the sources shown.",
              ],
              [
                "Instant answers from company files",
                "A support team points it at their policy and product documents. Instead of digging through files, they ask in plain language and get answers with the exact document and section cited.",
              ],
              [
                "Answers that span many files",
                "A consultant drops in PDFs, Word docs, and spreadsheets from different sources and asks a question covering all of them. The assistant connects the pieces into one answer.",
              ],
            ].map(([title, desc]) => (
              <div
                key={title}
                className="rounded-2xl border border-rule bg-surface p-6 transition hover:-translate-y-1 hover:border-coral-200 hover:shadow-[0_16px_32px_-20px_rgba(16,163,127,0.35)]"
              >
                <h3 className="font-serif text-lg font-semibold text-ink">{title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-muted">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Cross-file example */}
      <section className="border-t border-rule bg-paper">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading
            eyebrow="Worked example"
            title="Connecting information across files"
            lede="Neither file could answer this alone. The assistant took the ranking from one and the figure
            from the other and combined them into one correct answer."
          />
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <div className="rounded-2xl border border-rule bg-surface p-5">
                <p className="font-mono text-[11px] uppercase tracking-wide text-faint">Document 1 (PDF)</p>
                <p className="mt-2 text-sm leading-relaxed text-ink">
                  Said the North region was the top performer, but gave no numbers.
                </p>
              </div>
              <div className="rounded-2xl border border-rule bg-surface p-5">
                <p className="font-mono text-[11px] uppercase tracking-wide text-faint">Document 2 (Spreadsheet)</p>
                <p className="mt-2 text-sm leading-relaxed text-ink">
                  Listed the sales figures (North = 52,000, South = 31,000), but no ranking.
                </p>
              </div>
            </div>
            <div className="rounded-2xl border border-rule bg-coral-50 p-5">
              <p className="font-mono text-[11px] uppercase tracking-wide text-coral-600">Question</p>
              <p className="mt-2 font-serif text-base text-ink">
                “What were the Q1 sales for the top-performing region?”
              </p>
              <p className="mt-4 font-mono text-[11px] uppercase tracking-wide text-coral-600">Answer</p>
              <p className="mt-2 text-[15px] leading-relaxed text-ink">
                The top-performing region was North<Cite n={1} />, and its Q1 sales value was 52,000
                USD<Cite n={2} />.
              </p>
              <div className="hp-footnotes mt-4 space-y-1.5 pt-3 font-mono text-xs text-muted">
                <p><span className="text-faint">1</span>&nbsp;&nbsp;Document 1</p>
                <p><span className="text-faint">2</span>&nbsp;&nbsp;Document 2</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Deployment and Privacy */}
      <section id="privacy" className="border-t border-rule bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading eyebrow="Deployment and privacy" title="Lightweight now, private when you need it" />
          <div className="mt-10 grid gap-10 lg:grid-cols-2">
            <ul className="space-y-5">
              <li className="flex gap-3">
                <ServerCog size={20} className="mt-0.5 shrink-0 text-sage-600" strokeWidth={1.75} />
                <p className="text-sm leading-relaxed text-muted">
                  Uses a fast hosted model to stay lightweight
                </p>
              </li>
              <li className="flex gap-3">
                <ServerCog size={20} className="mt-0.5 shrink-0 text-sage-600" strokeWidth={1.75} />
                <p className="text-sm leading-relaxed text-muted">
                  The embedding step already runs locally on the server.
                </p>
              </li>
            </ul>
            <div className="rounded-2xl border border-rule bg-surface p-6">
              <p className="font-serif text-lg font-semibold text-ink">Can be made fully private.</p>
              <p className="mt-3 text-sm leading-relaxed text-muted">
                The model that answers from your documents can run locally, so your document data
                never leaves your own server.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Who It Is For */}
      <section className="border-t border-rule bg-paper">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <SectionHeading eyebrow="Who it's for" title="Built for people drowning in documents" />
          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              [Building2, "Teams and businesses that work with a lot of documents."],
              [Users, "Analysts, consultants, and agencies who need answers from files plus market context."],
              [UserSearch, "Anyone who tried a general AI on their documents and couldn't trust the answers."],
            ].map(([Icon, text], i) => (
              <div
                key={text}
                className="rounded-2xl border border-rule bg-surface p-6 transition hover:-translate-y-1 hover:border-coral-200 hover:shadow-[0_16px_32px_-20px_rgba(16,163,127,0.35)]"
              >
                <IconChip icon={Icon} tone={i === 1 ? "sage" : "coral"} />
                <p className="mt-4 text-sm leading-relaxed text-ink">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-8 text-xs text-faint">
          <span>RAG Document Assistant — made by M Usman</span>
          <a
            href="https://www.linkedin.com/in/usmandatasciences/"
            target="_blank"
            rel="noopener noreferrer"
            title="Connect on LinkedIn"
            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-rule text-black transition hover:border-coral-500"
          >
            <LinkedinMark className="h-4 w-4" />
          </a>
        </div>
      </footer>
    </div>
  );
}
