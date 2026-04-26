import { X, Check } from "lucide-react";

const before = [
  <>
    <strong className="font-semibold text-foreground">15 000 à 50 000 €</strong>{" "}
    de honoraires + success fee de 8 à 15%
  </>,
  <>
    <strong className="font-semibold text-foreground">3 à 6 semaines</strong>{" "}
    pour obtenir une première liste de programmes
  </>,
  <>Couverture limitée aux programmes que connaît votre consultant</>,
  <>Vous re-expliquez votre projet de zéro à chaque rendez-vous</>,
];

const after = [
  <>
    <strong className="font-semibold text-foreground">
      À partir de 49 €/mois
    </strong>
    , sans success fee
  </>,
  <>
    <strong className="font-semibold text-foreground">3 minutes</strong> pour un
    diagnostic complet et personnalisé
  </>,
  <>
    <strong className="font-semibold text-foreground">800+ programmes</strong>{" "}
    EU et FR couverts en continu
  </>,
  <>Votre projet est compris une fois, exploité partout</>,
];

export const Comparison = () => (
  <section className="mx-auto w-full max-w-[1200px] px-8 pb-24 sm:pb-[120px]">
    <div className="mx-auto mb-14 max-w-[720px] text-center">
      <div
        className="mb-3 text-[11px] font-bold uppercase tracking-[1.5px]"
        style={{ color: "#C084FC" }}
      >
        Pourquoi maintenant
      </div>
      <h2
        className="mb-3.5 font-sans font-bold text-foreground"
        style={{ fontSize: "clamp(26px, 4.4vw, 42px)", lineHeight: 1.1, letterSpacing: "-1.5px" }}
      >
        Le conseil en financement n'a pas changé depuis 20 ans
      </h2>
      <p className="mx-auto max-w-[560px] text-[15px] leading-[1.55] text-muted-foreground">
        Coûteux, lent, opaque. Nous remplaçons le cabinet par un agent IA.
      </p>
    </div>

    <div className="overflow-hidden rounded-[14px] border border-border bg-surface">
      <div className="grid md:grid-cols-2">
        {/* Before */}
        <div
          className="border-b p-8 md:border-b-0 md:border-r"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <span
            className="mb-3.5 inline-block rounded-[4px] px-2.5 py-[3px] text-[11px] font-semibold uppercase tracking-[0.3px] text-muted-foreground"
            style={{ background: "rgba(255,255,255,0.06)" }}
          >
            Avant
          </span>
          <h3
            className="mb-[18px] text-[20px] font-semibold text-foreground"
            style={{ letterSpacing: "-0.3px" }}
          >
            Avec un cabinet de conseil
          </h3>
          <ul className="flex flex-col gap-2.5">
            {before.map((item, i) => (
              <li
                key={i}
                className="grid gap-2.5 text-[14px] leading-[1.5] text-muted-foreground"
                style={{ gridTemplateColumns: "18px 1fr" }}
              >
                <X
                  className="mt-0.5 h-4 w-4 shrink-0"
                  style={{ stroke: "#EF4444", strokeWidth: 2.5 }}
                />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* After */}
        <div
          className="p-8"
          style={{
            background:
              "linear-gradient(135deg, rgba(168,85,247,0.06), transparent 70%)",
          }}
        >
          <span
            className="mb-3.5 inline-block rounded-[4px] px-2.5 py-[3px] text-[11px] font-semibold uppercase tracking-[0.3px]"
            style={{ background: "var(--accent-soft)", color: "#C084FC" }}
          >
            Avec SubventionAI
          </span>
          <h3
            className="mb-[18px] text-[20px] font-semibold text-foreground"
            style={{ letterSpacing: "-0.3px" }}
          >
            Votre agent IA dédié
          </h3>
          <ul className="flex flex-col gap-2.5">
            {after.map((item, i) => (
              <li
                key={i}
                className="grid gap-2.5 text-[14px] leading-[1.5] text-muted-foreground"
                style={{ gridTemplateColumns: "18px 1fr" }}
              >
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-success"
                  strokeWidth={2.5}
                />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  </section>
);
