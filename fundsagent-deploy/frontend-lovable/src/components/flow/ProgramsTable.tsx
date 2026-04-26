import { useState } from "react";
import { useAgent } from "@/state/AgentContext";

type Category = "subvention" | "aide_fr" | "vc" | "pret";

type Program = {
  name: string;
  org: string;
  amount: string;
  amountSub?: string;
  match: number;
  delay: string;
  category: Category;
  kind?: "Dilutif" | "Non-dilutif";
};

export const PROGRAMS: Program[] = [
  {
    name: "EIC Accelerator",
    org: "European Innovation Council · Subvention + equity · Deep tech",
    amount: "2,5 M€",
    amountSub: "+ equity 15 M€",
    match: 94,
    delay: "~6 mois",
    category: "subvention",
  },
  {
    name: "Horizon Europe — Cluster 4",
    org: "Digital, Industry & Space · Consortium · 36 mois",
    amount: "800 K€",
    amountSub: "part PaymentFlow",
    match: 88,
    delay: "~9 mois",
    category: "subvention",
  },
  {
    name: "Crédit Impôt Recherche",
    org: "Bpifrance · 30% des dépenses R&D · Récurrent annuel",
    amount: "340 K€",
    amountSub: "/an",
    match: 100,
    delay: "~3 mois",
    category: "aide_fr",
  },
  {
    name: "Jeune Entreprise Innovante",
    org: "Exonération charges sociales · Critères R&D 15%+",
    amount: "180 K€",
    amountSub: "/an",
    match: 100,
    delay: "~2 mois",
    category: "aide_fr",
  },
  {
    name: "i-Lab Concours d'innovation",
    org: "Bpifrance · Subvention deeptech · 1 lauréat / an",
    amount: "600 K€",
    match: 84,
    delay: "~5 mois",
    category: "subvention",
  },
  {
    name: "France 2030 — Deeptech",
    org: "Bpifrance · Subvention + avance remboursable",
    amount: "1,2 M€",
    match: 89,
    delay: "~7 mois",
    category: "aide_fr",
  },
  {
    name: "Prêt Innovation Bpifrance",
    org: "Prêt sans garantie · Taux préférentiel · 7 ans",
    amount: "800 K€",
    match: 86,
    delay: "~2 mois",
    category: "pret",
  },
  {
    name: "Prêt French Tech Émergence",
    org: "Bpifrance · Avance récupérable · Pre-seed",
    amount: "200 K€",
    match: 82,
    delay: "~1 mois",
    category: "pret",
  },
  {
    name: "Women TechEU",
    org: "EISMEA · Subvention femmes fondatrices",
    amount: "75 K€",
    match: 76,
    delay: "~4 mois",
    category: "subvention",
  },
  {
    name: "Elaia Partners",
    org: "VC français · Seed deeptech · Ticket 1-3 M€",
    amount: "1,5 M€",
    match: 81,
    delay: "Variable",
    category: "vc",
  },
  {
    name: "Partech Africa & Europe",
    org: "VC corporate · Seed / Series A · B2B SaaS",
    amount: "1,0 M€",
    match: 71,
    delay: "Variable",
    category: "vc",
  },
  {
    name: "BNP Paribas Cardif Lab",
    org: "Corporate VC · Fintech / insurtech · Seed",
    amount: "500 K€",
    match: 74,
    delay: "Variable",
    category: "vc",
  },
];

const FILTERS: { id: Category | "all"; label: string }[] = [
  { id: "all", label: "Tous" },
  { id: "subvention", label: "Subventions" },
  { id: "aide_fr", label: "Aides FR" },
  { id: "vc", label: "VC" },
  { id: "pret", label: "Prêts" },
];

const matchColor = (m: number, category?: Category) => {
  // VCs are dilutive equity — give them a distinct violet hue so they
  // stand out from public non-dilutive funding.
  if (category === "vc") return "hsl(271 91% 70%)";
  if (m >= 90) return "hsl(var(--success))";
  if (m >= 80) return "hsl(152 70% 60%)";
  return "hsl(var(--warning))";
};

