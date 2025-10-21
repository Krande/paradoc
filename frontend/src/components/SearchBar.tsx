import React, { useEffect, useState, useCallback, useRef } from 'react'

interface SearchBarProps {
  isOpen: boolean
  onClose: () => void
}

export function SearchBar({ isOpen, onClose }: SearchBarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [totalResults, setTotalResults] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const searchTimeoutRef = useRef<number | null>(null)

  // Clear all highlights
  const clearHighlights = useCallback(() => {
    const highlighted = document.querySelectorAll('.paradoc-search-highlight')
    highlighted.forEach(el => {
      const parent = el.parentNode
      if (parent) {
        parent.replaceChild(document.createTextNode(el.textContent || ''), el)
        parent.normalize()
      }
    })
  }, [])

  // Highlight search results in the document
  const highlightSearchResults = useCallback((query: string) => {
    clearHighlights()

    if (!query.trim()) {
      setTotalResults(0)
      setCurrentIndex(0)
      return
    }

    const content = document.querySelector('[data-search-root]')
    if (!content) return

    const walker = document.createTreeWalker(
      content,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: (node) => {
          // Skip script, style, and already highlighted nodes
          const parent = node.parentElement
          if (!parent) return NodeFilter.FILTER_REJECT
          const tag = parent.tagName.toLowerCase()
          if (['script', 'style', 'noscript'].includes(tag)) return NodeFilter.FILTER_REJECT
          if (parent.classList.contains('paradoc-search-highlight')) return NodeFilter.FILTER_REJECT
          if (parent.closest('input, textarea, select')) return NodeFilter.FILTER_REJECT
          return NodeFilter.FILTER_ACCEPT
        }
      }
    )

    const nodes: Text[] = []
    let node: Node | null
    while ((node = walker.nextNode())) {
      nodes.push(node as Text)
    }

    const regex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    let matchCount = 0

    nodes.forEach(textNode => {
      const text = textNode.textContent || ''
      const matches = Array.from(text.matchAll(regex))

      if (matches.length > 0) {
        const fragment = document.createDocumentFragment()
        let lastIndex = 0

        matches.forEach(match => {
          const matchIndex = match.index!

          // Add text before match
          if (matchIndex > lastIndex) {
            fragment.appendChild(document.createTextNode(text.slice(lastIndex, matchIndex)))
          }

          // Add highlighted match
          const span = document.createElement('span')
          span.className = 'paradoc-search-highlight'
          span.setAttribute('data-match-index', String(matchCount))
          span.textContent = match[0]
          fragment.appendChild(span)

          matchCount++
          lastIndex = matchIndex + match[0].length
        })

        // Add remaining text
        if (lastIndex < text.length) {
          fragment.appendChild(document.createTextNode(text.slice(lastIndex)))
        }

        textNode.parentNode?.replaceChild(fragment, textNode)
      }
    })

    setTotalResults(matchCount)
    if (matchCount > 0) {
      setCurrentIndex(0)
      scrollToMatch(0)
    } else {
      setCurrentIndex(0)
    }
  }, [clearHighlights])

  // Scroll to a specific match
  const scrollToMatch = useCallback((index: number) => {
    const matches = document.querySelectorAll('.paradoc-search-highlight')
    if (matches.length === 0) return

    // Remove current highlight
    matches.forEach(el => el.classList.remove('paradoc-search-current'))

    // Add current highlight to target
    const target = matches[index]
    if (target) {
      target.classList.add('paradoc-search-current')
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [])

  // Navigate to next result
  const goToNext = useCallback(() => {
    if (totalResults === 0) return
    const next = (currentIndex + 1) % totalResults
    setCurrentIndex(next)
    scrollToMatch(next)
  }, [currentIndex, totalResults, scrollToMatch])

  // Navigate to previous result
  const goToPrevious = useCallback(() => {
    if (totalResults === 0) return
    const prev = (currentIndex - 1 + totalResults) % totalResults
    setCurrentIndex(prev)
    scrollToMatch(prev)
  }, [currentIndex, totalResults, scrollToMatch])

  // Handle search input change
  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value)

    // Debounce search
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    searchTimeoutRef.current = setTimeout(() => {
      highlightSearchResults(value)
    }, 300)
  }, [highlightSearchResults])

  // Focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isOpen])

  // Cleanup on close
  useEffect(() => {
    if (!isOpen) {
      clearHighlights()
      setSearchQuery('')
      setCurrentIndex(0)
      setTotalResults(0)
    }
  }, [isOpen, clearHighlights])

  // Handle keyboard shortcuts within search bar
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) {
        goToPrevious()
      } else {
        goToNext()
      }
    }
  }, [onClose, goToNext, goToPrevious])

  if (!isOpen) return null

  return (
    <>
      <style>{`
        .paradoc-search-highlight {
          background-color: #fef08a;
          color: #000;
          padding: 2px 0;
        }
        .paradoc-search-current {
          background-color: #fbbf24;
          color: #000;
          font-weight: 600;
        }
      `}</style>
      <div className="fixed top-4 right-4 z-50 bg-white border border-gray-300 rounded-lg shadow-lg p-3 min-w-[320px]">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search in document..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          />
          <div className="flex items-center gap-1">
            <button
              onClick={goToPrevious}
              disabled={totalResults === 0}
              className="p-2 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              title="Previous (Shift+Enter)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            </button>
            <button
              onClick={goToNext}
              disabled={totalResults === 0}
              className="p-2 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              title="Next (Enter)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded cursor-pointer"
              title="Close (Esc)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        {searchQuery && (
          <div className="mt-2 text-xs text-gray-600">
            {totalResults > 0 ? (
              <span>
                Result {currentIndex + 1} of {totalResults}
              </span>
            ) : (
              <span>No results found</span>
            )}
          </div>
        )}
      </div>
    </>
  )
}

