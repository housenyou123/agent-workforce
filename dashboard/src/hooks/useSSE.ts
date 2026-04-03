import { useEffect, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://118.196.147.14/aw';

export function useSSE(onEvent: (event: { type: string; count?: number }) => void) {
  const retryRef = useRef(0);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let es: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    function connect() {
      if (disposed) return;
      es = new EventSource(`${API_BASE}/sse`);

      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          retryRef.current = 0;
          onEventRef.current(data);
        } catch { /* ignore malformed */ }
      };

      es.onerror = () => {
        es?.close();
        if (disposed) return;
        // exponential backoff: 3s, 6s, 12s, max 30s
        const delay = Math.min(3000 * Math.pow(2, retryRef.current), 30000);
        retryRef.current++;
        timer = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      disposed = true;
      es?.close();
      if (timer) clearTimeout(timer);
    };
  }, []);
}
