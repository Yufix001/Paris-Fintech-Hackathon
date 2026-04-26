import { Check, AlertTriangle, Sparkles, Trophy } from "lucide-react";
import { useAgent } from "@/state/AgentContext";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Deck = Record<string, any>;

type ImprovementRule = {
  id: string;
  check: (d: Deck) => boolean;
  title: string;
  sub: string;
  points: number;
  fundsKeur: number;
};

type StrengthRule = {
  id: string;
  check: (d: Deck) => boolean;
  title: (d: Deck) => string;
  sub: (d: Deck) => string;
};

const IMPROVEMENT_RULES: ImprovementRule[] = [
  {
    id: "esg",
    check: (d) =>
      !d?.impact?.co2_reduction_t_yr5 &&
      !(d?.impact?.green_deal_alignment?.length),
    title: "Plan d'impact ESG",
    sub: "+8 points sur Horizon Europe",
    points: 8,
    fundsKeur: 400,
  },
  {
    id: "roadmap",
    check: (d) => !d?.funding_ask?.horizon_months,
    title: "Roadmap 36 mois détaillée",
    sub: "Requis par EIC Accelerator",
    points: 9,
    fundsKeur: 600,
  },
  {
    id: "diversity",
    check: (d) => d?.team?.gender_balance_pct_female == null,
    title: "Diversité fondateurs",
    sub: "+12 points sur Women TechEU",
    points: 12,
    fundsKeur: 75,
  },
  {
    id: "ip",
    check: (d) => !d?.product?.ip_status,
    title: "Statut IP / brevets",
    sub: "+10 points sur EIC Pathfinder",
    points: 10,
    fundsKeur: 300,
  },
  {
    id: "pilots",
    check: (d) => !(d?.traction?.pilot_partners?.length),
    title: "Partenaires industriels pilotes",
    sub: "+9 points sur France 2030",
    points: 9,
    fundsKeur: 350,
  },
  {
    id: "region",
    check: (d) => !d?.company?.region,
    title: "Ancrage régional précisé",
    sub: "+15 points FEDER régional",
    points: 15,
    fundsKeur: 500,
  },
];

const STRENGTH_RULES: StrengthRule[] = [
  {
    id: "phds",
    check: (d) => (d?.team?.phds ?? 0) > 0,
    title: (d) =>
      `Équipe R&D · ${d?.team?.phds} doctorat${d?.team?.phds > 1 ? "s" : ""}`,
    sub: () => "Profil recherche éligible ERC/EIC",
  },
  {
    id: "revenue",
    check: (d) => (d?.traction?.revenue_eur_last_year ?? 0) > 0,
    title: () => "Traction démontrée",
    sub: (d) =>
      `ARR ${Math.round((d?.traction?.revenue_eur_last_year ?? 0) / 1000)} K€ · clients actifs`,
  },
  {
    id: "ip_strength",
    check: (d) => !!d?.product?.ip_status,
    title: () => "Innovation IP protégée",
    sub: (d) => `${d?.product?.ip_status} · avantage compétitif documenté`,
  },
  {
    id: "green_deal",
    check: (d) => (d?.impact?.green_deal_alignment?.length ?? 0) > 0,
    title: () => "Alignement Green Deal EU",
    sub: (d) =>
      (d?.impact?.green_deal_alignment as string[]).slice(0, 3).join(", "),
  },
  {
    id: "pilots_strength",
    check: (d) => (d?.traction?.pilot_partners?.length ?? 0) > 0,
    title: () => "Partenaires pilotes identifiés",
    sub: (d) =>
      (d?.traction?.pilot_partners as string[]).slice(0, 3).join(", "),
  },
  {
    id: "deeptech",
    check: (d) => !!d?.company?.deeptech,
    title: () => "Profil deeptech EIC éligible",
    sub: () => "Priorité haute EIC Accelerator & Horizon",
  },
  {
    id: "consortium",
    check: (d) => !!d?.funding_ask?.open_to_consortium,
    title: () => "Ouvert au consortium EU",
    sub: () => "Eligible programmes multi-partenaires Horizon",
  },
  {
    id: "team_size",
    check: (d) => (d?.team?.size ?? 0) >= 4,
    title: (d) => `Équipe structurée · ${d?.team?.size} personnes`,
    sub: () => "Structure opérationnelle démontrée",
  },
];

// Fallback mock data (shown when no live data yet)
const MOCK_STRENGTHS = [
  { title: "Équipe technique solide", sub: "2 docteurs ML, ex-Stripe et BNP Paribas" },
  { title: "Traction démontrée · +18% MoM", sub: "34 clients B2B européens" },
  { title: "Innovation IA brevetable", sub: "Algo détection fraude propriétaire" },
  { title: "Marché EU prioritaire", sub: "PSD2/PSD3 & souveraineté financière" },
];

const MOCK_IMPROVEMENTS = [
  { title: "Plan d'impact ESG", sub: "+8 points sur Horizon Europe" },
  { title: "Roadmap 36 mois détaillée", sub: "Requis par EIC Accelerator" },
  { title: "Diversité fondateurs", sub: "+12 points sur Women TechEU" },
];

