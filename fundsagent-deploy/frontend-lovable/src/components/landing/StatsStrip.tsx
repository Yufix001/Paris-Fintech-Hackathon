const stats = [
  { value: "812", label: "Programmes couverts", accent: true },
  { value: "3 min", label: "Pour votre diagnostic" },
  { value: "−85%", label: "vs cabinet de conseil" },
  { value: "5,8 M€", label: "Financement médian détecté" },
];

export const StatsStrip = () => (
  <section
    aria-label="Chiffres clés"
    className="mx-auto grid w-full max-w-[1200px] grid-cols-2 px-8 py-16 sm:grid-cols-4 sm:py-20"
  >
    {stats.map((s) => (
      <div key={s.label} className="px-5 py-6 text-center">
        <div
          className={`mb-2 font-bold leading-none ${s.accent ? "text-gradient-violet" : "text-foreground"}`}
          style={{ fontSize: "36px", letterSpacing: "-1.5px" }}
        >
          {s.value}
        </div>
        <div className="text-[12px] font-medium text-muted-foreground">
          {s.label}
        </div>
      </div>
    ))}
  </section>
);
