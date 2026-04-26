type Step = { id: number; label: string };

const STEPS: Step[] = [
  { id: 1, label: "Importer" },
  { id: 2, label: "Analyser" },
  { id: 3, label: "Diagnostic" },
  { id: 4, label: "Financements" },
];

export const Stepper = ({ current }: { current: 1 | 2 | 3 | 4 }) => {
  return (
    <nav
      aria-label="Étapes"
      className="mx-auto mb-10 grid w-full max-w-[800px] grid-cols-4 gap-4"
    >
      {STEPS.map((step) => {
        const state =
          step.id < current ? "done" : step.id === current ? "active" : "todo";
        const filled = state === "active" || state === "done";
        return (
          <div key={step.id} className="flex min-w-0 flex-col gap-2.5">
            <div className="flex items-center gap-2.5">
              <span
                className={`text-[13px] font-medium tabular-nums transition-colors ${
                  filled ? "text-foreground" : "text-faint"
                }`}
              >
                {step.id}
              </span>
              <span
                className={`overflow-hidden text-ellipsis whitespace-nowrap text-[14px] transition-colors ${
                  filled
                    ? "font-semibold text-foreground"
                    : "font-medium text-muted-foreground"
                }`}
              >
                {step.label}
              </span>
            </div>
            <div
              className="relative h-1.5 overflow-hidden rounded-full"
              style={{ background: "hsl(var(--surface-elevated-2))" }}
            >
              <div
                className="absolute inset-0 origin-left rounded-full transition-transform duration-500 ease-out"
                style={{
                  background: "var(--gradient-violet)",
                  transform: filled ? "scaleX(1)" : "scaleX(0)",
                }}
              />
              {state === "active" && (
                <div
                  aria-hidden="true"
                  className="absolute left-0 top-0 z-10 h-full w-1/4 rounded-full"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.18) 50%, transparent 100%)",
                    animation: "stepper-shimmer 2.6s ease-in-out infinite",
                  }}
                />
              )}
            </div>
          </div>
        );
      })}
    </nav>
  );
};
