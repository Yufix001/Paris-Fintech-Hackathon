import { useNavigate } from "react-router-dom";
import { Navbar } from "@/components/landing/Navbar";
import { Stepper } from "@/components/flow/Stepper";
import { DeckBanner } from "@/components/flow/DeckBanner";
import { ProfilePanel } from "@/components/flow/ProfilePanel";
import { TagsPanel } from "@/components/flow/TagsPanel";
import { StrengthsAndImprovements } from "@/components/flow/StrengthsAndImprovements";
import { MiniSecurity } from "@/components/flow/MiniSecurity";


const Diagnostic = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background text-foreground">
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

        <Stepper current={3} />

        <section
          aria-labelledby="step3-title"
          role="region"
          className="flex flex-col gap-4"
        >
          <h2 id="step3-title" className="sr-only">
            Étape 3 : Diagnostic du pitch deck
          </h2>

          <DeckBanner />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <ProfilePanel />
            <TagsPanel />
          </div>

          <StrengthsAndImprovements />

          <div className="mt-4 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={() => navigate("/upload")}
              className="inline-flex items-center gap-2 rounded-lg px-5 py-3 text-[14px] font-semibold text-foreground transition-colors"
              style={{
                background: "transparent",
                border: "1px solid hsl(var(--border))",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background =
                  "hsl(var(--surface-elevated))")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "transparent")
              }
            >
              ← Retour
            </button>
            <button
              type="button"
              onClick={() => navigate("/financements")}
              className="btn-violet inline-flex items-center gap-2 rounded-lg px-6 py-3 text-[14px] font-semibold"
            >
              Voir mes financements →
            </button>
          </div>
        </section>

        <MiniSecurity />
      </main>
    </div>
  );
};

export default Diagnostic;
