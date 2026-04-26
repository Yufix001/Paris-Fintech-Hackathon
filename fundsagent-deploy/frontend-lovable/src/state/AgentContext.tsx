import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  streamAgent,
  uploadDeck,
  vcToProgram,
  type AgentEvent,
  type MatchedProgram,
  type MatchedVc,
  type ProgramRow,
} from "@/lib/api";
import { PROGRAMS as MOCK_PROGRAMS } from "@/components/flow/ProgramsTable";

type Status = "idle" | "uploading" | "streaming" | "done" | "error";

type AgentState = {
  status: Status;
  error: string | null;
  fileName: string | null;
  pitchText: string | null;
  programs: ProgramRow[];
  vcs: MatchedVc[];
  events: AgentEvent[];
  /** True if we have received any real data from the API. */
  hasLiveData: boolean;
  /** Programs to render: live data when available, mock fallback otherwise. */
  displayedPrograms: ProgramRow[];
};

type AgentContextValue = AgentState & {
  startFromFile: (file: File) => Promise<void>;
  startFromText: (text: string) => Promise<void>;
  reset: () => void;
};

const AgentContext = createContext<AgentContextValue | null>(null);

const initialState: Omit<AgentState, "displayedPrograms" | "hasLiveData"> = {
  status: "idle",
  error: null,
  fileName: null,
  pitchText: null,
  programs: [],
  vcs: [],
  events: [],
};

const normaliseMatchedProgram = (p: MatchedProgram): ProgramRow => ({
  name: p.name,
  org: p.org ?? "",
  amount: p.amount ?? "—",
  amountSub: p.amountSub,
  match: typeof p.match === "number" ? p.match : 0,
  delay: p.delay ?? "—",
  category: p.category ?? "subvention",
  kind: "Non-dilutif",
});

export const AgentProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<typeof initialState>(initialState);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(initialState);
  }, []);

  const runStream = useCallback(async (pitchText: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState((s) => ({
      ...s,
      status: "streaming",
      error: null,
      pitchText,
      programs: [],
      vcs: [],
      events: [],
    }));

    try {
      await streamAgent({
        pitchdeck_text: pitchText,
        want_draft: true,
        signal: controller.signal,
        onEvent: (evt) => {
          setState((s) => {
            const next = { ...s, events: [...s.events, evt] };

            if (evt.type === "matched") {
              const payload = evt.payload as { programs?: MatchedProgram[] };
              const incoming = (payload?.programs ?? []).map(
                normaliseMatchedProgram,
              );
              next.programs = [
                // Preserve any VC rows already received, then refresh
                // the non-VC programs from the matched event.
                ...incoming,
                ...s.programs.filter((p) => p.category === "vc"),
              ];
            }

            if (evt.type === "matched_vcs") {
              const payload = evt.payload as { vcs?: MatchedVc[] };
              const vcs = payload?.vcs ?? [];
              const vcRows = vcs.map(vcToProgram);
              next.vcs = vcs;
              next.programs = [
                ...s.programs.filter((p) => p.category !== "vc"),
                ...vcRows,
              ];
            }

            return next;
          });
        },
      });

      setState((s) => ({ ...s, status: "done" }));
    } catch (err) {
      if (controller.signal.aborted) return;
      const message = err instanceof Error ? err.message : "Stream failed";
      // eslint-disable-next-line no-console
      console.error("[agent] stream error", err);
      setState((s) => ({ ...s, status: "error", error: message }));
    }
  }, []);

  const startFromText = useCallback(
    async (text: string) => {
      await runStream(text);
    },
    [runStream],
  );

  const startFromFile = useCallback(
    async (file: File) => {
      abortRef.current?.abort();
      setState((s) => ({
        ...s,
        status: "uploading",
        error: null,
        fileName: file.name,
        programs: [],
        vcs: [],
        events: [],
      }));
      try {
        const { text } = await uploadDeck(file);
        setState((s) => ({ ...s, pitchText: text }));
        await runStream(text);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
        // eslint-disable-next-line no-console
        console.error("[agent] upload error", err);
        setState((s) => ({ ...s, status: "error", error: message }));
      }
    },
    [runStream],
  );

  const value = useMemo<AgentContextValue>(() => {
    const hasLiveData = state.programs.length > 0;
    const displayedPrograms: ProgramRow[] = hasLiveData
      ? state.programs
      : (MOCK_PROGRAMS as ProgramRow[]).map((p) => ({
        ...p,
        kind: p.category === "vc" ? "Dilutif" : "Non-dilutif",
      }));

    return {
      ...state,
      hasLiveData,
      displayedPrograms,
      startFromFile,
      startFromText,
      reset,
    };
  }, [state, startFromFile, startFromText, reset]);

  return (
    <AgentContext.Provider value={value}>{children}</AgentContext.Provider>
  );
};

export const useAgent = () => {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error("useAgent must be used inside <AgentProvider>");
  return ctx;
};
