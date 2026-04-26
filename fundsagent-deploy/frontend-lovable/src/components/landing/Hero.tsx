import { useNavigate } from "react-router-dom";
import { HeroVisual } from "./HeroVisual";

export const Hero = () => {
  const navigate = useNavigate();
  return (
    <section
      id="top"
      className="bg-hero-radial bg-hero-grid relative isolate overflow-hidden"
    >
      {/* Visual area */}
      <div className="mx-auto w-full max-w-[1200px] px-8 pb-0 pt-16 sm:pt-16">
        <HeroVisual />
      </div>

      {/* Content area */}
      <div className="relative z-10 mx-auto w-full max-w-[1200px] px-8 pb-20">
        <h1
          id="hero-title"
          className="font-sans font-bold text-foreground"
          style={{
            fontSize: "clamp(38px, 7vw, 76px)",
            lineHeight: 1.02,
            letterSpacing: "-2.5px",
            marginBottom: "24px",
          }}
        >
          Trouvez vos financements
          <br />
          en 3 minutes.
        </h1>

        <p className="mb-9 max-w-[580px] text-[18px] leading-[1.6] text-muted-foreground">
          Remplacez votre cabinet de conseil par un agent IA qui identifie tous
          vos financements éligibles à partir de votre pitch deck.
        </p>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => navigate("/upload")}
            className="btn-glow inline-flex items-center gap-1.5 rounded-lg px-[26px] py-[14px] text-[15px] font-semibold"
          >
            <span>Commencer gratuitement</span>
            <span aria-hidden="true">→</span>
          </button>
          <button
            type="button"
            className="btn-ghost-soft inline-flex items-center gap-1.5 rounded-lg px-[26px] py-[14px] text-[15px] font-semibold"
            onClick={() =>
              document
                .getElementById("how-it-works")
                ?.scrollIntoView({ behavior: "smooth" })
            }
          >
            Voir comment ça marche
          </button>
        </div>
      </div>
    </section>
  );
};