export const ProgramsTable = () => {
  const [filter, setFilter] = useState<Category | "all">("all");
  const { displayedPrograms } = useAgent();

  const programs = displayedPrograms as Program[];
  const visible = programs.filter(
    (p) => filter === "all" || p.category === filter,
  );

  return (
    <div className="mt-8 flex flex-col gap-5">
      {/* Header + filters — outside the table card */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-1">
        <div className="flex items-center gap-3">
          <h3 className="text-[18px] font-semibold text-foreground">
            Programmes recommandés
          </h3>
          <span
            className="inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold tabular-nums text-muted-foreground"
            style={{
              background: "hsl(var(--surface-elevated-2))",
              border: "1px solid hsl(var(--border))",
            }}
          >
            {PROGRAMS.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12.5px] text-muted-foreground">Filtrer :</span>
          <div role="tablist" aria-label="Filtres" className="flex flex-wrap gap-1">
            {FILTERS.map((f) => {
              const active = filter === f.id;
              return (
                <button
                  key={f.id}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setFilter(f.id)}
                  className="rounded-md px-3 py-1.5 text-[13px] font-semibold transition-colors"
                  style={
                    active
                      ? {
                          background: "hsl(var(--accent-soft))",
                          color: "hsl(var(--accent))",
                          border: "1px solid hsl(var(--accent-border))",
                        }
                      : {
                          background: "transparent",
                          color: "hsl(var(--muted-foreground))",
                          border: "1px solid transparent",
                        }
                  }
                >
                  {f.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Table card */}
      <div
        className="rounded-[14px]"
        style={{
          background: "hsl(var(--surface))",
          border: "1px solid hsl(var(--border))",
        }}
      >

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr
              className="text-[10.5px] uppercase text-muted-foreground"
              style={{
                borderTop: "1px solid hsl(var(--border-soft))",
                borderBottom: "1px solid hsl(var(--border-soft))",
                letterSpacing: "0.8px",
              }}
            >
              <th className="px-7 py-3 font-semibold">Programme</th>
              <th className="px-4 py-3 text-left font-semibold">Type</th>
              <th className="px-4 py-3 text-right font-semibold">Montant</th>
              <th className="px-4 py-3 text-left font-semibold" style={{ minWidth: 180 }}>
                Match
              </th>
              <th className="px-4 py-3 text-left font-semibold">Délai</th>
              <th className="px-7 py-3 text-right font-semibold sr-only">Action</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((p, i) => {
              const c = matchColor(p.match, p.category);
              return (
                <tr
                  key={p.name}
                  className="transition-colors hover:bg-[hsl(var(--surface-elevated))]"
                  style={
                    i < visible.length - 1
                      ? { borderBottom: "1px solid hsl(var(--border-soft))" }
                      : undefined
                  }
                >
                  <td className="px-7 py-5">
                    <div className="text-[14.5px] font-semibold text-foreground">
                      {p.name}
                    </div>
                    <div className="mt-1 text-[12.5px] text-muted-foreground">
                      {p.org}
                    </div>
                  </td>
                  <td className="px-4 py-5">
                    {(() => {
                      const kind =
                        p.kind ?? (p.category === "vc" ? "Dilutif" : "Non-dilutif");
                      const isDilutif = kind === "Dilutif";
                      return (
                        <span
                          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
                          style={{
                            background: isDilutif
                              ? "hsl(271 91% 65% / 0.14)"
                              : "hsl(152 70% 60% / 0.14)",
                            color: isDilutif
                              ? "hsl(271 91% 75%)"
                              : "hsl(152 70% 65%)",
                            border: `1px solid ${
                              isDilutif
                                ? "hsl(271 91% 65% / 0.35)"
                                : "hsl(152 70% 60% / 0.35)"
                            }`,
                          }}
                        >
                          {kind}
                        </span>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-5 text-right">
                    <div className="text-[14.5px] font-semibold tabular-nums text-foreground">
                      {p.amount}
                    </div>
                    {p.amountSub && (
                      <div className="mt-0.5 text-[12px] text-muted-foreground">
                        {p.amountSub}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-5">
                    <div className="flex items-center gap-3">
                      <span
                        className="text-[13.5px] font-bold tabular-nums"
                        style={{ color: c, minWidth: 42 }}
                      >
                        {p.match}%
                      </span>
                      <div
                        className="h-1 w-[110px] overflow-hidden rounded-full"
                        style={{ background: "hsl(var(--surface-elevated-2))" }}
                      >
                        <div
                          className="h-full rounded-full"
                          style={{ background: c, width: `${p.match}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-5 text-[13px] text-muted-foreground">
                    {p.delay}
                  </td>
                  <td className="px-7 py-5 text-right">
                    <button
                      type="button"
                      className="rounded-md px-4 py-2 text-[13px] font-semibold text-foreground transition-colors"
                      style={{
                        background: "transparent",
                        border: "1px solid hsl(var(--border))",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background =
                          "hsl(var(--accent-soft))";
                        e.currentTarget.style.borderColor =
                          "hsl(var(--accent-border))";
                        e.currentTarget.style.color = "hsl(var(--accent))";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.borderColor =
                          "hsl(var(--border))";
                        e.currentTarget.style.color = "hsl(var(--foreground))";
                      }}
                    >
                      Candidater
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      </div>
    </div>
  );
};
