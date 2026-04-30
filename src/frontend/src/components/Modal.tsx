import React from 'react'

interface ModalProps {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
}

// Lightweight modal: backdrop click and Escape close it. We don't pull
// in a focus-trap library because these modals are read-only info panels
// — keyboard users tab through the close button + content links and then
// back out via Escape. If we ever add forms inside one, revisit this.
export function Modal({ open, title, onClose, children }: ModalProps) {
  React.useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start sm:items-center justify-center bg-black/40 p-4 sm:p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="bg-white rounded-lg shadow-xl border border-gray-200 w-full max-w-md max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-800">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded p-1 text-gray-500 hover:text-gray-800 hover:bg-gray-100"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path fillRule="evenodd" clipRule="evenodd" d="M4.28 4.28a.75.75 0 011.06 0L10 8.94l4.66-4.66a.75.75 0 111.06 1.06L11.06 10l4.66 4.66a.75.75 0 11-1.06 1.06L10 11.06l-4.66 4.66a.75.75 0 11-1.06-1.06L8.94 10 4.28 5.34a.75.75 0 010-1.06z" />
            </svg>
          </button>
        </div>
        <div className="px-4 py-3 overflow-y-auto text-sm text-gray-700">{children}</div>
      </div>
    </div>
  )
}
