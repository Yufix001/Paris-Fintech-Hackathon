type TagTone = "violet" | "blue" | "emerald" | "amber";

type Tag = { label: string; tone: TagTone };
type Group = { title: string; tags: Tag[] };

const GROUPS: Group[] = [
  {
    title: "Verticales",
    tags: [
      { label: "B2B Fintech", tone: "blue" },
      { label: "Embedded Finance", tone: "blue" },
      { label: "SaaS", tone: "blue" },
    ],
  },
  {
    title: "Thématiques EU",
    tags: [
      { label: "Digital transition", tone: "emerald" },
      { label: "Deep tech", tone: "emerald" },
      { label: "SME scale-up", tone: "emerald" },
    ],
  },
  {
    title: "Innovation",
    tags: [
      { label: "IA / ML", tone: "violet" },
      { label: "Real-time payments", tone: "violet" },
      { label: "Compliance regtech", tone: "amber" },
    ],
  },
];

const TONE_STYLES: Record<TagTone, { bg: string; border: string; color: string }> = {
  violet: {
    bg: "hsl(271 91% 65% / 0.12)",
    border: "hsl(271 91% 65% / 0.4)",
    color: "hsl(271 91% 78%)",
  },
  blue: {
    bg: "hsl(217 91% 60% / 0.12)",
    border: "hsl(217 91% 60% / 0.4)",
    color: "hsl(217 91% 75%)",
  },
  emerald: {
    bg: "hsl(152 76% 50% / 0.12)",
    border: "hsl(152 76% 50% / 0.4)",
    color: "hsl(152 70% 65%)",
  },
  amber: {
    bg: "hsl(43 96% 56% / 0.12)",
    border: "hsl(43 96% 56% / 0.4)",
    color: "hsl(43 96% 70%)",
  },
};

const TargetIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </svg>
);

export const TagsPanel = () => {
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
          <TargetIcon />
        </span>
        <h3 className="text-[15px] font-semibold text-foreground">
          Tags identifiés
        </h3>
      </div>

      <div className="flex flex-col gap-4">
        {GROUPS.map((group) => (
          <div key={group.title}>
            <div
              className="mb-2 text-[10.5px] font-semibold uppercase"
              style={{
                color: "hsl(var(--text-faint))",
                letterSpacing: "0.6px",
              }}
            >
              {group.title}
            </div>
            <div className="flex flex-wrap gap-2">
              {group.tags.map((tag) => {
                const s = TONE_STYLES[tag.tone];
                return (
                  <span
                    key={tag.label}
                    className="inline-flex items-center rounded-md px-2.5 py-1 text-[12.5px] font-semibold"
                    style={{
                      background: s.bg,
                      border: `1px solid ${s.border}`,
                      color: s.color,
                    }}
                  >
                    {tag.label}
                  </span>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
