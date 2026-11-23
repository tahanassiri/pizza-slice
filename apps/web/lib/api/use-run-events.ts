"use client";

import { useEffect, useRef } from "react";
import type { RunEvent } from "@/types";
import { resolveSource } from "./client";
import { eventsUrl } from "./live-adapter";

/**
 * Subscribe to live SSE for a run. Heartbeats are ignored (not progress).
 * On disconnect, reconnects with Last-Event-ID / last_event_id resume.
 */
export function useRunEvents(
  runId: string,
  opts: {
    enabled?: boolean;
    lastEventId?: string | null;
    onEvent: (event: RunEvent) => void;
    onConnectionChange?: (connected: boolean) => void;
  }
) {
  const { enabled = true, lastEventId, onEvent, onConnectionChange } = opts;
  const lastIdRef = useRef<string | null | undefined>(lastEventId);
  const onEventRef = useRef(onEvent);
  const onConnRef = useRef(onConnectionChange);

  useEffect(() => {
    onEventRef.current = onEvent;
    onConnRef.current = onConnectionChange;
  }, [onEvent, onConnectionChange]);

  useEffect(() => {
    lastIdRef.current = lastEventId;
  }, [lastEventId]);

  useEffect(() => {
    if (!enabled || resolveSource() !== "live" || !runId) return;

    let closed = false;
    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    function connect() {
      if (closed) return;
      const url = eventsUrl(runId, lastIdRef.current);
      es = new EventSource(url);

      es.addEventListener("open", () => {
        attempt = 0;
        onConnRef.current?.(true);
      });

      es.addEventListener("run_event", (msg) => {
        try {
          const data = JSON.parse((msg as MessageEvent).data) as RunEvent;
          if (data.event_id) lastIdRef.current = data.event_id;
          onEventRef.current(data);
        } catch {
          // ignore malformed
        }
      });

      // Heartbeat: keep-alive only — do not treat as progress
      es.addEventListener("heartbeat", () => {
        onConnRef.current?.(true);
      });

      es.onerror = () => {
        onConnRef.current?.(false);
        es?.close();
        es = null;
        if (closed) return;
        const delay = Math.min(8000, 500 * 2 ** attempt);
        attempt += 1;
        retryTimer = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      es?.close();
    };
  }, [runId, enabled]);
}
