import React, { useEffect, useRef, useState } from 'react'
import { getPlotData } from '../sections/store'

interface PlotRendererProps {
  plotKey: string
  docId?: string
}

// plotly.js-dist-min is ~4.8 MiB raw / ~1.5 MiB gzipped. Pages without a
// plot block (the home DocList, doc bodies that are pure text/tables/3D)
// shouldn't pay that on first load. Dynamic-import the module here so
// Vite emits the pinned `plotly` chunk lazily — modulepreload only kicks
// in when this component actually mounts. Module-level cache so multiple
// PlotRenderers share one fetch.
let _plotlyPromise: Promise<any> | null = null
function loadPlotly(): Promise<any> {
  if (!_plotlyPromise) {
    _plotlyPromise = import('plotly.js-dist-min').then((m) => (m as any).default || m)
  }
  return _plotlyPromise
}

export function PlotRenderer({ plotKey, docId }: PlotRendererProps) {
  const plotRef = useRef<HTMLDivElement>(null)
  const plotlyRef = useRef<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [plotData, setPlotData] = useState<any>(null)
  const [plotly, setPlotly] = useState<any>(null)

  // Kick off the plotly fetch as soon as the component mounts; runs in
  // parallel with the IndexedDB plotData fetch.
  useEffect(() => {
    let canceled = false
    loadPlotly()
      .then((mod) => {
        if (!canceled) {
          plotlyRef.current = mod
          setPlotly(mod)
        }
      })
      .catch((err) => {
        console.error('Failed to load plotly bundle:', err)
        if (!canceled) setError('Failed to load plotting engine')
      })
    return () => {
      canceled = true
    }
  }, [])

  useEffect(() => {
    if (!docId) return

    // Load plot data from IndexedDB
    getPlotData(docId, plotKey)
      .then(data => {
        if (data) {
          setPlotData(data)
          setError(null)
        } else {
          setError(`Plot '${plotKey}' not found`)
        }
        setLoading(false)
      })
      .catch(err => {
        console.error('Error loading plot data:', err)
        setError('Failed to load plot data')
        setLoading(false)
      })
  }, [plotKey, docId])

  useEffect(() => {
    if (!plotRef.current || !plotData || !plotData.figure || !plotly) return

    try {
      const figure = plotData.figure
      const desiredWidth = plotData.width || 800
      const desiredHeight = plotData.height || 600

      // Ensure the figure has a layout object. Plotly's `responsive: true`
      // only re-flows the figure when the container resizes — it doesn't
      // help if we pin `layout.width` to the desired size, since that
      // creates a 900px-wide canvas on a 360px-wide phone. Let Plotly
      // pick the width from the container; we constrain the container's
      // CSS `max-width` separately so the plot never grows beyond the
      // author's intent on desktop.
      const layout = { ...(figure.layout || {}) }
      delete layout.width
      layout.height = desiredHeight
      layout.autosize = true

      // Add some default styling
      if (!layout.margin) {
        layout.margin = { l: 50, r: 50, t: 50, b: 50 }
      }

      const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['sendDataToCloud'],
      }

      if (plotRef.current) {
        plotRef.current.style.maxWidth = `${desiredWidth}px`
      }

      // Create the plot
      plotly.newPlot(plotRef.current, figure.data, layout, config)
        .then(() => {
          console.log('Plot rendered successfully:', plotData.key)
        })
        .catch((err: any) => {
          console.error('Plotly rendering error:', err)
          setError('Failed to render plot')
        })
    } catch (err) {
      console.error('Failed to render plot:', err)
      setError('Failed to render plot')
    }

    // Cleanup. plotlyRef survives unmount so we don't read a stale
    // closure-captured plotly that may have been collected.
    return () => {
      const p = plotlyRef.current
      if (plotRef.current && p) {
        try {
          p.purge(plotRef.current)
        } catch (err) {
          // Ignore cleanup errors
        }
      }
    }
  }, [plotData, plotly])

  if (loading) {
    return (
      <div className="my-4 p-4 border border-gray-300 dark:border-gray-700 rounded bg-gray-50 dark:bg-gray-900">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600 dark:text-gray-400">Loading plot...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="my-4 p-4 border border-red-300 rounded bg-red-50">
        <p className="text-red-600 font-semibold">Error loading plot: {plotKey}</p>
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    )
  }

  return (
    <div className="my-4 w-full overflow-x-auto">
      <div
        ref={plotRef}
        className="border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 w-full"
        // ``touchAction: pan-y`` confines the browser's default touch
        // gestures over the plot area to vertical scrolling; pinch and
        // horizontal pan are blocked at the OS / browser layer so they
        // don't double-fire viewport zoom on top of plotly's own zoom
        // handlers. Without this a two-finger pinch over a plotly chart
        // on mobile scales the entire page (browser pinch-zoom),
        // creating the "the whole site zoomed" effect. Plotly still
        // honours the modeBar's Zoom / Pan / Reset tools because those
        // use mouse / pointer events, not gesture events.
        style={{ minHeight: '320px', touchAction: 'pan-y' }}
      />
      {plotData?.caption && (
        <p className="text-sm text-gray-600 dark:text-gray-400 italic mt-2 text-center">
          {plotData.caption}
        </p>
      )}
    </div>
  )
}
