// Inline favicon glyph: same paths as public/favicon.svg, rendered inline so
// it inherits `currentColor` and adapts to dark mode.
export function BrandMark({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M3 3 H21 V21 H3 Z M6 6 H18 V18 H6 Z M7 17 L7 13 L10 13 L10 11 L13 11 L13 8 L17 8 L17 17 Z"
      />
    </svg>
  )
}
