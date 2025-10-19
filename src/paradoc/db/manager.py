"""Database manager for handling table and plot data storage."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Callable

from .models import PlotData, TableCell, TableColumn, TableData, TableSortConfig, TableFilterConfig
from .plot_renderer import PlotRenderer


class DbManager:
    """Manages SQLite database for tables and plots."""

    def __init__(self, db_path: str | Path = "paradoc_data.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.connection: Optional[sqlite3.Connection] = None
        self._initialized = False

    def _init_db(self):
        """Initialize database schema. Only called when data is written."""
        if self._initialized:
            return

        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()

        # Tables schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tables (
                key TEXT PRIMARY KEY,
                caption TEXT NOT NULL,
                show_index_default INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS table_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_key TEXT NOT NULL,
                name TEXT NOT NULL,
                data_type TEXT DEFAULT 'string',
                FOREIGN KEY (table_key) REFERENCES tables(key) ON DELETE CASCADE,
                UNIQUE(table_key, name)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS table_cells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_key TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                column_name TEXT NOT NULL,
                value TEXT,
                FOREIGN KEY (table_key) REFERENCES tables(key) ON DELETE CASCADE,
                UNIQUE(table_key, row_index, column_name)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS table_sort_config (
                table_key TEXT PRIMARY KEY,
                column_name TEXT NOT NULL,
                ascending INTEGER DEFAULT 1,
                FOREIGN KEY (table_key) REFERENCES tables(key) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS table_filter_config (
                table_key TEXT PRIMARY KEY,
                column_name TEXT NOT NULL,
                pattern TEXT NOT NULL,
                is_regex INTEGER DEFAULT 1,
                FOREIGN KEY (table_key) REFERENCES tables(key) ON DELETE CASCADE
            )
        """)

        # Plots schema (placeholder for future)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plots (
                key TEXT PRIMARY KEY,
                plot_type TEXT NOT NULL,
                data TEXT NOT NULL,
                caption TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                custom_function_name TEXT,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.connection.commit()
        self._initialized = True

    def _ensure_connection(self):
        """Ensure database connection exists for read operations."""
        if self.connection is None and self.db_path.exists():
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row
            self._initialized = True

    def add_table(self, table_data: TableData) -> None:
        """
        Add or update a table in the database.

        Args:
            table_data: TableData model instance
        """
        # Initialize database if not already done
        self._init_db()

        cursor = self.connection.cursor()

        # Insert or update main table record
        cursor.execute("""
            INSERT OR REPLACE INTO tables (key, caption, show_index_default, metadata, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            table_data.key,
            table_data.caption,
            1 if table_data.show_index_default else 0,
            json.dumps(table_data.metadata)
        ))

        # Delete existing columns and cells for this table
        cursor.execute("DELETE FROM table_columns WHERE table_key = ?", (table_data.key,))
        cursor.execute("DELETE FROM table_cells WHERE table_key = ?", (table_data.key,))

        # Insert columns
        for column in table_data.columns:
            cursor.execute("""
                INSERT INTO table_columns (table_key, name, data_type)
                VALUES (?, ?, ?)
            """, (table_data.key, column.name, column.data_type))

        # Insert cells
        for cell in table_data.cells:
            cursor.execute("""
                INSERT INTO table_cells (table_key, row_index, column_name, value)
                VALUES (?, ?, ?, ?)
            """, (table_data.key, cell.row_index, cell.column_name, str(cell.value)))

        # Handle sort config
        if table_data.default_sort:
            cursor.execute("""
                INSERT OR REPLACE INTO table_sort_config (table_key, column_name, ascending)
                VALUES (?, ?, ?)
            """, (
                table_data.key,
                table_data.default_sort.column_name,
                1 if table_data.default_sort.ascending else 0
            ))

        # Handle filter config
        if table_data.default_filter:
            cursor.execute("""
                INSERT OR REPLACE INTO table_filter_config (table_key, column_name, pattern, is_regex)
                VALUES (?, ?, ?, ?)
            """, (
                table_data.key,
                table_data.default_filter.column_name,
                table_data.default_filter.pattern,
                1 if table_data.default_filter.is_regex else 0
            ))

        self.connection.commit()

    def get_table(self, key: str) -> Optional[TableData]:
        """
        Retrieve table data by key.

        Args:
            key: Table key (without __ markers)

        Returns:
            TableData instance or None if not found
        """
        # Ensure connection exists for reading
        self._ensure_connection()

        if self.connection is None:
            return None

        cursor = self.connection.cursor()

        # Get main table record
        cursor.execute("SELECT * FROM tables WHERE key = ?", (key,))
        row = cursor.fetchone()

        if not row:
            return None

        # Get columns
        cursor.execute("SELECT name, data_type FROM table_columns WHERE table_key = ?", (key,))
        columns = [TableColumn(name=r['name'], data_type=r['data_type']) for r in cursor.fetchall()]

        # Get cells
        cursor.execute("""
            SELECT row_index, column_name, value 
            FROM table_cells 
            WHERE table_key = ?
            ORDER BY row_index, column_name
        """, (key,))
        cells = [
            TableCell(row_index=r['row_index'], column_name=r['column_name'], value=r['value'])
            for r in cursor.fetchall()
        ]

        # Get sort config
        cursor.execute("SELECT * FROM table_sort_config WHERE table_key = ?", (key,))
        sort_row = cursor.fetchone()
        default_sort = None
        if sort_row:
            default_sort = TableSortConfig(
                column_name=sort_row['column_name'],
                ascending=bool(sort_row['ascending'])
            )

        # Get filter config
        cursor.execute("SELECT * FROM table_filter_config WHERE table_key = ?", (key,))
        filter_row = cursor.fetchone()
        default_filter = None
        if filter_row:
            default_filter = TableFilterConfig(
                column_name=filter_row['column_name'],
                pattern=filter_row['pattern'],
                is_regex=bool(filter_row['is_regex'])
            )

        return TableData(
            key=row['key'],
            caption=row['caption'],
            columns=columns,
            cells=cells,
            default_sort=default_sort,
            default_filter=default_filter,
            show_index_default=bool(row['show_index_default']),
            metadata=json.loads(row['metadata'])
        )

    def list_tables(self) -> List[str]:
        """List all table keys in the database."""
        # Ensure connection exists for reading
        self._ensure_connection()

        if self.connection is None:
            return []

        cursor = self.connection.cursor()
        cursor.execute("SELECT key FROM tables ORDER BY key")
        return [row['key'] for row in cursor.fetchall()]

    def delete_table(self, key: str) -> None:
        """Delete a table and all associated data."""
        # Initialize database if not already done (in case we're deleting from existing DB)
        self._ensure_connection()

        if self.connection is None:
            return

        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM tables WHERE key = ?", (key,))
        self.connection.commit()

    def add_plot(self, plot_data: PlotData) -> None:
        """
        Add or update a plot in the database.

        Args:
            plot_data: PlotData model instance
        """
        # Initialize database if not already done
        self._init_db()

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO plots (key, plot_type, data, caption, width, height, custom_function_name, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            plot_data.key,
            plot_data.plot_type,
            json.dumps(plot_data.data),
            plot_data.caption,
            plot_data.width,
            plot_data.height,
            plot_data.custom_function_name,
            json.dumps(plot_data.metadata)
        ))
        self.connection.commit()

    def get_plot(self, key: str) -> Optional[PlotData]:
        """
        Retrieve plot data by key.

        Args:
            key: Plot key (without __ markers)

        Returns:
            PlotData instance or None if not found
        """
        # Ensure connection exists for reading
        self._ensure_connection()

        if self.connection is None:
            return None

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM plots WHERE key = ?", (key,))
        row = cursor.fetchone()

        if not row:
            return None

        return PlotData(
            key=row['key'],
            plot_type=row['plot_type'],
            data=json.loads(row['data']),
            caption=row['caption'],
            width=row['width'],
            height=row['height'],
            custom_function_name=row['custom_function_name'],
            metadata=json.loads(row['metadata'])
        )

    def list_plots(self) -> List[str]:
        """List all plot keys in the database."""
        # Ensure connection exists for reading
        self._ensure_connection()

        if self.connection is None:
            return []

        cursor = self.connection.cursor()
        cursor.execute("SELECT key FROM plots ORDER BY key")
        return [row['key'] for row in cursor.fetchall()]

    def delete_plot(self, key: str) -> None:
        """Delete a plot."""
        # Ensure connection exists
        self._ensure_connection()

        if self.connection is None:
            return

        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM plots WHERE key = ?", (key,))
        self.connection.commit()

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
