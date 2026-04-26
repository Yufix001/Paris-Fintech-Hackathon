export const DeckPreview = () => {
  return (
    <div
      className="rounded-[10px] p-5"
      style={{
        background: "hsl(var(--surface))",
        border: "1px solid hsl(var(--border))",
      }}
    >
      <div
        className="mb-2.5 text-[11px] font-semibold uppercase"
        style={{ color: "hsl(var(--text-faint))", letterSpacing: "0.5px" }}
      >
        Pitch deck
      </div>

      <div
        aria-hidden="true"
        className="relative mb-3.5 overflow-hidden rounded-lg"
        style={{
          background: "hsl(var(--surface-elevated-2))",
          border: "1px solid hsl(var(--border))",
          aspectRatio: "4 / 3",
        }}
      >
        <div className="absolute inset-0 flex flex-col gap-2 px-5 py-6">
          <div
            className="rounded-sm"
            style={{
              height: "10px",
              width: "60%",
              background: "hsl(var(--text-faint))",
            }}
          />
          <div
            className="rounded-sm"
            style={{ height: "6px", width: "40%", background: "hsl(var(--border))" }}
          />
          <div style={{ height: "12px" }} />
          <div
            className="rounded-sm"
            style={{ height: "6px", width: "100%", background: "hsl(var(--border))" }}
          />
          <div
            className="rounded-sm"
            style={{ height: "6px", width: "70%", background: "hsl(var(--border))" }}
          />
          <div
            className="rounded-sm"
            style={{ height: "6px", width: "100%", background: "hsl(var(--border))" }}
          />
          <div
            className="rounded-sm"
            style={{ height: "6px", width: "40%", background: "hsl(var(--border))" }}
          />
          <div style={{ height: "8px" }} />
          <div
            className="rounded-sm"
            style={{ height: "6px", width: "100%", background: "hsl(var(--border))" }}
          />
          <div
            className="rounded-sm"
            style={{ height: "6px", width: "70%", background: "hsl(var(--border))" }}
          />
        </div>

        {/* Scan line */}
        <div
          className="pointer-events-none absolute left-0 right-0"
          style={{
            height: "2px",
            background:
              "linear-gradient(90deg, transparent, hsl(var(--accent)), transparent)",
            boxShadow: "0 0 12px hsl(var(--accent))",
            animation: "deck-scan 2.5s ease-in-out infinite",
          }}
        />
      </div>

      <div className="text-[13px] font-semibold text-foreground">
        PaymentFlow_Deck.pdf
      </div>
      <div className="mt-0.5 text-[12px] text-muted-foreground">
        14 slides · 4,2 Mo
      </div>
    </div>
  );
};
