import React, { useEffect, useRef, useState } from 'react'
import { getPlotData } from '../sections/store'
import Plotly from 'plotly.js-dist-min'

interface PlotRendererProps {
  plotKey: string
  docId?: string
}

export function PlotRenderer({ plotKey, docId }: PlotRendererProps) {
  const plotRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [plotData, setPlotData] = useState<any>(null)

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
    if (!plotRef.current || !plotData || !plotData.figure) return

    // Render the plot using statically imported Plotly
    try {
      const figure = plotData.figure
      const width = plotData.width || 800
      const height = plotData.height || 600

      // Ensure the figure has a layout object
      const layout = { ...(figure.layout || {}) }
      layout.width = width
      layout.height = height
      layout.autosize = false

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

      // Create the plot
      Plotly.newPlot(plotRef.current, figure.data, layout, config)
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

    // Cleanup
    return () => {
      if (plotRef.current && Plotly) {
        try {
          Plotly.purge(plotRef.current)
        } catch (err) {
          // Ignore cleanup errors
        }
      }
    }
  }, [plotData])

  if (loading) {
    return (
      <div className="my-4 p-4 border border-gray-300 rounded bg-gray-50">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Loading plot...</span>
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
    <div className="my-4">
      <div
        ref={plotRef}
        className="border border-gray-300 rounded bg-white"
        style={{ minHeight: '400px' }}
      />
      {plotData?.caption && (
        <p className="text-sm text-gray-600 italic mt-2 text-center">
          {plotData.caption}
        </p>
      )}
    </div>
  )
}
