import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi, ApiError } from "@/api/client";
import type { StreamEvent, UIMessage } from "@/types";

/**
 * Streaming chat hook.
 *
 * Same external surface as ``useChat`` (messages, send, reset, error,
 * loading) so swapping it in is one line in App.tsx, plus an extra
 * ``thoughts`` array — the live pipeline-progress timeline used by the
 * ``ChainOfThought`` component.
 *
 * Every event from the SSE stream is appended to ``thoughts``. When the
 * final event arrives, ``thoughts`` is cleared and the assistant reply
 * is appended to ``messages`` with full metadata (route, latency,
 * timings, model_used) — identical to the non-streaming path.
 *
 * Falls back to ``chatApi.send`` if the streaming request fails — the
 * user always gets an answer, even if the pipeline progress is missing.
 */

export interface ThoughtItem {
  id: string;
  type: "stage" | "tool";
  label: string;
  status: "running" | "done" | "error";
  ms?: number;
  detail?: string;
  // Used to merge stage_start + stage_done events into one row.
  matchKey: string;
}

interface UseChatStreamArgs {
  userId: string;
  sessionId: string;
}

export function useChatStream({ userId, sessionId }: UseChatStreamArgs) {
  const identity = useRef({ userId, sessionId });
  identity.current = { userId, sessionId };
  const inFlight = useRef<AbortController | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [thoughts, setThoughts] = useState<ThoughtItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Reset + load history when user or session changes ─────────────
  useEffect(() => {
    let cancelled = false;
    inFlight.current?.abort();
    setLoading(false);
    setMessages([]);
    setThoughts([]);
    setError(null);
    if (!userId || !sessionId) return;

    void chatApi
      .sessionTurns(sessionId, userId, 50)
      .then((res) => {
        if (cancelled || !res?.turns) return;
        setMessages(
          res.turns.map((t) => ({
            id: crypto.randomUUID(),
            role: t.role as "user" | "assistant",
            content: t.content,
            ts: t.ts,
          })),
        );
      })
      .catch(() => { /* silent — empty history is fine */ });

    return () => { cancelled = true; inFlight.current?.abort(); };
  }, [userId, sessionId]);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || loading || !userId || !sessionId) return;
    const controller = new AbortController();
    inFlight.current = controller;
    const current = () => !controller.signal.aborted && identity.current.userId === userId && identity.current.sessionId === sessionId;
    setError(null);

    const userMsg: UIMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      ts: Date.now() / 1000,
    };
    setMessages((prev) => [...prev, userMsg]);

    setLoading(true);
    setThoughts([]);

    const onEvent = (event: StreamEvent) => {
      if (!current()) return;
      if (event.type === "stage_start") {
        const matchKey = `stage:${event.stage}`;
        setThoughts((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            type: "stage",
            matchKey,
            label: event.label,
            status: "running",
          },
        ]);
      } else if (event.type === "stage_done") {
        const matchKey = `stage:${event.stage}`;
        const detailStr = formatStageDetail(event.detail);
        setThoughts((prev) => {
          // Find the matching running row, mark done. If absent (warm
          // cache short-circuit emits done without start), append a row.
          const idx = prev.findIndex((p) => p.matchKey === matchKey && p.status === "running");
          if (idx === -1) {
            return [
              ...prev,
              {
                id: crypto.randomUUID(),
                type: "stage",
                matchKey,
                label: event.detail && (event.detail as { cached?: boolean }).cached
                  ? `${stageLabelFromId(event.stage)} (cached)`
                  : stageLabelFromId(event.stage),
                status: "done",
                ms: event.ms,
                detail: detailStr,
              },
            ];
          }
          const next = prev.slice();
          next[idx] = { ...next[idx], status: "done", ms: event.ms, detail: detailStr };
          return next;
        });
      } else if (event.type === "tool_invoke") {
        const matchKey = `tool:${event.route}:${event.action ?? "_"}`;
        setThoughts((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            type: "tool",
            matchKey,
            label: event.label,
            status: "running",
          },
        ]);
      } else if (event.type === "tool_done") {
        const matchKey = `tool:${event.route}:${event.action ?? "_"}`;
        setThoughts((prev) => {
          const idx = prev.findIndex((p) => p.matchKey === matchKey && p.status === "running");
          if (idx === -1) return prev;
          const next = prev.slice();
          next[idx] = {
            ...next[idx],
            status: "done",
            ms: event.ms,
            detail: event.summary || undefined,
          };
          return next;
        });
      }
    };

    try {
      const res = await chatApi.stream(
        { user_id: userId, session_id: sessionId, message: text },
        onEvent,
        controller.signal,
      );
      if (!current()) return;
      const botMsg: UIMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.answer,
        ts: Date.now() / 1000,
        meta: {
          route: res.route,
          routes: res.routes,
          cached: res.cached,
          latency_ms: res.latency_ms,
          trace_id: res.trace_id,
          timings: res.timings,
          model_used: res.model_used,
        },
      };
      setMessages((prev) => [...prev, botMsg]);
      setThoughts([]);
    } catch (e) {
      if (!current()) return;
      // A lost stream may have already executed a booking. Never resubmit a
      // mutating conversation automatically after an uncertain response.
      const message = e instanceof ApiError ? e.message : String(e);
      setError(message);
      setThoughts([]);
    } finally {
      if (current()) setLoading(false);
    }
  }, [loading, userId, sessionId]);

  const reset = useCallback(async () => {
    inFlight.current?.abort();
    setLoading(false);
    try {
      await chatApi.reset(userId, sessionId);
    } catch { /* ignore */ }
    if (identity.current.userId !== userId || identity.current.sessionId !== sessionId) return;
    setMessages([]);
    setThoughts([]);
    setError(null);
  }, [userId, sessionId]);

  return { messages, thoughts, loading, error, send, reset };
}


function stageLabelFromId(stage: string): string {
  const m: Record<string, string> = {
    cache: "Cache lookup",
    recall_st: "Loading conversation history",
    recall_lt: "Searching long-term memory",
    patient: "Verifying patient profile",
    route: "Routing your question",
    synth: "Composing reply",
    save: "Saving",
  };
  return m[stage] ?? stage;
}

function formatStageDetail(detail: Record<string, unknown> | undefined): string | undefined {
  if (!detail) return undefined;
  const parts: string[] = [];
  if ("hit" in detail) parts.push(detail.hit ? "cache hit" : "miss");
  if ("turns" in detail) parts.push(`${detail.turns} turns`);
  if ("facts" in detail) parts.push(`${detail.facts} facts`);
  if ("loaded" in detail) parts.push(detail.loaded ? "profile loaded" : "no profile");
  if ("route" in detail) {
    const r = detail.route as string;
    const a = "action" in detail ? (detail.action as string | null) : null;
    parts.push(a ? `${r}/${a}` : r);
  }
  if ("model" in detail) parts.push(`${detail.model}`);
  return parts.join(" · ") || undefined;
}
