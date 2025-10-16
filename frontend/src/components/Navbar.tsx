import React from 'react'

export type TocItem = {
  id: string
  text: string
  level: number // 0-based: h1 -> 0
}

export function Navbar({ toc }: { toc: TocItem[] }) {
  return (
    <aside className="hidden md:flex md:flex-col w-72 shrink-0 border-r border-gray-200 bg-white/60 backdrop-blur sticky top-0 h-screen overflow-auto">
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Contents</div>
      </div>
      <nav className="p-2">
        <ul className="space-y-1">
          {toc.map((item) => (
            <li key={item.id}>
              <a
                className="cursor-pointer block text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded px-2 py-1"
                style={{ paddingLeft: `${item.level * 16 + 8}px` }}
                href={`#${item.id}`}
                onClick={(e) => {
                  e.preventDefault()
                  const el = document.getElementById(item.id)
                  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
                }}
              >
                {item.text}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
