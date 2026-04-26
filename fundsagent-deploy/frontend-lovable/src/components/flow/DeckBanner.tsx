const PdfIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const CheckIcon = () => (
  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export const DeckBanner = ({
  fileName = "PaymentFlow_Deck.pdf",
  meta = "14 slides · Analysé en 2,4 s · il y a 12 secondes",
}: {
  fileName?: string;
  meta?: string;
  onView?: () => void;
}) => {
  return (
    <div
      className="mb-4 flex items-center gap-4 rounded-[12px] px-5 py-4"
      style={{
        background: "hsl(var(--surface))",
        border: "1px solid hsl(var(--border))",
      }}
    >
      <span
        className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-[10px]"
        style={{
          background: "hsl(var(--accent-soft))",
          color: "hsl(var(--accent))",
          border: "1px solid hsl(var(--accent-border))",
        }}
      >
        <PdfIcon />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[15px] font-semibold text-foreground">
          {fileName}
        </div>
        <div className="mt-0.5 text-[12.5px] text-muted-foreground">
          {meta}
        </div>
      </div>
      <span
        className="flex-shrink-0 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold"
        style={{
          background: "hsl(142 76% 50% / 0.12)",
          color: "hsl(142 76% 60%)",
          border: "1px solid hsl(142 76% 50% / 0.3)",
        }}
      >
        <CheckIcon />
        Analysé
      </span>
    </div>
  );
};
