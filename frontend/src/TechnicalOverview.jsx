import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  CodeXml,
  FolderInput,
  Scissors,
  Cpu,
  Database,
  HelpCircle,
  Search,
  FileCode2,
  Sparkles,
  FileOutput,
  BookOpen,
  Workflow,
  Layers3,
  Lightbulb,
  FlaskConical,
  ShieldCheck,
  ListChecks,
  Link2,
} from "lucide-react";
import "./homepage.css";

const TOC = [
  ["#overview", "Overview", BookOpen],
  ["#architecture", "Architecture", Workflow],
  ["#stack", "Tech stack and why", Layers3],
  ["#decisions", "Engineering decisions", Lightbulb],
  ["#proof", "Proof: cross-file reasoning", FlaskConical],
  ["#deployment", "Deployment and privacy", ShieldCheck],
  ["#limitations", "Limitations and next steps", ListChecks],
  ["#links", "Links", Link2],
];
const TOC_IDS = TOC.map(([href]) => href);

function Cite({ n }) {
  return <sup className="hp-cite ml-0.5 text-[0.65em] font-medium text-coral-600">{n}</sup>;
}

function NavLink({ href, icon: Icon, active, children }) {
  return (
    <a
      href={href}
      className={`flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition hover:bg-coral-50 hover:text-coral-600 ${
        active ? "bg-coral-50 font-medium text-coral-600" : "text-muted"
      }`}
    >
      <Icon size={15} strokeWidth={1.75} className="shrink-0" />
      {children}
    </a>
  );
}

function useScrollSpy(ids) {
  const [active, setActive] = useState(ids[0]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.find((e) => e.isIntersecting);
        if (visible) setActive(`#${visible.target.id}`);
      },
      { rootMargin: "-96px 0px -70% 0px", threshold: 0 }
    );
    ids.forEach((id) => {
      const el = document.getElementById(id.slice(1));
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [ids]);

  return active;
}

function Section({ id, eyebrow, icon: Icon, title, children }) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-rule py-12 first:border-t-0 first:pt-0">
      <div className="flex items-center gap-2.5">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-coral-500 text-white">
          <Icon size={15} strokeWidth={2} />
        </span>
        <p className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-coral-600">{eyebrow}</p>
      </div>
      <h2 className="mt-3 font-serif text-2xl font-semibold text-ink">{title}</h2>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function Card({ children, className = "" }) {
  return (
    <div className={`rounded-2xl border border-rule bg-surface p-6 ${className}`}>{children}</div>
  );
}

function PipelineStep({ icon: Icon, n, children, last }) {
  return (
    <div className="relative flex gap-4 pb-6 last:pb-0">
      {!last && <span className="absolute left-[15px] top-8 h-full w-px bg-rule" aria-hidden="true" />}
      <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-coral-200 bg-coral-50 text-coral-600">
        <Icon size={15} strokeWidth={2} />
      </span>
      <p className="pt-1 text-sm leading-relaxed text-ink">
        <span className="font-mono text-xs text-faint">{n}&nbsp;&nbsp;</span>
        {children}
      </p>
    </div>
  );
}

function DefItem({ term, children }) {
  return (
    <div className="border-t border-rule py-5 first:border-t-0 first:pt-0">
      <p className="font-mono text-sm font-semibold text-ink">{term}</p>
      <p className="mt-1.5 text-sm leading-relaxed text-muted">{children}</p>
    </div>
  );
}

