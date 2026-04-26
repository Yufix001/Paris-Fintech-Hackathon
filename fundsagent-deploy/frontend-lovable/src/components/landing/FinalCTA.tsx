import { useNavigate } from "react-router-dom";

export const FinalCTA = () => {
  const navigate = useNavigate();
  return (
    <section className="mx-auto w-full max-w-[1200px] px-8 pb-24">
      <div
        className="rounded-2xl px-8 py-14 text-center sm:px-10 sm:py-[56px]"
        style={{
          background:
            "linear-gradient(135deg, rgba(168,85,247,0.12), rgba(217,70,239,0.06))",
          border: "1px solid var(--accent-border)",
        }}
      >
        <h2
          className="mx-auto mb-3.5 font-sans font-bold text-foreground"
          style={{
            fontSize: "clamp(28px, 4.6vw, 44px)",
            lineHeight: 1.1,
            letterSpacing: "-1.5px",
          }}
        >
          Prêt à trouver vos financements ?
        </h2>
        <p className="mx-auto mb-7 max-w-[460px] text-[15px] text-muted-foreground">
          Importez votre pitch deck et obtenez votre diagnostic personnalisé en
          moins de 3 minutes.
        </p>
        <button
          type="button"
          onClick={() => navigate("/upload")}
          className="btn-violet inline-flex items-center gap-1.5 rounded-lg px-[26px] py-[14px] text-[15px] font-semibold"
        >
          Démarrer mon analyse <span aria-hidden="true">→</span>
        </button>
      </div>
    </section>
  );
};
