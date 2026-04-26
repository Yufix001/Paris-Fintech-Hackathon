import type { ReactNode } from "react";

type Tone = "success" | "warning";

type Item = { title: string; desc: string };

const CheckIcon = ({ size = 14 }: { size?: number }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const WarnIcon = ({ size = 14 }: { size?: number }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="8" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const BoltIcon = () => (
  <svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor">
    <path d="M13 2 3 14h7l-1 8 10-12h-7z" />
  </svg>
);

export const InsightsPanel = ({
  tone,
  title,
  items,
  insight,
}: {
  tone: Tone;
  title: string;
  items: Item[];
  insight: ReactNode;
}) => {
  const isSuccess = tone === "success";
  const accent = isSuccess ? "hsl(var(--success))" : "hsl(var(--warning))";

  return (
    <div
      className="flex flex-col rounded-[12px] p-6"
      style={{
        background: "hsl(var(--surface))",
        border: "1px solid hsl(var(--border))",
      }}
    >
      <div className="mb-5 flex items-center gap-3">
        <span
          className="flex h-8 w-8 items-center justify-center rounded-full text-white"
          style={{ background: accent }}
        >
          {isSuccess ? <CheckIcon size={16} /> : <WarnIcon size={16} />}
        </span>
        <h3 className="text-[15px] font-semibold text-foreground">{title}</h3>
      </div>

      <ul className="flex flex-1 flex-col gap-4">
        {items.map((item) => (
          <li key={item.title} className="flex gap-3">
            <span
              aria-hidden="true"
              className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-white"
              style={{ background: accent }}
            >
              {isSuccess ? <CheckIcon size={14} /> : <WarnIcon size={14} />}
            </span>
            <div>
              <div className="text-[14px] font-semibold text-foreground">
                {item.title}
              </div>
              <div className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                {item.desc}
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div
        className="mt-6 rounded-[10px] p-4"
        style={{
          background: "hsl(271 91% 65% / 0.08)",
          border: "1px solid hsl(var(--accent-border))",
        }}
      >
        <div
          className="mb-2 inline-flex items-center gap-1.5 text-[11px] font-bold uppercase"
          style={{ color: "hsl(var(--accent))", letterSpacing: "0.8px" }}
        >
          <BoltIcon />
          Insight IA
        </div>
        <div className="text-[13px] leading-relaxed text-muted-foreground">
          {insight}
        </div>
      </div>
    </div>
  );
};
