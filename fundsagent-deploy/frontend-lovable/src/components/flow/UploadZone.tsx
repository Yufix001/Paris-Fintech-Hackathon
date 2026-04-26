import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAgent } from "@/state/AgentContext";

const ACCEPTED = ".pdf,.pptx,.key";

export const UploadZone = () => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const navigate = useNavigate();
  const { startFromFile } = useAgent();

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    // Kick off the API call (upload + SSE stream) in the background and
    // immediately navigate to the analyse step where progress is shown.
    if (file) {
      void startFromFile(file);
    }
    navigate("/analyse");
  };

  return (
    <>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        aria-describedby="upload-help"
        className="upload-zone block w-full rounded-xl px-8 py-16 text-center transition-all duration-200"
        data-dragging={isDragging || undefined}
        style={{
          borderWidth: "1.5px",
          borderStyle: isDragging ? "solid" : "dashed",
          borderColor: isDragging
            ? "hsl(var(--accent))"
            : "hsl(var(--border))",
          background: isDragging
            ? "hsl(var(--surface-elevated-2))"
            : "hsl(var(--surface-elevated))",
          fontFamily: "inherit",
          color: "inherit",
        }}
      >
        <div
          className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-xl"
          style={{ background: "hsl(292 84% 60% / 0.14)" }}
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-[26px] w-[26px]"
            fill="none"
            stroke="hsl(292 84% 60%)"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="9" y1="15" x2="15" y2="15" />
            <line x1="9" y1="11" x2="15" y2="11" />
          </svg>
        </div>

        <h3
          className="mb-2 font-sans text-[20px] font-semibold text-foreground"
          style={{ letterSpacing: "-0.3px" }}
        >
          Importez votre pitch deck
        </h3>

        <p
          id="upload-help"
          className="mx-auto mb-6 max-w-[420px] text-[14px] text-muted-foreground"
        >
          Glissez-déposez votre fichier ou cliquez pour le sélectionner.
          L'analyse démarre automatiquement.
        </p>

        <span
          role="presentation"
          className="btn-violet inline-flex items-center gap-1.5 rounded-lg px-[22px] py-[11px] text-[14px] font-semibold"
        >
          Sélectionner un fichier
        </span>

        <div
          className="mt-6 flex flex-wrap justify-center gap-4"
          aria-label="Formats acceptés"
        >
          {[".pdf", ".pptx", ".key", "≤ 50 Mo"].map((tag) => (
            <span
              key={tag}
              className="text-[12px] font-medium text-muted-foreground"
            >
              {tag}
            </span>
          ))}
        </div>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="sr-only"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </>
  );
};
