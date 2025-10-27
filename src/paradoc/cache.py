"""
Caching utilities for Paradoc to improve performance.

Provides timestamp-based caching for Plotly figure generation.
"""

import logging
import pathlib
import pickle
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PlotFigureCache:
    """
    Specialized cache for Plotly figure objects.

    Uses database timestamp-based invalidation instead of expensive content hashing.
    Cache is valid as long as the plot data in the database hasn't been updated.
    """

    def __init__(self, cache_dir: pathlib.Path):
        """Initialize plot figure cache."""
        self.cache_dir = pathlib.Path(cache_dir) / "plot_figures"
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def get_figure(self, plot_key: str, db_updated_at: float) -> Optional[Any]:
        """
        Get cached Plotly figure if available and still valid.

        Args:
            plot_key: Plot identifier
            db_updated_at: Unix timestamp of when the plot was last updated in the database

        Returns:
            Cached figure object or None
        """
        # Check memory cache first
        if plot_key in self._memory_cache:
            cache_entry = self._memory_cache[plot_key]
            if cache_entry["timestamp"] >= db_updated_at:
                logger.debug(f"Plot figure cache hit (memory): {plot_key}")
                return cache_entry["figure"]
            else:
                # Stale cache entry
                del self._memory_cache[plot_key]
                logger.debug(f"Plot figure cache stale (memory): {plot_key}")

        # Check disk cache
        cache_file = self.cache_dir / f"{plot_key}.pkl"
        timestamp_file = self.cache_dir / f"{plot_key}.timestamp"

        if cache_file.exists() and timestamp_file.exists():
            try:
                cached_timestamp = float(timestamp_file.read_text(encoding="utf-8").strip())

                # Check if cache is still valid
                if cached_timestamp >= db_updated_at:
                    with open(cache_file, "rb") as f:
                        fig = pickle.load(f)

                    # Store in memory cache
                    self._memory_cache[plot_key] = {"figure": fig, "timestamp": cached_timestamp}
                    logger.debug(f"Plot figure cache hit (disk): {plot_key}")
                    return fig
                else:
                    logger.debug(f"Plot figure cache stale (disk): {plot_key}")
            except Exception as e:
                logger.warning(f"Failed to load cached figure for {plot_key}: {e}")

        return None

    def set_figure(self, plot_key: str, db_updated_at: float, fig: Any) -> None:
        """
        Cache a Plotly figure.

        Args:
            plot_key: Plot identifier
            db_updated_at: Unix timestamp of when the plot was updated in the database
            fig: Plotly figure object to cache
        """
        # Store in memory cache
        self._memory_cache[plot_key] = {"figure": fig, "timestamp": db_updated_at}

        # Store on disk
        cache_file = self.cache_dir / f"{plot_key}.pkl"
        timestamp_file = self.cache_dir / f"{plot_key}.timestamp"

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(fig, f)

            timestamp_file.write_text(str(db_updated_at), encoding="utf-8")
            logger.debug(f"Cached plot figure: {plot_key} (timestamp: {db_updated_at})")
        except Exception as e:
            logger.warning(f"Failed to cache figure for {plot_key}: {e}")

    def invalidate(self, plot_key: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            plot_key: Specific key to invalidate, or None to clear all
        """
        if plot_key is None:
            # Clear all caches
            self._memory_cache.clear()
            for cache_file in self.cache_dir.glob("*"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
            logger.info("Cleared all plot figure cache entries")
        else:
            # Clear specific key
            if plot_key in self._memory_cache:
                del self._memory_cache[plot_key]

            cache_file = self.cache_dir / f"{plot_key}.pkl"
            timestamp_file = self.cache_dir / f"{plot_key}.timestamp"

            for path in [cache_file, timestamp_file]:
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass

            logger.debug(f"Invalidated plot figure cache: {plot_key}")


class DocumentCache:
    """
    Manages caching for document processing operations.

    Uses content-based hashing to determine cache validity.
    Cache is stored in a .paradoc_cache directory within the document's build directory.
    """

    def __init__(self, cache_dir: pathlib.Path):
        """
        Initialize document cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = pathlib.Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self._memory_cache: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if valid.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        # Check memory cache first
        if key in self._memory_cache:
            logger.debug(f"Cache hit (memory): {key}")
            return self._memory_cache[key]

        return None

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        # Store in memory cache
        self._memory_cache[key] = value
        logger.debug(f"Cached: {key}")

    def invalidate(self, key: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate, or None to clear all
        """
        if key is None:
            # Clear all caches
            self._memory_cache.clear()
            logger.info("Cleared all cache entries")
        else:
            # Clear specific key
            if key in self._memory_cache:
                del self._memory_cache[key]
            logger.debug(f"Invalidated cache: {key}")
