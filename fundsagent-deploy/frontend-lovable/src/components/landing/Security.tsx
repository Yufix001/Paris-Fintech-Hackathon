import { Shield, Lock, Globe, Square, Clock } from "lucide-react";

const items = [
  {
    icon: Lock,
    title: "Chiffrement de bout en bout",
    desc: "TLS 1.3 en transit, AES-256 au repos. Standard bancaire.",
  },
  {
    icon: Globe,
    title: "Hébergement 100% européen",
    desc: "Données stockées en France (OVHcloud Gravelines).",
  },
  {
    icon: Square,
    title: "Aucun entraînement IA",
    desc: "Votre pitch deck n'est jamais utilisé pour entraîner des modèles.",
  },
  {
    icon: Clock,
    title: "Suppression à tout moment",
    desc: "Documents supprimés sous 24h ou immédiatement (RGPD art. 17).",
  },
];

const badges = ["RGPD", "SOC 2 Type II", "ISO 27001", "Hébergement HDS"];

export const Security = () => (
  <section className="mx-auto w-full max-w-[1200px] px-8 pb-24 sm:pb-[120px]">
    <div className="mx-auto mb-14 max-w-[640px] text-center">
      <div
        className="mb-3 text-[11px] font-bold uppercase tracking-[1.5px]"
        style={{ color: "#C084FC" }}
      >
        Sécurité
      </div>
      <h2
        className="mb-3.5 font-sans font-bold text-foreground"
        style={{ fontSize: "clamp(28px, 4.4vw, 42px)", lineHeight: 1.1, letterSpacing: "-1.5px" }}
      >
        Votre pitch deck reste à vous
      </h2>
      <p className="mx-auto max-w-[560px] text-[15px] leading-[1.55] text-muted-foreground">
        Confidentialité bancaire, hébergement souverain, aucun entraînement IA
        sur vos données.
      </p>
    </div>

    <section
      aria-labelledby="security-title-landing"
      className="rounded-[14px] border border-border bg-surface p-8 sm:p-10"
    >
      <header className="mb-7 flex items-start gap-4">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px]"
          style={{
            background: "var(--accent-soft)",
            border: "1px solid var(--accent-border)",
          }}
          aria-hidden="true"
        >
          <Shield className="h-5 w-5 text-primary" strokeWidth={1.8} />
        </span>
        <div>
          <div
            id="security-title-landing"
            className="text-[17px] font-semibold text-foreground"
            style={{ letterSpacing: "-0.3px" }}
          >
            Vos données restent confidentielles
          </div>
          <div className="mt-1 text-[13px] text-muted-foreground">
            Conformité RGPD · Hébergement européen · Aucun partage avec des tiers
          </div>
        </div>
      </header>

      <div role="list" className="grid gap-5 sm:grid-cols-2">
        {items.map((it) => (
          <div
            key={it.title}
            role="listitem"
            className="flex items-start gap-3.5"
          >
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border"
              style={{ background: "hsl(var(--surface-elevated))" }}
              aria-hidden="true"
            >
              <it.icon className="h-[18px] w-[18px] text-primary" strokeWidth={1.8} />
            </span>
            <div>
              <div className="text-[14px] font-semibold text-foreground">
                {it.title}
              </div>
              <div className="mt-1 text-[13px] leading-[1.55] text-muted-foreground">
                {it.desc}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div
        aria-label="Certifications et conformité"
        className="mt-8 flex flex-wrap items-center gap-2.5 border-t pt-6"
        style={{ borderColor: "hsl(var(--border-soft))" }}
      >
        <span className="text-[11px] font-semibold uppercase tracking-[1px] text-faint">
          Conformité
        </span>
        {badges.map((b) => (
          <span
            key={b}
            className="rounded-md border border-border px-2.5 py-1 text-[12px] font-medium text-muted-foreground"
            style={{ background: "hsl(var(--surface-elevated))" }}
          >
            {b}
          </span>
        ))}
      </div>
    </section>
  </section>
);
