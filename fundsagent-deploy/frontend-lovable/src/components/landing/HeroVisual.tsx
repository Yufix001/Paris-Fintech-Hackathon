/**
 * 3D stack of three documents — replicates the reference HTML demo.
 * The front document shows pitch-deck KPIs.
 */
export const HeroVisual = () => {
  return (
    <div className="relative w-full" aria-hidden="true">
      {/* Trustpilot floating badge */}
      <div className="absolute left-2 top-2 z-[5] flex flex-col gap-1 sm:left-0 sm:top-4">
        <span className="text-[14px] leading-none tracking-[1px] text-success">
          ★★★★★
        </span>
        <span className="text-[13px] text-muted-foreground">
          <strong className="font-semibold text-foreground">4.9/5</strong> sur Trustpilot
        </span>
      </div>

      {/* Stage */}
      <div
        className="relative mx-auto h-[280px] w-full max-w-[720px] sm:h-[380px]"
        style={{
          perspective: "1400px",
          perspectiveOrigin: "50% 40%",
          transformStyle: "preserve-3d",
        }}
      >
        {/* Back doc */}
        <Doc
          position="back"
          style={{
            top: 0,
            left: "50%",
            transform:
              "translateX(-58%) rotateX(38deg) rotateY(-22deg) rotateZ(8deg) translateZ(-80px)",
            opacity: 0.55,
            filter: "blur(0.5px)",
          }}
        >
          <DocHeader />
          <Line w={80} />
          <Line w={60} />
          <Line w={70} />
          <Line w={50} />
        </Doc>

        {/* Mid doc */}
        <Doc
          position="mid"
          style={{
            top: "18px",
            left: "50%",
            transform:
              "translateX(-50%) rotateX(38deg) rotateY(-22deg) rotateZ(4deg) translateZ(-30px)",
            opacity: 0.85,
          }}
        >
          <DocHeader />
          <Line w={80} />
          <Line w={60} />
          <Line w={70} />
          <Line w={50} />
        </Doc>

        {/* Front doc with KPIs */}
        <div
          className="absolute overflow-hidden rounded-[14px] p-6 sm:p-[24px_26px]"
          style={{
            top: "36px",
            left: "50%",
            width: "min(380px, 90vw)",
            height: "280px",
            background: "linear-gradient(160deg, #1F2127 0%, #16181C 100%)",
            border: "1px solid rgba(168,85,247,0.18)",
            boxShadow:
              "0 30px 60px -20px rgba(0,0,0,0.7), 0 18px 36px -18px rgba(168,85,247,0.15)",
            transform:
              "translateX(-42%) rotateX(38deg) rotateY(-22deg) rotateZ(0deg)",
            transformStyle: "preserve-3d",
            animation: "doc-float 6s ease-in-out infinite",
          }}
        >
          <span
            className="mb-[14px] inline-block rounded-[4px] px-2 py-[3px] text-[10px] font-bold uppercase tracking-[1px]"
            style={{
              color: "#C084FC",
              background: "var(--accent-soft)",
              border: "1px solid var(--accent-border)",
            }}
          >
            Pitch deck
          </span>
          <div
            className="mb-4 h-[14px] w-4/5 rounded-[3px]"
            style={{
              background:
                "linear-gradient(90deg, rgba(255,255,255,0.25), rgba(255,255,255,0.10))",
            }}
          />
          <Line w={80} />
          <Line w={60} />
          <div
            className="my-[14px] grid grid-cols-2 gap-2.5 rounded-lg p-3"
            style={{
              background: "rgba(0,0,0,0.25)",
              border: "1px solid rgba(255,255,255,0.05)",
            }}
          >
            <Stat value="812" label="programmes" />
            <Stat value="5,8 M€" label="éligibles" accent />
          </div>
          <Line w={70} />
          <Line w={50} />
        </div>
      </div>
    </div>
  );
};

const Doc = ({
  children,
  style,
}: {
  children: React.ReactNode;
  position: "back" | "mid";
  style: React.CSSProperties;
}) => (
  <div
    className="absolute rounded-[14px] p-6 sm:p-[24px_26px]"
    style={{
      width: "min(380px, 90vw)",
      height: "280px",
      background: "linear-gradient(160deg, #1A1C20 0%, #131517 100%)",
      border: "1px solid rgba(255,255,255,0.06)",
      boxShadow:
        "0 30px 60px -20px rgba(0,0,0,0.7), 0 18px 36px -18px rgba(168,85,247,0.15)",
      transformStyle: "preserve-3d",
      ...style,
    }}
  >
    {children}
  </div>
);

const DocHeader = () => (
  <div
    className="mb-[14px] h-3 w-1/2 rounded-[3px]"
    style={{ background: "rgba(255,255,255,0.18)" }}
  />
);

const Line = ({ w }: { w: 50 | 60 | 70 | 80 }) => (
  <div
    className="mb-2 h-[6px] rounded-[2px]"
    style={{ width: `${w}%`, background: "rgba(255,255,255,0.08)" }}
  />
);

const Stat = ({
  value,
  label,
  accent = false,
}: {
  value: string;
  label: string;
  accent?: boolean;
}) => (
  <div className="text-left">
    <div
      className={`mb-1 font-bold leading-none ${accent ? "text-gradient-violet" : "text-foreground"}`}
      style={{ fontSize: "20px", letterSpacing: "-0.6px" }}
    >
      {value}
    </div>
    <div
      className="text-[10px] font-medium uppercase tracking-[0.4px] text-faint"
    >
      {label}
    </div>
  </div>
);
