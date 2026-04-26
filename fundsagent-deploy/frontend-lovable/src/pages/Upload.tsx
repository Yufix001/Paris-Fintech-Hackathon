import { Navbar } from "@/components/landing/Navbar";
import { Stepper } from "@/components/flow/Stepper";
import { UploadZone } from "@/components/flow/UploadZone";
import { MiniSecurity } from "@/components/flow/MiniSecurity";

const Upload = () => {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="mx-auto w-full max-w-[760px] px-6 pb-24 pt-12 sm:pt-16">
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

        <Stepper current={1} />

        <section aria-labelledby="step1-title" role="region">
          <h2 id="step1-title" className="sr-only">
            Étape 1 : Importer votre pitch deck
          </h2>

          <UploadZone />

          <p className="mt-7 text-center text-[13px] text-muted-foreground">
            Votre pitch deck est protégé. Aucune information n'est partagée avec
            des tiers.
          </p>

          <MiniSecurity />
        </section>
      </main>
    </div>
  );
};

export default Upload;
