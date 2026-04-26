import { useNavigate } from "react-router-dom";
import { Navbar } from "@/components/landing/Navbar";
import { Stepper } from "@/components/flow/Stepper";
import { DeckPreview } from "@/components/flow/DeckPreview";
import { StreamPanel } from "@/components/flow/StreamPanel";
import { MiniSecurity } from "@/components/flow/MiniSecurity";

const Analyse = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="mx-auto w-full max-w-[900px] px-6 pb-24 pt-12 sm:pt-16">
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

        <Stepper current={2} />

        <section
          aria-labelledby="step2-title"
          role="region"
          className="grid grid-cols-1 items-start gap-4 md:grid-cols-[1fr_1.6fr]"
        >
          <h2 id="step2-title" className="sr-only">
            Étape 2 : Analyse en cours
          </h2>

          <DeckPreview />
          <StreamPanel onComplete={() => navigate("/diagnostic")} />
        </section>

        <MiniSecurity />
      </main>
    </div>
  );
};

export default Analyse;
