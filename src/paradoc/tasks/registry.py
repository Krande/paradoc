"""Task registry — maps qualname -> TaskFn and resolves parent references.

Two entry points:

1. The default module-level registry, populated by `@task` decoration as
   modules import. Most users never touch this directly; it's the
   destination for decoration side effects and the source for discovery.
2. Standalone `TaskRegistry()` instances for tests or multi-doc builds
   where isolation matters. The discovery loader accepts an explicit
   registry argument.

Parent references on `@task(parent=...)` accept either a callable (the
upstream task's TaskFn) or a string (the upstream task's `name`).
Resolution to a concrete TaskFn happens at `validate()` time, after
discovery has loaded every module — that way forward references inside
a single `tasks.py` work without ordering constraints.
"""

from __future__ import annotations

from typing import Optional

from .models import TaskFn


class TaskRegistry:
    """Registry of named `TaskFn` instances."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskFn] = {}

    # ---------------- registration ----------------

    def register(self, task: TaskFn) -> None:
        """Register a task. Raises on duplicate qualnames."""
        key = task.qualname
        if key in self._tasks:
            existing = self._tasks[key]
            if existing is task:
                return
            raise ValueError(
                f"Task {key!r} is already registered "
                f"(existing: {existing!r}, new: {task!r})"
            )
        self._tasks[key] = task

    def unregister(self, qualname: str) -> None:
        self._tasks.pop(qualname, None)

    def clear(self) -> None:
        self._tasks.clear()

    # ---------------- lookup ----------------

    def get(self, qualname: str) -> Optional[TaskFn]:
        return self._tasks.get(qualname)

    def known_qualnames(self) -> list[str]:
        return sorted(self._tasks)

    def all_tasks(self) -> list[TaskFn]:
        return [self._tasks[k] for k in self.known_qualnames()]

    # ---------------- validation ----------------

    def resolve_parent(self, task: TaskFn) -> Optional[TaskFn]:
        """Resolve `task.parent` (callable or string) to a concrete TaskFn.

        Returns None if the task has no parent. Raises KeyError if the
        parent is a string that doesn't match any registered task.
        """
        parent = task.parent
        if parent is None:
            return None
        if isinstance(parent, TaskFn):
            return parent
        if isinstance(parent, str):
            # Try qualname first, then bare name.
            if parent in self._tasks:
                return self._tasks[parent]
            for t in self._tasks.values():
                if t.name == parent:
                    return t
            raise KeyError(
                f"Task {task.qualname!r} declares parent={parent!r} "
                f"but no task with that name is registered. "
                f"Known: {self.known_qualnames()!r}"
            )
        # Some other callable — assume the caller knows what they're doing
        # (e.g. a directly-imported TaskFn from another module).
        return parent  # type: ignore[return-value]

    def validate(self) -> None:
        """Check structural invariants: parent refs resolve, no cycles.

        Called by the discovery loader after every task module has been
        imported. The runner (next phase) assumes a validated registry.
        """
        # Resolve all parents — KeyError on unknown strings.
        for t in self.all_tasks():
            self.resolve_parent(t)

        # Cycle detection (Kahn-style).
        deps: dict[str, set[str]] = {}
        for t in self.all_tasks():
            p = self.resolve_parent(t)
            deps[t.qualname] = {p.qualname} if isinstance(p, TaskFn) else set()

        # All names with no deps left.
        ready = [k for k, v in deps.items() if not v]
        visited = 0
        while ready:
            cur = ready.pop()
            visited += 1
            for k, v in deps.items():
                if cur in v:
                    v.remove(cur)
                    if not v:
                        ready.append(k)
        if visited != len(deps):
            unresolved = [k for k, v in deps.items() if v]
            raise ValueError(f"Task parent cycle detected involving: {unresolved!r}")


_default_registry = TaskRegistry()


def get_default_registry() -> TaskRegistry:
    """Module-level singleton populated by `@task` decoration."""
    return _default_registry


def reset_default_registry() -> None:
    """Test helper: clear the module-level registry between tests."""
    _default_registry.clear()
