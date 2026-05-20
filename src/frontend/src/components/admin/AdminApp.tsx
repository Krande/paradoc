import React from 'react'
import { Link } from 'react-router-dom'
import {
  adminApi,
  AdminApiError,
  AdminMember,
  AdminProject,
  AdminUser,
} from '../../api/admin'

// Admin panel — project CRUD + member management + shelf_base_url
// paste. Single-column layout for v0; polish (two-pane / mobile)
// follows adapy's ProjectsTab pattern when needed.
//
// Backend-gated: every request requires the user to be in the
// PARADOC_AUTH_ADMIN_GROUP. The UI just renders the error if the
// request fails (401 / 403 / 503).

export default function AdminApp() {
  const [projects, setProjects] = React.useState<AdminProject[]>([])
  const [selected, setSelected] = React.useState<AdminProject | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  const reload = React.useCallback(async () => {
    setLoading(true)
    try {
      const { projects: xs } = await adminApi.listProjects()
      setProjects(xs)
      // Keep selection if the project still exists; otherwise drop it.
      setSelected((cur) => (cur ? xs.find((p) => p.id === cur.id) ?? null : null))
      setError(null)
    } catch (e) {
      setError(formatErr(e))
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void reload()
  }, [reload])

  const onCreate = async (slug: string, name: string) => {
    setError(null)
    try {
      const p = await adminApi.createProject(slug, name)
      await reload()
      setSelected(p)
    } catch (e) {
      setError(formatErr(e))
    }
  }

  const onArchive = async (p: AdminProject) => {
    if (!confirm(`Archive "${p.name}"? Members will lose access.`)) return
    try {
      await adminApi.archiveProject(p.id)
      await reload()
    } catch (e) {
      setError(formatErr(e))
    }
  }

  const onShelfUrlChange = async (p: AdminProject, value: string) => {
    const trimmed = value.trim()
    try {
      const updated = await adminApi.updateProject(p.id, {
        shelf_base_url: trimmed || null,
      })
      setProjects((xs) => xs.map((x) => (x.id === updated.id ? { ...x, ...updated } : x)))
      setSelected((cur) => (cur && cur.id === updated.id ? { ...cur, ...updated } : cur))
    } catch (e) {
      setError(formatErr(e))
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div>
          <h1 className="text-lg font-semibold text-gray-800">Paradoc admin</h1>
          <p className="text-xs text-gray-500">
            Projects, members, and shelf-link configuration.
          </p>
        </div>
        <Link
          to="/"
          className="text-sm text-blue-700 hover:text-blue-900 hover:underline"
        >
          ← Back to docs
        </Link>
      </header>

      <main className="max-w-5xl mx-auto p-4 space-y-6">
        <CreateProjectForm onCreate={onCreate} />

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2 text-sm rounded">
            {error}
          </div>
        )}

        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-2 flex items-center justify-between">
            <span>Projects {loading && <span className="text-xs text-gray-400">…</span>}</span>
            <span className="text-xs text-gray-400 font-normal">
              {projects.length} total
            </span>
          </h2>
          {projects.length === 0 && !loading && (
            <div className="text-sm text-gray-500 italic px-3 py-6 bg-white border border-gray-200 rounded">
              No projects yet.
            </div>
          )}
          <ul className="space-y-1">
            {projects.map((p) => (
              <li key={p.id}>
                <button
                  className={`w-full text-left px-3 py-2 rounded border ${
                    selected?.id === p.id
                      ? 'bg-blue-50 border-blue-300'
                      : 'bg-white border-gray-200 hover:bg-gray-100'
                  }`}
                  onClick={() => setSelected(selected?.id === p.id ? null : p)}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm text-gray-800 truncate">
                      {p.name}
                    </span>
                    {p.archived_at && (
                      <span className="text-[10px] uppercase text-gray-500">archived</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {p.slug} · {p.member_count} member{p.member_count === 1 ? '' : 's'}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {selected && (
          <ProjectDetail
            project={selected}
            onArchive={() => onArchive(selected)}
            onShelfUrlChange={(v) => onShelfUrlChange(selected, v)}
          />
        )}
      </main>
    </div>
  )
}

function CreateProjectForm({
  onCreate,
}: {
  onCreate: (slug: string, name: string) => void
}) {
  const [name, setName] = React.useState('')
  const [slug, setSlug] = React.useState('')
  const [touchedSlug, setTouchedSlug] = React.useState(false)
  const effectiveSlug = touchedSlug ? slug : autoSlug(name)

  return (
    <form
      className="bg-white border border-gray-200 rounded p-4 space-y-3"
      onSubmit={(e) => {
        e.preventDefault()
        if (!name.trim() || !effectiveSlug) return
        onCreate(effectiveSlug, name.trim())
        setName('')
        setSlug('')
        setTouchedSlug(false)
      }}
    >
      <div className="text-sm font-semibold text-gray-700">Create project</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <input
          className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          placeholder="Project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="border border-gray-300 rounded px-2 py-1.5 text-sm font-mono"
          placeholder="slug"
          value={effectiveSlug}
          onChange={(e) => {
            setTouchedSlug(true)
            setSlug(e.target.value)
          }}
        />
      </div>
      <button
        type="submit"
        className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 text-sm rounded disabled:opacity-50"
        disabled={!name.trim() || !effectiveSlug}
      >
        Create
      </button>
    </form>
  )
}

function ProjectDetail({
  project,
  onArchive,
  onShelfUrlChange,
}: {
  project: AdminProject
  onArchive: () => void
  onShelfUrlChange: (value: string) => void
}) {
  return (
    <section className="bg-white border border-gray-200 rounded p-4 space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-gray-800 truncate">
            {project.name}
          </h3>
          <div className="text-xs text-gray-500 font-mono break-all">
            {project.slug} · {project.id}
          </div>
        </div>
        {!project.archived_at && (
          <button
            className="text-xs text-red-700 hover:text-red-900 px-2 py-1 border border-red-200 rounded"
            onClick={onArchive}
          >
            Archive
          </button>
        )}
      </div>

      <ShelfUrlEditor
        initial={project.shelf_base_url || ''}
        disabled={!!project.archived_at}
        onSave={onShelfUrlChange}
      />

      <MembersPane project={project} />
    </section>
  )
}

function ShelfUrlEditor({
  initial,
  disabled,
  onSave,
}: {
  initial: string
  disabled: boolean
  onSave: (value: string) => void
}) {
  const [value, setValue] = React.useState(initial)
  const [dirty, setDirty] = React.useState(false)

  React.useEffect(() => {
    setValue(initial)
    setDirty(false)
  }, [initial])

  return (
    <div>
      <label className="block text-xs uppercase tracking-wide text-gray-500 mb-1">
        Shelf base URL
      </label>
      <div className="flex gap-2">
        <input
          type="text"
          className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm font-mono"
          placeholder="https://shelf.example.com"
          value={value}
          disabled={disabled}
          onChange={(e) => {
            setValue(e.target.value)
            setDirty(e.target.value !== initial)
          }}
        />
        <button
          className="bg-gray-700 hover:bg-gray-800 text-white px-3 py-1.5 text-sm rounded disabled:opacity-50"
          disabled={disabled || !dirty}
          onClick={() => onSave(value)}
        >
          Save
        </button>
      </div>
      <p className="text-xs text-gray-500 mt-1">
        Paste the shelf instance's base URL (no validation, just stored).
        Used by citation deep-links in this project's bundles.
      </p>
    </div>
  )
}

function MembersPane({ project }: { project: AdminProject }) {
  const [members, setMembers] = React.useState<AdminMember[]>([])
  const [users, setUsers] = React.useState<AdminUser[]>([])
  const [pickedUserId, setPickedUserId] = React.useState('')
  const [role, setRole] = React.useState('member')
  const [error, setError] = React.useState<string | null>(null)

  const reload = React.useCallback(async () => {
    try {
      const [{ members: m }, { users: u }] = await Promise.all([
        adminApi.listMembers(project.id),
        adminApi.listUsers(),
      ])
      setMembers(m)
      setUsers(u)
      setError(null)
    } catch (e) {
      setError(formatErr(e))
    }
  }, [project.id])

  React.useEffect(() => {
    void reload()
  }, [reload])

  const memberIds = new Set(members.map((m) => m.user_id))
  const candidates = users.filter((u) => !memberIds.has(u.id))

  const onAdd = async () => {
    if (!pickedUserId) return
    try {
      await adminApi.addMember(project.id, pickedUserId, role || 'member')
      setPickedUserId('')
      await reload()
    } catch (e) {
      setError(formatErr(e))
    }
  }

  const onRemove = async (m: AdminMember) => {
    const label = m.display_name || m.email || m.user_id
    if (!confirm(`Remove ${label} from "${project.name}"?`)) return
    try {
      await adminApi.removeMember(project.id, m.user_id)
      await reload()
    } catch (e) {
      setError(formatErr(e))
    }
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <h4 className="text-xs uppercase tracking-wide text-gray-500">Members</h4>
        <span className="text-xs text-gray-400">{members.length}</span>
      </div>
      {error && (
        <div className="text-xs text-red-700 mb-2">{error}</div>
      )}
      {!project.archived_at && (
        <div className="flex gap-2 mb-2">
          <select
            className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm"
            value={pickedUserId}
            onChange={(e) => setPickedUserId(e.target.value)}
          >
            <option value="">— pick a user —</option>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name || u.email || u.oidc_sub}
              </option>
            ))}
          </select>
          <select
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="member">member</option>
            <option value="owner">owner</option>
          </select>
          <button
            className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 text-sm rounded disabled:opacity-50"
            disabled={!pickedUserId}
            onClick={onAdd}
          >
            Add
          </button>
        </div>
      )}
      {members.length === 0 ? (
        <div className="text-sm text-gray-500 italic px-3 py-4 bg-gray-50 border border-gray-200 rounded">
          No members yet. Users must sign in once before they can be added.
        </div>
      ) : (
        <ul className="divide-y divide-gray-200 border border-gray-200 rounded">
          {members.map((m) => (
            <li key={m.user_id} className="flex items-center justify-between px-3 py-2">
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-800 truncate">
                  {m.display_name || m.email || m.oidc_sub}
                </div>
                <div className="text-xs text-gray-500 truncate font-mono">
                  {m.role} · {m.oidc_iss}
                </div>
              </div>
              {!project.archived_at && (
                <button
                  className="text-xs text-red-700 hover:text-red-900 px-2 py-1"
                  onClick={() => onRemove(m)}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function formatErr(e: unknown): string {
  if (e instanceof AdminApiError) return e.detail || `HTTP ${e.status}`
  if (e instanceof Error) return e.message
  return String(e)
}

function autoSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 63)
}