export default function TechnicalOverview({ onBack }) {
  const active = useScrollSpy(TOC_IDS);

  return (
    <div className="homepage min-h-screen bg-paper font-sans text-ink">
      <header className="sticky top-0 z-20 border-b border-white/60 bg-surface/70 shadow-[0_1px_2px_rgba(0,0,0,0.03)] backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-4">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-1.5 rounded-full border border-rule px-3 py-1.5 text-sm font-medium text-muted transition hover:border-coral-500 hover:text-coral-600"
          >
            <ArrowLeft size={15} /> Back
          </button>
          <span className="font-serif text-base font-semibold text-ink">
            RAG Document Assistant
          </span>
          <span className="rounded-full bg-coral-50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-coral-600">
            Technical overview
          </span>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-12 px-6 py-14 lg:grid-cols-[220px_1fr]">
        {/* TOC */}
        <nav className="hidden lg:block">
          <div className="sticky top-24 rounded-2xl border border-rule bg-surface p-2">
            {TOC.map(([href, label, Icon]) => (
              <NavLink key={href} href={href} icon={Icon} active={href === active}>
                {label}
              </NavLink>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="min-w-0">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-coral-600">
            AI document intelligence
          </p>
          <h1 className="mt-3 font-serif text-3xl font-semibold leading-tight text-ink sm:text-4xl">
            Technical overview
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">
            A Retrieval-Augmented Generation (RAG) system that answers questions from a business's
            own documents, with every document answer grounded in and cited back to the source files.
          </p>

          <Section id="overview" eyebrow="Overview" icon={BookOpen} title="What it does">
            <Card>
              <p className="max-w-2xl text-[15px] leading-relaxed text-muted">
                The system lets a business query its own documents in plain language and get sourced,
                verifiable answers, instead of a general chatbot's guesses. It retrieves the relevant
                parts of the uploaded files, and the language model answers only from what was
                retrieved. It also supports live web search for comparing document data against the
                current market. Like ChatGPT, it runs multiple separate chats, and each chat keeps its
                own uploaded documents isolated from the others, so files and answers never mix
                between conversations.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {["Python", "FastAPI", "React", "Chroma", "Hugging Face embeddings", "Groq (Llama 3.3 + compound-beta)"].map((s) => (
                  <span key={s} className="rounded-full border border-rule bg-coral-50 px-3 py-1 font-mono text-xs text-coral-600">
                    {s}
                  </span>
                ))}
              </div>
            </Card>
          </Section>

          <Section id="architecture" eyebrow="Architecture" icon={Workflow} title="Two phases">
            <p className="max-w-2xl text-[15px] leading-relaxed text-muted">
              The system runs in two phases: documents are indexed once per document set, then
              queried on every question.
            </p>
            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              <Card>
                <p className="font-mono text-xs uppercase tracking-wide text-faint">Indexing — once per document set</p>
                <div className="mt-4">
                  <PipelineStep icon={FolderInput} n="1">Documents are loaded and parsed: pypdf for PDFs, python-docx for Word, and pandas for Excel and CSV.</PipelineStep>
                  <PipelineStep icon={Scissors} n="2">Text is split into overlapping, paragraph-packed chunks (about 800 characters, 150 overlap).</PipelineStep>
                  <PipelineStep icon={Cpu} n="3">Each chunk is embedded into a vector using a local Hugging Face model (all-MiniLM-L6-v2).</PipelineStep>
                  <PipelineStep icon={Database} n="4" last>Vectors and their source metadata are stored in Chroma.</PipelineStep>
                </div>
              </Card>
              <Card>
                <p className="font-mono text-xs uppercase tracking-wide text-faint">Query — per question</p>
                <div className="mt-4">
                  <PipelineStep icon={HelpCircle} n="1">The question is embedded with the same model.</PipelineStep>
                  <PipelineStep icon={Search} n="2">Chroma returns the nearest chunks by vector similarity.</PipelineStep>
                  <PipelineStep icon={FileCode2} n="3">The retrieved chunks and the question are composed into a grounded prompt.</PipelineStep>
                  <PipelineStep icon={Sparkles} n="4">Groq (llama-3.3-70b-versatile, or compound-beta for web search) generates the answer using only that context.</PipelineStep>
                  <PipelineStep icon={FileOutput} n="5" last>The answer is returned with the source document and section shown.</PipelineStep>
                </div>
              </Card>
            </div>
          </Section>

          <Section id="stack" eyebrow="Tech stack" icon={Layers3} title="Tech stack and why">
            <Card>
              <div>
                <DefItem term="Python + FastAPI (backend)">
                  Async-native, which suits waiting on LLM and embedding calls without blocking, and
                  clean for exposing a JSON API to the frontend.
                </DefItem>
                <DefItem term="React (frontend)">
                  The chat interface, document upload, and conversation history.
                </DefItem>
                <DefItem term="Hugging Face, all-MiniLM-L6-v2 (embeddings)">
                  Runs locally on the server. Chosen so the embedding step needs no external API (Groq
                  does not provide embeddings), avoids a per-chunk API cost, and keeps that stage
                  in-house.
                </DefItem>
                <DefItem term="Chroma (vector store)">
                  Purpose-built for vector similarity search, runs locally, and needs no separate
                  setup, unlike forcing vector search onto a general SQL database. Each chunk carries
                  its chat id and session owner as metadata, and retrieval filters on it, so a
                  question only ever searches the documents uploaded to that specific chat.
                </DefItem>
                <DefItem term="Groq API (generation)">
                  Two models are used depending on the question: llama-3.3-70b-versatile for grounded
                  answers from the documents, and compound-beta for answers that need live web search.
                  Groq was chosen for fast inference and a free tier, so the system stays lightweight
                  with no large model to self-host.
                </DefItem>
              </div>
            </Card>
          </Section>

          <Section id="decisions" eyebrow="Engineering decisions" icon={Lightbulb} title="Key engineering decisions">
            <Card>
              <div>
                <DefItem term="Split the models by role">
                  Embeddings run locally, generation runs on a hosted API. This keeps cost low (one
                  generation call per question, not one call per chunk) and keeps the heavy embedding
                  work off any external service.
                </DefItem>
                <DefItem term="Chunking with a custom paragraph-packing splitter">
                  Text is split into chunks of about 800 characters with 150 characters of overlap,
                  but the splitter works on whole paragraphs rather than a blind character count.
                  Complete paragraphs are packed together up to the size limit, and only a paragraph
                  that on its own exceeds the limit is split, and then only on sentence boundaries.
                  This keeps related sentences together so each chunk's embedding stays about one
                  topic, and the overlap means a fact sitting on a chunk boundary still appears whole
                  in at least one chunk instead of being cut in half.
                </DefItem>
                <DefItem term="Grounded prompting">
                  The model is instructed to answer only from the retrieved context and to say it does
                  not know when the answer is not present, which reduces hallucination and keeps
                  answers verifiable.
                </DefItem>
                <DefItem term="Cross-file retrieval">
                  Retrieval pulls the most relevant chunks regardless of which file they came from, so
                  a single answer can draw on several documents at once.
                </DefItem>
                <DefItem term="Swappable generation model (document answers)">
                  The document-grounded generation step is isolated from the rest of the pipeline.
                  Chunking, the vector store, and the loaders never touch the LLM client or the API
                  key, they just pass the question and retrieved chunks in and get an answer back.
                  Because the Groq client is OpenAI-compatible, swapping in a local model for a fully
                  private deployment means changing one file, not the pipeline. The web-search path is
                  the exception: it relies on Groq's compound-beta model and its built-in search, so a
                  fully local version would need its own search-and-tool-calling layer.
                </DefItem>
                <DefItem term="Exact-match fallback for IDs and numbers">
                  Embeddings are good at matching meaning but poor at telling long numeric identifiers
                  apart, so a tracking number, CN number, or order ID can pull back the wrong row. To
                  handle this, when a question contains a long number, any chunk that holds that exact
                  number is force-included in the retrieved set, alongside the normal similarity
                  results. Precise lookups stay reliable without giving up semantic search for
                  everything else.
                </DefItem>
                <DefItem term="Spreadsheet-aware loading">
                  Excel and CSV rows are turned into text one row per paragraph, in the form
                  "Column: value | Column: value", rather than dumped as a flat grid. This keeps each
                  row, and any ID inside it, intact through chunking, so a single row is not split
                  across two chunks and does not lose its meaning. Date columns stored as raw serial
                  numbers are detected and converted back to real dates during loading.
                </DefItem>
                <DefItem term="Capped retrieval at 20 chunks">
                  Retrieval returns the top 20 chunks per question by cosine similarity. This was
                  tuned down from a higher number after hitting the Groq account's token rate limit,
                  since every retrieved chunk is added to the prompt and counts against the per-minute
                  token budget. The cap trades a little recall for staying under the limit and keeping
                  responses reliable.
                </DefItem>
                <DefItem term="Per-session isolation without accounts">
                  There is no login system. Each browser tab gets a private session id stored in
                  sessionStorage, which resets on a new tab or browser and is sent to the backend as a
                  header. Every chat and its documents are scoped to that session, so one user's
                  uploads and conversations are never visible to another. Sessions clear after six
                  hours of inactivity, and immediately when the user leaves through the exit button.
                  This gives real per-user isolation for a demo without the weight of a full auth
                  system.
                </DefItem>
              </div>
            </Card>
          </Section>

          <Section id="proof" eyebrow="Proof" icon={FlaskConical} title="Cross-file reasoning">
            <p className="max-w-2xl text-[15px] leading-relaxed text-muted">
              Tested deliberately, with the linking information split across two files.
            </p>
            <div className="mt-6 overflow-hidden rounded-2xl border border-rule bg-ink">
              <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-2.5">
                <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
                <span className="ml-2 font-mono text-[11px] text-white/40">test_cross_file_reasoning</span>
              </div>
              <div className="space-y-3 px-5 py-5 font-mono text-[13px] leading-relaxed">
                <p className="text-white/50"># document 1 (pdf): "North is the top-performing region" — no numbers</p>
                <p className="text-white/50"># document 2 (xlsx): North 52000, South 31000 — no ranking</p>
                <p className="mt-3 text-white">
                  <span className="text-coral-400">question</span> = "What were the Q1 sales for the top-performing region?"
                </p>
                <p className="text-white">
                  <span className="text-coral-400">answer</span> = "North<Cite n={1} />, 52000 USD<Cite n={2} />"
                </p>
              </div>
              <div className="hp-footnotes space-y-1 border-t border-white/10 px-5 py-3 font-mono text-[11px] text-white/40">
                <p><span>1</span>&nbsp;&nbsp;regional-performance.pdf</p>
                <p><span>2</span>&nbsp;&nbsp;sales-data.xlsx</p>
              </div>
            </div>
            <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-muted">
              Neither file could answer alone. This confirms retrieval surfaces the relevant chunks
              across sources, and the model composes them into one grounded answer.
            </p>
          </Section>

          <Section id="deployment" eyebrow="Deployment" icon={ShieldCheck} title="Deployment and privacy">
            <Card>
              <ul className="space-y-3">
                {[
                  "The current build uses the Groq API for generation, chosen for speed and to stay lightweight.",
                  "The embedding and retrieval stages run locally on the server.",
                  "The document-grounded generation step is pluggable: swapping Groq for a local model keeps all document data on the company's own server, enabling a fully private deployment for the document Q&A. The web-search feature is the exception, since it depends on Groq's compound-beta and its built-in search (noted under limitations).",
                ].map((t) => (
                  <li key={t} className="flex gap-3 text-[15px] leading-relaxed text-muted">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-coral-500" />
                    {t}
                  </li>
                ))}
              </ul>
            </Card>
          </Section>

          <Section id="limitations" eyebrow="Limitations" icon={ListChecks} title="Limitations and next steps">
            <Card>
              <ul className="space-y-3">
                {[
                  "The real ceiling on how much context fits into one question is the Groq account's token rate tier (12,000 tokens per minute), not the model's 128k context window. I first assumed the context window was the binding constraint and was wrong; the rate tier is what actually limits large-context questions. Very large spreadsheets that need every row will not get full coverage on this tier.",
                  "There is no real login or accounts. Isolation is per browser tab, not authenticated, so it suits a demo but not shared production use.",
                  "Chat history is stored in a single JSON file. Fine for a demo, but a proper database would be needed for concurrent multi-user use.",
                  "Models are used as-is, with no fine-tuning; the focus is retrieval and grounding, not model training.",
                  "Next steps: evaluation on a labelled question set, re-ranking of retrieved chunks, a proper database and auth layer, and a local-model deployment path.",
                  "The fully-private local swap applies to the document-grounded answers. The web-search feature depends on Groq's compound-beta and its built-in search, so a fully local deployment would need a custom search-tool layer to replace it.",
                ].map((t) => (
                  <li key={t} className="flex gap-3 text-[15px] leading-relaxed text-muted">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />
                    {t}
                  </li>
                ))}
              </ul>
            </Card>
          </Section>

          <Section id="links" eyebrow="Links" icon={Link2} title="Links">
            <div className="flex flex-wrap gap-3">
              <a
                href="https://github.com/usmandev16/Rag-Document-Assistant"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-rule bg-surface px-4 py-2 text-sm text-ink transition hover:border-coral-500 hover:text-coral-600"
              >
                <CodeXml size={15} /> GitHub
              </a>
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}
