type Tone = "default" | "success" | "violet";
type Row = { label: string; value: string; tone?: Tone };

const ROWS: Row[] = [
  { label: "Nom", value: "PaymentFlow SAS" },
  { label: "Secteur", value: "Fintech B2B · Paiement" },
  { label: "Stade", value: "Seed" },
  { label: "Localisation", value: "Paris, France" },
  { label: "Équipe", value: "8 personnes" },
  { label: "ARR", value: "420 K€", tone: "success" },
  { label: "Levée recherchée", value: "2,5 M€", tone: "violet" },
];

const FileIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const valueColor = (tone?: Tone) => {
  if (tone === "success") return "hsl(var(--success))";
  if (tone === "violet") return "hsl(271 91% 75%)";
  return "hsl(var(--foreground))";
};

export const ProfilePanel = () => {
  return (
    <div
      className="rounded-[12px] p-6"
      style={{
        background: "hsl(var(--surface))",
        border: "1px solid hsl(var(--border))",
      }}
    >
      <div className="mb-5 flex items-center gap-2.5">
        <span
          className="flex h-6 w-6 items-center justify-center rounded-md"
          style={{
            background: "hsl(var(--accent-soft))",
            color: "hsl(var(--accent))",
            border: "1px solid hsl(var(--accent-border))",
          }}
        >
          <FileIcon />
        </span>
        <h3 className="text-[15px] font-semibold text-foreground">
          Profil détecté
        </h3>
      </div>
      <dl className="flex flex-col">
        {ROWS.map((row, i) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-3 py-3"
            style={
              i < ROWS.length - 1
                ? { borderBottom: "1px solid hsl(var(--border-soft))" }
                : undefined
            }
          >
            <dt className="text-[13px] text-muted-foreground">{row.label}</dt>
            <dd
              className="text-right text-[14px] font-semibold"
              style={{ color: valueColor(row.tone) }}
            >
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
};
