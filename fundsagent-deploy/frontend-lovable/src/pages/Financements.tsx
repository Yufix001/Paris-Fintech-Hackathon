import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Navbar } from "@/components/landing/Navbar";
import { Stepper } from "@/components/flow/Stepper";
import { FundingDonut } from "@/components/flow/FundingDonut";
import { ProgramsTable } from "@/components/flow/ProgramsTable";
import { MiniSecurity } from "@/components/flow/MiniSecurity";
import { exportFundingReport } from "@/lib/exportFundingReport";
import { useAgent } from "@/state/AgentContext";

const DownloadIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const SpinnerIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
    style={{ animation: "spin 0.8s linear infinite" }}>
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

const TrophyIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
    <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
    <path d="M4 22h16" />
    <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
    <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
    <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
  </svg>
);

const EuroIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 10h12" /><path d="M4 14h9" />
    <path d="M19 6a7.7 7.7 0 0 0-5.2-2A7.9 7.9 0 0 0 6 12c0 4.4 3.5 8 7.8 8 2 0 3.8-.8 5.2-2" />
  </svg>
);

const ShieldIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

const TargetIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" />
  </svg>
);

type StatCard = {
  label: string;
  value: string;
  sub: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ReactNode;
};

const Financements = () => {
  const navigate = useNavigate();
  const { displayedPrograms } = useAgent();
  const [isExporting, setIsExporting] = useState(false);

  const nonDilutifPrograms = displayedPrograms.filter((p) => p.category !== "vc");
  const topMatch = displayedPrograms.length > 0
    ? Math.max(...displayedPrograms.map((p) => p.match))
    : 94;

  const stats: StatCard[] = [
    {
      label: "Total éligible",
      value: "5,8 M€",
      sub: "toutes sources",
      color: "#A855F7",
      bgColor: "hsl(271 91% 65% / 0.12)",
      borderColor: "hsl(271 91% 65% / 0.3)",
      icon: <EuroIcon />,
    },
    {
      label: "Non-dilutif",
      value: "2,1 M€",
      sub: "subventions + aides",
      color: "#4ADE80",
      bgColor: "hsl(142 76% 50% / 0.12)",
      borderColor: "hsl(142 76% 50% / 0.3)",
      icon: <ShieldIcon />,
    },
    {
      label: "Programmes",
      value: `${nonDilutifPrograms.length}`,
      sub: "matchés par l'IA",
      color: "#3B82F6",
      bgColor: "hsl(217 91% 60% / 0.12)",
      borderColor: "hsl(217 91% 60% / 0.3)",
      icon: <TrophyIcon />,
    },
    {
      label: "Meilleur match",
      value: `${topMatch}%`,
      sub: "score de compatibilité",
      color: "#FBBF24",
      bgColor: "hsl(43 96% 56% / 0.12)",
      borderColor: "hsl(43 96% 56% / 0.3)",
      icon: <TargetIcon />,
    },
  ];

  const handleExport = async () => {
    if (isExporting) return;
    setIsExporting(true);
    // Small delay for perceived smoothness
    await new Promise((r) => setTimeout(r, 600));
    exportFundingReport(displayedPrograms);
    await new Promise((r) => setTimeout(r, 400));
    setIsExporting(false);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <Navbar />
      <main className="mx-auto w-full max-w-[1100px] px-6 pb-24 pt-12 sm:pt-16">
        <div className="mb-8 text-center">
          <h1
            className="font-sans font-bold text-foreground"
            style={{
              fontSize: "clamp(26px, 4vw, 34px)",
              letterSpacing: "-1.2px",
              lineHeight: 1.1,
            }}
          >
            Trouvez vos financements en 3 minutes
          </h1>
        </div>

        <Stepper current={4} />

        <section
          aria-labelledby="step4-title"
          role="region"
          className="flex flex-col gap-4"
        >
          <h2 id="step4-title" className="sr-only">
            Étape 4 : Financements éligibles
          </h2>

          {/* Stats strip */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-[12px] px-5 py-4 flex flex-col gap-2"
                style={{
                  background: s.bgColor,
                  border: `1px solid ${s.borderColor}`,
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {s.label}
                  </span>
                  <span style={{ color: s.color, opacity: 0.8 }}>{s.icon}</span>
                </div>
                <div
                  className="text-[26px] font-bold leading-none tabular-nums"
                  style={{ color: s.color }}
                >
                  {s.value}
                </div>
                <div className="text-[11.5px] text-muted-foreground">{s.sub}</div>
              </div>
            ))}
          </div>

          {/* Hero insight strip */}
          <div
            className="rounded-[12px] px-6 py-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"
            style={{
              background:
                "linear-gradient(135deg, hsl(271 91% 65% / 0.08) 0%, hsl(217 91% 60% / 0.06) 100%)",
              border: "1px solid hsl(271 91% 65% / 0.2)",
            }}
          >
            <div>
              <div
                className="text-[13px] font-semibold"
                style={{ color: "hsl(271 91% 78%)" }}
              >
                Dossier de financement VC-grade généré par FundsAgent
              </div>
              <div className="text-[12px] text-muted-foreground mt-0.5">
                Analyse Cerebras Qwen 3 235B · 37 programmes EU/FR évalués · Combinabilité vérifiée
              </div>
            </div>
            <div
              className="text-[11px] font-semibold uppercase tracking-wide flex items-center gap-1.5 flex-shrink-0"
              style={{ color: "hsl(142 76% 60%)" }}
            >
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Règles de cumul encodées
            </div>
          </div>

          <FundingDonut />
          <ProgramsTable />

          <div className="mt-4 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={() => navigate("/diagnostic")}
              className="inline-flex items-center gap-2 rounded-lg px-5 py-3 text-[14px] font-semibold text-foreground transition-colors"
              style={{
                background: "transparent",
                border: "1px solid hsl(var(--border))",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "hsl(var(--surface-elevated))")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "transparent")
              }
            >
              ← Retour au diagnostic
            </button>

            <button
              type="button"
              onClick={handleExport}
              disabled={isExporting}
              className="inline-flex items-center gap-2 rounded-lg px-6 py-3 text-[14px] font-semibold text-white transition-all"
              style={{
                background: isExporting
                  ? "hsl(271 91% 55% / 0.7)"
                  : "linear-gradient(135deg, #6D28D9 0%, #A855F7 60%, #D946EF 100%)",
                boxShadow: isExporting
                  ? "none"
                  : "0 0 24px -4px hsl(271 91% 65% / 0.5), 0 1px 0 rgba(255,255,255,0.15) inset",
                border: "1px solid hsl(271 91% 65% / 0.4)",
                opacity: isExporting ? 0.85 : 1,
                cursor: isExporting ? "not-allowed" : "pointer",
              }}
            >
              {isExporting ? (
                <>
                  <SpinnerIcon />
                  Génération du rapport…
                </>
              ) : (
                <>
                  Télécharger le dossier PDF
                  <DownloadIcon />
                </>
              )}
            </button>
          </div>
        </section>

        <MiniSecurity />
      </main>
    </div>
  );
};

export default Financements;
