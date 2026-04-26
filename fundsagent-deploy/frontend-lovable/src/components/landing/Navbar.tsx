import { useNavigate } from "react-router-dom";
import { Logo } from "./Logo";
import { Button } from "@/components/ui/button";

export const Navbar = () => {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-50 flex h-14 items-center gap-6 border-b border-border bg-background px-6">
      <button
        type="button"
        onClick={() => navigate("/")}
        className="flex items-center"
        aria-label="Retour à l'accueil"
      >
        <Logo />
      </button>
      <div className="ml-auto flex items-center gap-2">
        <Button
          variant="ghost"
          onClick={() => navigate("/")}
          className="btn-ghost-soft h-9 rounded-md px-4 text-[13px] font-medium"
          aria-label="Réinitialiser la démo"
        >
          Reset
        </Button>
      </div>
    </header>
  );
};
