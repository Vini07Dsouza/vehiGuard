import { useCallback, useEffect, useRef, useState } from 'react'

// Load data now and again every `everyMs` while the tab is visible.
// Returns { data, error, loading, reload }. `deps` re-run it (e.g. filters).
export function usePolling(fetcher, everyMs = 0, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const reload = useCallback(async () => {
    try {
      const data = await fetcherRef.current()
      setState({ data, error: null, loading: false })
    } catch (error) {
      setState((s) => ({ data: s.data, error, loading: false }))
    }
  }, [])

  useEffect(() => {
    let stopped = false
    const tick = () => {
      if (!stopped && !document.hidden) reload()
    }
    setState((s) => ({ ...s, loading: true }))
    reload()
    const timer = everyMs ? setInterval(tick, everyMs) : null
    return () => {
      stopped = true
      if (timer) clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [everyMs, reload, ...deps])

  return { ...state, reload }
}
