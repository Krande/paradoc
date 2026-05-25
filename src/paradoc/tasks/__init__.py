"""Task primitives — the declarative side of paradoc's build system.

Scaffolding scope: this module ships the @task decorator + registry +
discovery so authors can write `<doc>/tasks.py` and have it loaded by
paradoc. The runner that turns a validated registry into actual cell
execution (with cache, fanout expansion, subprocess marshaling, env
selection) lives in the next phase.

The legacy file-centric `Task` BaseModel is preserved under
`LegacyTaskSpec` (and aliased as `Task` for backwards compat) until
`Filter.task` and `FEAModelResults.task_id` migrate to `TaskHandle`.
"""

from .cache import CacheKey, TaskCache, compute_cache_key
from .cells import Cell, cells_for, expand_fanout
from .decorator import is_task, task
from .discovery import discover_tasks
from .executors import Executor, InProcessExecutor
from .models import LegacyTaskSpec, Task, TaskFn, TaskHandle
from .registry import (
    TaskRegistry,
    get_default_registry,
    reset_default_registry,
)
from .runner import Runner
from .source_hash import ast_source_hash

__all__ = [
    "task",
    "is_task",
    "discover_tasks",
    "TaskFn",
    "TaskHandle",
    "TaskRegistry",
    "get_default_registry",
    "reset_default_registry",
    "LegacyTaskSpec",
    "Task",
    "Cell",
    "cells_for",
    "expand_fanout",
    "Executor",
    "InProcessExecutor",
    "Runner",
    "TaskCache",
    "CacheKey",
    "compute_cache_key",
    "ast_source_hash",
]