export function StrengthsAndImprovements() {
  const { events, hasLiveData } = useAgent();

  // Extract parsed deck from SSE events
  const parsedEvent = events.find((e) => e.type === "parsed");
  const deck = parsedEvent?.payload as Deck | undefined;

  // Compute dynamic data only when we have live parsed data
  const strengths = hasLiveData && deck
    ? STRENGTH_RULES.filter((r) => r.check(deck)).map((r) => ({
        title: r.title(deck),
        sub: r.sub(deck),
      }))
    : MOCK_STRENGTHS;

  const improvements = hasLiveData && deck
    ? IMPROVEMENT_RULES.filter((r) => r.check(deck))
    : null; // null = use mock

  const displayImprovements = improvements
    ? improvements.map((r) => ({ title: r.title, sub: r.sub }))
    : MOCK_IMPROVEMENTS;

  const totalPoints = improvements
    ? improvements.reduce((s, r) => s + r.points, 0)
    : 29;
  const totalFundsKeur = improvements
    ? improvements.reduce((s, r) => s + r.fundsKeur, 0)
    : 1200;

  const baseScore = 87;
  const finalScore = Math.min(99, baseScore + Math.round(totalPoints * 0.35));
  const extraPrograms = improvements ? Math.min(improvements.length, 6) : 4;

  const allGood = improvements !== null && improvements.length === 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Points forts */}
      <div className="bg-[#0E0F11] border border-[#24262B] rounded-[10px] p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-[18px] h-[18px] rounded-md bg-emerald-500/15 text-emerald-400 flex items-center justify-center">
            <Check className="w-3 h-3" strokeWidth={3} />
          </div>
          <h3 className="text-sm font-semibold text-[#F0F2F5]">
            Points forts du dossier
          </h3>
        </div>

        <ul className="divide-y divide-[#1A1C20]">
          {(strengths.length > 0 ? strengths : MOCK_STRENGTHS).map((item, i) => (
            <li key={i} className="grid grid-cols-[20px_1fr] gap-3 py-2.5 items-start">
              <div className="w-[18px] h-[18px] rounded-full bg-emerald-500 text-[#08090A] flex items-center justify-center mt-0.5 flex-shrink-0">
                <Check className="w-2.5 h-2.5" strokeWidth={3.5} />
              </div>
              <div>
                <div className="text-[13px] font-medium text-[#F0F2F5]">{item.title}</div>
                <div className="text-xs text-[#9DA3AC] mt-0.5">{item.sub}</div>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* À renforcer */}
      <div className="bg-[#0E0F11] border border-[#24262B] rounded-[10px] p-5">
        <div className="flex items-center gap-2 mb-4">
          {allGood ? (
            <div className="w-[18px] h-[18px] rounded-md bg-violet-500/15 text-violet-400 flex items-center justify-center">
              <Trophy className="w-3 h-3" strokeWidth={2.5} />
            </div>
          ) : (
            <div className="w-[18px] h-[18px] rounded-md bg-amber-500/15 text-amber-400 flex items-center justify-center">
              <AlertTriangle className="w-3 h-3" strokeWidth={2.5} />
            </div>
          )}
          <h3 className="text-sm font-semibold text-[#F0F2F5]">
            {allGood ? "Dossier complet" : "À renforcer pour décrocher plus"}
          </h3>
        </div>

        {allGood ? (
          <div className="py-4 text-center">
            <div className="text-[13px] font-medium text-[#F0F2F5] mb-1">
              Toutes les sections sont renseignées
            </div>
            <div className="text-xs text-[#9DA3AC]">
              Votre pitchdeck est complet — score maximal d'éligibilité.
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-[#1A1C20]">
            {displayImprovements.map((item, i) => (
              <li key={i} className="grid grid-cols-[20px_1fr] gap-3 py-2.5 items-start">
                <div className="w-[18px] h-[18px] rounded-full bg-amber-400 text-[#08090A] flex items-center justify-center mt-0.5 flex-shrink-0 text-[10px] font-bold">
                  !
                </div>
                <div>
                  <div className="text-[13px] font-medium text-[#F0F2F5]">{item.title}</div>
                  <div className="text-xs text-[#9DA3AC] mt-0.5">{item.sub}</div>
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Insight IA box */}
        <div className="mt-4 bg-purple-500/[0.14] border border-purple-500/35 rounded-lg p-3.5">
          <div className="flex items-center gap-1.5 mb-1.5">
            <Sparkles className="w-2.5 h-2.5 text-purple-300" strokeWidth={3} />
            <span className="text-[11px] font-semibold text-purple-300 uppercase tracking-wide">
              Insight IA
            </span>
          </div>
          {allGood ? (
            <p className="text-[13px] text-[#F0F2F5] leading-relaxed">
              Score d'éligibilité estimé à{" "}
              <strong className="font-semibold">98/100</strong> — vous êtes
              positionné sur le{" "}
              <strong className="font-semibold text-emerald-400">top 5%</strong>{" "}
              des candidats.
            </p>
          ) : (
            <p className="text-[13px] text-[#F0F2F5] leading-relaxed">
              En complétant ces {displayImprovements.length} point
              {displayImprovements.length > 1 ? "s" : ""}, votre score passe de{" "}
              <strong className="font-semibold">{baseScore}</strong> à{" "}
              <strong className="font-semibold">{finalScore}</strong> — débloquant{" "}
              {extraPrograms} programmes premium pour{" "}
              <strong className="font-semibold text-emerald-400">
                +{totalFundsKeur >= 1000
                  ? `${(totalFundsKeur / 1000).toFixed(1).replace(".", ",")} M€`
                  : `${totalFundsKeur} K€`}
              </strong>
              .
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
