"""Task primitives — placeholder for Phase 9 (real runner).

The plan calls out a follow-up PR to integrate pixi-tasks (or a similar
input/output-hashing runner). This module ships the *type surface* for
that work so other code (Filter.task, FEAModelResults.task_id) can
reference it today without binding to an implementation.

The Task object today is purely declarative: declaring `inputs`,
`outputs`, `env_lock`, and `solver_version` is enough to plan the cache
key. The runner that actually executes tasks lives in a follow-up PR.
"""

from .models import Task

__all__ = ["Task"]
