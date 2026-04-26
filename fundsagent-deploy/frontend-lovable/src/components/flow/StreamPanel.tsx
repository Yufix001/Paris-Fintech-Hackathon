import { useEffect, useState } from "react";

type StepState = "todo" | "active" | "done";

const STEPS = [
  { id: 1, label: "Extraction du profil entreprise", duration: 900 },
  { id: 2, label: "Classification thématique", duration: 700 },
  { id: 3, label: "Raisonnement sur l'éligibilité", duration: 1100 },
  { id: 4, label: "Matching programmes éligibles", duration: 900 },
] as const;

const CheckIcon = ({ size = 13 }: { size?: number }) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export const StreamPanel = ({ onComplete }: { onComplete?: () => void }) => {
  const [states, setStates] = useState<StepState[]>([
    "todo",
    "todo",
    "todo",
    "todo",
  ]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

    (async () => {
      for (let i = 0; i < STEPS.length; i++) {
        if (cancelled) return;
        setStates((s) => {
          const next = [...s];
          next[i] = "active";
          return next;
        });
        await sleep(STEPS[i].duration);
        if (cancelled) return;
        setStates((s) => {
          const next = [...s];
          next[i] = "done";
          return next;
        });
      }
      if (cancelled) return;
      setDone(true);
      await sleep(1100);
      if (cancelled) return;
      onComplete?.();
    })();

    return () => {
      cancelled = true;
    };
  }, [onComplete]);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="false"
      className="overflow-hidden rounded-[10px] transition-[border-color,box-shadow] duration-[400ms]"
      style={{
        background: "hsl(var(--surface))",
        border: done
          ? "1px solid rgba(74,222,128,0.45)"
          : "1px solid hsl(var(--border))",
        boxShadow: done
          ? "0 0 0 1px rgba(74,222,128,0.15), 0 8px 32px rgba(74,222,128,0.08)"
          : "none",
        animation: done ? "stream-success-flash 0.7s ease-out" : undefined,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2.5 px-5 py-3.5"
        style={{ borderBottom: "1px solid hsl(var(--border))" }}
      >
        <span
          aria-hidden="true"
          className="inline-block h-2 w-2 rounded-full"
          style={{
            background: done ? "hsl(var(--success))" : "hsl(var(--accent))",
            animation: done ? undefined : "stream-pulse 1.6s ease-in-out infinite",
          }}
        />
        <span
          className={`text-[13px] font-semibold transition-colors duration-[400ms] ${
            done ? "" : "text-foreground"
          }`}
          style={done ? { color: "hsl(var(--success))" } : undefined}
        >
          {done ? "Analyse terminée" : "Analyse en cours…"}
        </span>
        <span
          aria-hidden="true"
          className="ml-auto flex h-[22px] w-[22px] items-center justify-center rounded-full"
          style={{
            background: "hsl(var(--success))",
            color: "hsl(var(--background))",
            opacity: done ? 1 : 0,
            transform: done ? "scale(1)" : "scale(0.4)",
            transition: "all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)",
          }}
        >
          <CheckIcon />
        </span>
      </div>

      {/* Steps */}
      {STEPS.map((step, i) => {
        const state = states[i];
        const isActive = state !== "todo";
        return (
          <div
            key={step.id}
            className={`px-5 py-4 transition-opacity duration-300 ${
              isActive ? "opacity-100" : "opacity-40"
            } ${i < STEPS.length - 1 ? "border-b" : ""}`}
            style={
              i < STEPS.length - 1
                ? { borderColor: "hsl(var(--border-soft))" }
                : undefined
            }
          >
            <div className="flex items-center gap-2.5 text-[13px] font-medium text-foreground">
              <StepIcon state={state} index={step.id} />
              <span>{step.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const StepIcon = ({ state, index }: { state: StepState; index: number }) => {
  const base =
    "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-semibold";

  if (state === "done") {
    return (
      <span
        className={base}
        style={{
          background: "hsl(var(--success) / 0.14)",
          border: "1px solid rgba(74,222,128,0.3)",
          color: "hsl(var(--success))",
        }}
      >
        <CheckIcon size={11} />
      </span>
    );
  }
  if (state === "active") {
    return (
      <span
        className={base}
        style={{
          background: "hsl(var(--accent-soft))",
          border: "1px solid hsl(var(--accent-border))",
          color: "hsl(var(--accent))",
        }}
      >
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{
            border: "1.5px solid hsl(var(--accent-soft))",
            borderTopColor: "hsl(var(--accent))",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </span>
    );
  }
  return (
    <span
      className={base}
      style={{
        background: "hsl(var(--surface-elevated-2))",
        border: "1px solid hsl(var(--border))",
        color: "hsl(var(--text-faint))",
      }}
    >
      {index}
    </span>
  );
};
