type Item = { icon: JSX.Element; text: JSX.Element };

const Check = (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const ITEMS: Item[] = [
  {
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
    text: (
      <>
        Chiffré <strong className="font-medium text-foreground">TLS 1.3</strong>
      </>
    ),
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
    text: (
      <>
        Hébergé en{" "}
        <strong className="font-medium text-foreground">France</strong>
      </>
    ),
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 3h18v18H3z" />
        <path d="M9 9h6v6H9z" />
      </svg>
    ),
    text: (
      <>
        <strong className="font-medium text-foreground">Aucun</strong>{" "}
        entraînement IA
      </>
    ),
  },
  {
    icon: Check,
    text: (
      <>
        Conforme <strong className="font-medium text-foreground">RGPD</strong>
      </>
    ),
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
    text: (
      <>
        Suppression sous{" "}
        <strong className="font-medium text-foreground">24h</strong>
      </>
    ),
  },
];

export const MiniSecurity = () => (
  <div
    role="note"
    aria-label="Garanties de confidentialité"
    className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-3 px-4 py-3 sm:flex-nowrap sm:gap-x-6"
  >
    {ITEMS.map((item, i) => (
      <span
        key={i}
        className="inline-flex flex-shrink-0 items-center gap-1.5 whitespace-nowrap text-[12px] text-muted-foreground"
      >
        <span
          className="inline-flex h-[13px] w-[13px] flex-shrink-0 [&_svg]:h-[13px] [&_svg]:w-[13px] [&_svg]:fill-none [&_svg]:stroke-[hsl(var(--success))] [&_svg]:[stroke-width:2.5]"
        >
          {item.icon}
        </span>
        {item.text}
      </span>
    ))}
  </div>
);
