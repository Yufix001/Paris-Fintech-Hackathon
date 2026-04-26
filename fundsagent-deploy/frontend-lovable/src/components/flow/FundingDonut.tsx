import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

type Slice = {
  label: string;
  sub: string;
  value: number; // M€
  color: string;
  pct: number;
};

const SLICES: Slice[] = [
  { label: "Subventions EU", sub: "4 programmes", value: 1.4, color: "#4ADE80", pct: 24 },
  { label: "Aides publiques FR", sub: "CIR, JEI, Bpifrance", value: 0.7, color: "#3B82F6", pct: 12 },
  { label: "Venture Capital", sub: "8 fonds compatibles", value: 3.2, color: "#A855F7", pct: 55 },
  { label: "Prêts publics", sub: "BEI, Bpi · taux préf.", value: 0.5, color: "#FBBF24", pct: 9 },
];

const TOTAL = "5,8";
const NON_DILUTIF = "2,1";

const formatAmount = (v: number) =>
  v >= 1
    ? `${v.toFixed(1).replace(".", ",")} M€`
    : `${Math.round(v * 1000)} K€`;

export const FundingDonut = () => {
  return (
    <div
      className="rounded-[14px] p-8"
      style={{
        background: "hsl(var(--surface))",
        border: "1px solid hsl(var(--border))",
      }}
    >
      <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-[320px_1fr]">
        {/* Donut */}
        <div className="relative mx-auto h-[320px] w-[320px] [&_*]:outline-none [&_.recharts-sector]:focus:outline-none">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={SLICES}
                dataKey="value"
                nameKey="label"
                innerRadius={104}
                outerRadius={150}
                paddingAngle={1.5}
                stroke="hsl(var(--surface))"
                strokeWidth={3}
                startAngle={90}
                endAngle={-270}
                isAnimationActive
                activeShape={undefined}
                activeIndex={-1}
              >
                {SLICES.map((s) => (
                  <Cell key={s.label} fill={s.color} style={{ outline: "none" }} tabIndex={-1} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <div
              className="text-[10.5px] font-semibold uppercase"
              style={{
                color: "hsl(var(--text-faint))",
                letterSpacing: "1.4px",
              }}
            >
              Total éligible
            </div>
            <div className="mt-2 flex items-baseline">
              <span
                className="text-gradient-violet font-bold leading-none"
                style={{ fontSize: "60px", letterSpacing: "-2.5px" }}
              >
                {TOTAL}
              </span>
              <span
                className="text-gradient-violet font-bold leading-none"
                style={{ fontSize: "22px", letterSpacing: "-0.5px" }}
              >
                M€
              </span>
            </div>
            <div className="mt-2.5 text-[12px] text-muted-foreground">
              dont{" "}
              <span className="font-semibold text-foreground">
                {NON_DILUTIF} M€
              </span>{" "}
              non-dilutif
            </div>
          </div>
        </div>

        {/* Legend */}
        <ul className="flex flex-col">
          {SLICES.map((s, i) => (
            <li
              key={s.label}
              className="flex items-center gap-4 py-4"
              style={
                i < SLICES.length - 1
                  ? { borderBottom: "1px solid hsl(var(--border-soft))" }
                  : undefined
              }
            >
              <span
                aria-hidden="true"
                className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-sm"
                style={{ background: s.color }}
              />
              <div className="min-w-0 flex-1">
                <div className="text-[14px] font-semibold text-foreground">
                  {s.label}
                </div>
                <div className="mt-2 flex items-center gap-3">
                  <div
                    className="h-1 flex-1 overflow-hidden rounded-full"
                    style={{ background: "hsl(var(--surface-elevated-2))" }}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{
                        background: s.color,
                        width: `${Math.min(s.pct * 2, 100)}%`,
                      }}
                    />
                  </div>
                  <span className="text-[12px] text-muted-foreground">
                    {s.sub}
                  </span>
                </div>
              </div>
              <div className="flex items-baseline gap-2 text-right">
                <span className="text-[15px] font-bold tabular-nums text-foreground">
                  {formatAmount(s.value)}
                </span>
                <span className="text-[12px] tabular-nums text-muted-foreground">
                  {s.pct}%
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
