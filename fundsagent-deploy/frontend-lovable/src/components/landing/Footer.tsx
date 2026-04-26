import { Linkedin, Twitter, Github } from "lucide-react";
import { Logo } from "./Logo";

const cols = [
  {
    title: "Produit",
    links: ["Fonctionnalités", "Tarifs", "Sécurité", "Changelog"],
  },
  {
    title: "Entreprise",
    links: ["À propos", "Blog", "Carrières", "Contact"],
  },
  {
    title: "Ressources",
    links: ["Guide financements EU", "Test d'éligibilité", "FAQ", "Aide"],
  },
  {
    title: "Légal",
    links: ["Confidentialité", "CGU", "DPA", "Cookies"],
  },
];

export const Footer = () => (
  <footer className="border-t border-border bg-background">
    <div className="mx-auto w-full max-w-[1200px] px-8 py-16">
      <div className="grid gap-12 lg:grid-cols-[1.4fr_1fr] lg:gap-16">
        <div className="max-w-md">
          <Logo />
          <p className="mt-4 text-[13px] leading-[1.6] text-muted-foreground">
            L'agent IA qui identifie tous vos financements éligibles à partir de
            votre pitch deck. Conçu en Europe, pour l'Europe.
          </p>
          <div className="mt-5 flex items-center gap-2">
            {[
              { icon: Linkedin, label: "LinkedIn" },
              { icon: Twitter, label: "X" },
              { icon: Github, label: "GitHub" },
            ].map(({ icon: Icon, label }) => (
              <a
                key={label}
                href="#"
                aria-label={label}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface text-muted-foreground transition-colors hover:border-[hsl(220_6%_20%)] hover:text-foreground"
              >
                <Icon className="h-4 w-4" />
              </a>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          {cols.map((c) => (
            <div key={c.title}>
              <div className="text-[11px] font-bold uppercase tracking-[1px] text-foreground">
                {c.title}
              </div>
              <ul className="mt-4 space-y-3">
                {c.links.map((l) => (
                  <li key={l}>
                    <a
                      href="#"
                      className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {l}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-14 flex flex-col items-start justify-between gap-3 border-t border-border pt-7 text-[12px] text-muted-foreground sm:flex-row sm:items-center">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>© {new Date().getFullYear()} SubventionAI</span>
          <span className="text-border">·</span>
          <span>Conçu en Europe</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="inline-flex h-1.5 w-1.5 rounded-full"
            style={{ background: "hsl(var(--success))" }}
          />
          <span>Tous les systèmes opérationnels</span>
        </div>
      </div>
    </div>
  </footer>
);
