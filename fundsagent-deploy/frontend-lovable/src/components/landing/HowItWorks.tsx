import { Upload, Settings, FileText } from "lucide-react";

const steps = [
  {
    icon: Upload,
    title: "Importez votre deck",
    desc:
      "Glissez-déposez votre pitch deck ou collez l'URL de votre site. L'IA extrait automatiquement secteur, traction, équipe et tech.",
  },
  {
    icon: Settings,
    title: "L'IA matche votre projet",
    desc:
      "4 agents IA spécialisés croisent votre profil avec les 800+ programmes EU et calculent un score d'éligibilité pour chacun.",
  },
  {
    icon: FileText,
    title: "Candidatez en un clic",
    desc:
      "Pour chaque programme matché, recevez un dossier de candidature pré-rempli. Vous n'avez plus qu'à valider et soumettre.",
  },
];

export const HowItWorks = () => (
  <section
    id="how-it-works"
    className="mx-auto w-full max-w-[1200px] px-8 pb-24 sm:pb-[120px]"
  >
    <div className="mx-auto mb-14 max-w-[640px] text-center">
      <div
        className="mb-3 text-[11px] font-bold uppercase tracking-[1.5px]"
        style={{ color: "#C084FC" }}
      >
        Comment ça marche
      </div>
      <h2
        className="mb-3.5 font-sans font-bold text-foreground"
        style={{ fontSize: "clamp(28px, 4.4vw, 42px)", lineHeight: 1.1, letterSpacing: "-1.5px" }}
      >
        Trois étapes, zéro paperasse
      </h2>
      <p className="mx-auto max-w-[560px] text-[15px] leading-[1.55] text-muted-foreground">
        Notre IA fait ce qu'un cabinet de conseil en financement fait en 3
        semaines, en quelques minutes.
      </p>
    </div>

    <div className="grid gap-4 md:grid-cols-3">
      {steps.map((s) => (
        <article
          key={s.title}
          className="rounded-[14px] border border-border bg-surface p-7 transition-all duration-200 hover:-translate-y-0.5"
          style={{ borderColor: "hsl(var(--border))" }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.borderColor = "var(--accent-border)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.borderColor = "hsl(var(--border))")
          }
        >
          <div
            className="mb-[18px] flex h-11 w-11 items-center justify-center rounded-[10px]"
            style={{
              background: "var(--accent-soft)",
              border: "1px solid var(--accent-border)",
            }}
          >
            <s.icon className="h-[22px] w-[22px] text-primary" strokeWidth={1.8} />
          </div>
          <h3
            className="mb-2 text-[17px] font-semibold text-foreground"
            style={{ letterSpacing: "-0.3px" }}
          >
            {s.title}
          </h3>
          <p className="text-[14px] leading-[1.6] text-muted-foreground">
            {s.desc}
          </p>
        </article>
      ))}
    </div>
  </section>
);
