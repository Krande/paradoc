import React, { ReactNode } from 'react'
import { useSourceDisplayStore } from '../store/sourceDisplayStore'

interface SourceInfo {
  source_file?: string
  source_dir?: string
}

interface SourceBadgeProps {
  children: ReactNode
  sourceInfo?: SourceInfo
  blockType?: string
}

/**
 * Wrapper component that displays source file information when enabled.
 * Shows a subtle indicator and tooltip on hover.
 */
export function SourceBadge({ children, sourceInfo, blockType = 'block' }: SourceBadgeProps) {
  const { enabled } = useSourceDisplayStore()

  if (!enabled || !sourceInfo?.source_file) {
    return <>{children}</>
  }

  // Extract filename from path
  const fileName = sourceInfo.source_file.split(/[/\\]/).pop() || sourceInfo.source_file
  const displayPath = sourceInfo.source_file

  return (
    <div className="group relative">
      {children}
      {/* Source indicator - appears on hover or always when enabled */}
      <div className="absolute -left-6 top-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="w-1 h-full bg-blue-400 rounded-full" />
      </div>
      {/* Tooltip */}
      <div className="absolute left-0 top-0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 -translate-y-full -mt-2">
        <div className="bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg whitespace-nowrap">
          <div className="font-semibold mb-1">Source File</div>
          <div className="font-mono text-gray-300">{fileName}</div>
          {displayPath !== fileName && (
            <div className="font-mono text-gray-400 text-[10px] mt-1 max-w-md truncate">
              {displayPath}
            </div>
          )}
        </div>
        {/* Arrow */}
        <div className="absolute left-4 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900" />
      </div>
    </div>
  )
}

