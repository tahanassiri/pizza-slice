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
  const cursorRef = useRef({ runId, id: lastEventId });
  const onEventRef = useRef(onEvent);
  const onConnRef = useRef(onConnectionChange);

  useEffect(() => {
    onEventRef.current = onEvent;
    onConnRef.current = onConnectionChange;
  }, [onEvent, onConnectionChange]);

  useEffect(() => {
    if (cursorRef.current.runId !== runId || !cursorRef.current.id) {
      cursorRef.current = { runId, id: lastEventId };
    }
  }, [runId, lastEventId]);

  useEffect(() => {
    if (!enabled || resolveSource() !== "live" || !runId) return;

    let closed = false;
    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    function connect() {
      if (closed) return;
      const url = eventsUrl(runId, cursorRef.current.id);
      const connection = new EventSource(url, { withCredentials: true });
      es = connection;

      connection.addEventListener("open", () => {
        if (closed || es !== connection) return;
        attempt = 0;
        onConnRef.current?.(true);
      });

      connection.addEventListener("run_event", (msg) => {
        if (closed || es !== connection) return;
        try {
          const data = JSON.parse((msg as MessageEvent).data) as RunEvent;
          if (data?.run_id !== runId || typeof data.event_id !== "string" || !data.event_id) return;
          if (data.event_id === cursorRef.current.id) return;
          cursorRef.current.id = data.event_id;
          onEventRef.current(data);
        } catch {
          // ignore malformed
        }
      });

      connection.onerror = () => {
        if (closed || es !== connection) return;
        onConnRef.current?.(false);
        connection.close();
        es = null;
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
