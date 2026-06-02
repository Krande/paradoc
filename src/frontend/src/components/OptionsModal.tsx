import React from 'react'
import { Modal } from './Modal'
import { useTheme, type Theme } from '../store/themeStore'
import { useViewerControlsStore } from '../store/viewerControlsStore'

interface OptionsModalProps {
  open: boolean
  onClose: () => void
}

// Preferences panel reached via the cog dropdown's "Options" item.
// Groups the user-tunable display + viewer settings into one place so
// the main dropdown can stay focused on actions (About / User info /
// Bundle files / Admin / Clear cache). The Theme picker is also
// surfaced inline in the desktop topbar, but we still show it here for
// users (especially on mobile) who reach for the cog when they want to
// change anything.
export function OptionsModal({ open, onClose }: OptionsModalProps) {
  const [theme, setTheme] = useTheme()
  const { enabled: viewerControlsEnabled, toggleEnabled: toggleViewerControls } =
    useViewerControlsStore()

  return (
    <Modal open={open} title="Options" onClose={onClose}>
      <div className="space-y-4">
        <Row label="Theme">
          <ThemePill theme={theme} setTheme={setTheme} />
        </Row>

        <Row
          label="3D viewer controls"
          title="Show adapy's native viewer controls (top navbar, selection tree, object/group info)"
        >
          <Toggle on={viewerControlsEnabled} onClick={toggleViewerControls} />
        </Row>
      </div>
    </Modal>
  )
}

function Row({
  label,
  title,
  children,
}: {
  label: string
  title?: string
  children: React.ReactNode
}) {
  return (
    <div
      className="flex items-center justify-between gap-3"
      title={title}
    >
      <span className="text-sm text-gray-800 dark:text-gray-200">{label}</span>
      {children}
    </div>
  )
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className={
        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition ' +
        (on ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-700')
      }
    >
      <span
        className={
          'inline-block h-5 w-5 transform rounded-full bg-white shadow transition ' +
          (on ? 'translate-x-5' : 'translate-x-0')
        }
      />
    </button>
  )
}

const THEME_OPTIONS: { value: Theme; label: string; icon: React.ReactNode }[] = [
  {
    value: 'light',
    label: 'Light',
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      </svg>
    ),
  },
  {
    value: 'system',
    label: 'System',
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="13" rx="2" />
        <path d="M8 21h8M12 17v4" />
      </svg>
    ),
  },
  {
    value: 'dark',
    label: 'Dark',
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
      </svg>
    ),
  },
]

function ThemePill({
  theme,
  setTheme,
}: {
  theme: Theme
  setTheme: (t: Theme) => void
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="inline-flex items-center rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-0.5"
    >
      {THEME_OPTIONS.map((opt) => {
        const active = theme === opt.value
        return (
          <button
            key={opt.value}
            role="radio"
            aria-checked={active}
            title={opt.label}
            onClick={() => setTheme(opt.value)}
            className={
              'inline-flex items-center justify-center w-7 h-7 rounded transition cursor-pointer ' +
              (active
                ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
                : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100')
            }
          >
            {opt.icon}
          </button>
        )
      })}
    </div>
  )
}
