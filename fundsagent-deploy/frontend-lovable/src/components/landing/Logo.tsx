import logoSrc from "@/assets/logo.png";

export const Logo = ({ className = "" }: { className?: string }) => (
  <a
    href="#top"
    className={`flex items-center gap-2.5 text-sm font-semibold tracking-tight text-foreground transition-opacity hover:opacity-85 ${className}`}
    aria-label="SubventionAI — accueil"
  >
    <img
      src={logoSrc}
      alt=""
      aria-hidden="true"
      className="h-10 w-10 object-contain"
      style={{ filter: "drop-shadow(0 2px 8px rgba(168,85,247,0.35))" }}
    />
    <span>SubventionAI</span>
  </a>
);
