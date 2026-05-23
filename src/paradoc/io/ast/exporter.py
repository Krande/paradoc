from __future__ import annotations

import contextlib
import json
import mimetypes
import os
import pathlib
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import pypandoc

from paradoc.citation import FILTER_PATH as SHELF_CITATION_FILTER
from paradoc.config import logger

if TYPE_CHECKING:
    from paradoc import OneDoc


@contextlib.contextmanager
def _shelf_citation_env(one: "OneDoc"):
    """Set env vars consumed by the shelf-citation pandoc filter.

    Mirrors HTMLExporter's helper — kept inline rather than shared so
    the two exporters' contracts stay independent.
    """
    keys = ("PARADOC_BIBLIOGRAPHY", "PARADOC_SHELF_BASE_URL")
    prior = {k: os.environ.get(k) for k in keys}
    bib = getattr(one, "bibliography_file", None)
    if bib is not None:
        os.environ["PARADOC_BIBLIOGRAPHY"] = str(bib)
    else:
        os.environ.pop("PARADOC_BIBLIOGRAPHY", None)
    shelf_url = getattr(one, "shelf_base_url", "")
    if shelf_url:
        os.environ["PARADOC_SHELF_BASE_URL"] = shelf_url
    else:
        os.environ.pop("PARADOC_SHELF_BASE_URL", None)
    try:
        yield
    finally:
        for k, v in prior.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _reset_kaleido_scope():
    """
    Reset the kaleido scope to recover from communication errors.

    This helps recover from choreographer JSONDecodeError issues where
    the Chrome subprocess pipe has stale data from interrupted processes.
    """
    try:
        import plotly.io as pio

        if hasattr(pio, "_kaleido") and hasattr(pio._kaleido, "scope"):
            if pio._kaleido.scope:
                logger.debug("Resetting kaleido scope to clear stale subprocess state")
                try:
                    pio._kaleido.scope.__exit__(None, None, None)
                except Exception:
                    pass
                pio._kaleido.scope = None
    except Exception as e:
        logger.debug(f"Could not reset kaleido scope: {e}")


class ASTExporter:
    """
    Exporter that builds a Pandoc JSON AST from the current OneDoc markdown sources
    and streams it to the frontend over WebSocket in sectioned chunks.

    Frontend contract (already implemented by the SPA worker):
    - First send a manifest message:
        { "kind": "manifest", "manifest": { "docId": str, "sections": [{ id, title, level, index }] } }
    - Then stream each section as:
        { "kind": "ast_section", "section": { id, title, level, index }, "doc": { "blocks": [...] } }
    """

    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    # -------------------------------
    # AST construction and slicing
    # -------------------------------
    def build_ast(self) -> Dict[str, Any]:
        """
        Concatenate main and appendix md (with \appendix marker) and obtain Pandoc JSON AST.
        Inserts source file markers to enable tracking which blocks came from which files.
        """
        one = self.one_doc

        # Build concatenated markdown with source file markers
        md_parts = []
        source_markers = []  # Track marker positions and corresponding files

        # Add main files with markers
        for md_file in one.md_files_main:
            marker = f"<!-- PARADOC_SOURCE_FILE: {md_file.path} -->"
            source_markers.append(
                {"marker": marker, "source_file": str(md_file.path), "source_dir": str(md_file.path.parent)}
            )
            md_parts.append(marker)
            md_parts.append(md_file.read_built_file())

        # Add appendix marker
        md_parts.append("\n\n\\appendix\n\n")

        # Add appendix files with markers
        for md_file in one.md_files_app:
            marker = f"<!-- PARADOC_SOURCE_FILE: {md_file.path} -->"
            source_markers.append(
                {"marker": marker, "source_file": str(md_file.path), "source_dir": str(md_file.path.parent)}
            )
            md_parts.append(marker)
            md_parts.append(md_file.read_built_file())

        combined_str = "\n\n".join(md_parts)

        with _shelf_citation_env(one):
            ast_json = pypandoc.convert_text(
                combined_str,
                to="json",
                format="markdown",
                extra_args=[
                    "-M2GB",
                    "+RTS",
                    "-K64m",
                    "-RTS",
                    f"--metadata-file={one.metadata_file}",
                ],
                # Shelf citation filter appended after pandoc-crossref;
                # it's a no-op when bibliography_file is unset.
                filters=["pandoc-crossref", str(SHELF_CITATION_FILTER)],
            )
        try:
            ast = json.loads(ast_json)
        except Exception as e:
            logger.error(f"Failed to parse Pandoc JSON AST: {e}")
            raise

        # Parse the AST and map blocks to source files using the markers
        self._map_blocks_to_sources(ast, source_markers)

        return ast

    def _map_blocks_to_sources(self, ast: Dict[str, Any], source_markers: List[Dict[str, str]]):
        """
        Map blocks in the AST to their source files by finding the marker comments.
        Annotates each block with _paradoc_source metadata.
        """
        blocks = ast.get("blocks", [])
        if not blocks:
            return

        # Find marker positions in the blocks list
        current_source = None
        marker_indices = []

        for idx, block in enumerate(blocks):
            if isinstance(block, dict) and block.get("t") == "RawBlock":
                c = block.get("c", [])
                if isinstance(c, list) and len(c) >= 2:
                    format_type, content = c[0], c[1]
                    if format_type == "html" and "PARADOC_SOURCE_FILE:" in content:
                        # Found a marker - extract source info
                        for marker_info in source_markers:
                            if marker_info["marker"] in content:
                                current_source = {
                                    "source_file": marker_info["source_file"],
                                    "source_dir": marker_info["source_dir"],
                                }
                                marker_indices.append(idx)
                                break

            # Annotate block with current source
            if current_source and isinstance(block, dict):
                block["_paradoc_source"] = current_source

        # Remove the marker blocks from the AST (they've served their purpose)
        for idx in reversed(marker_indices):
            blocks.pop(idx)

    @staticmethod
    def _header_text(inlines: List[Any]) -> str:
        # Extract plain text from a list of Pandoc inline elements (supports list- and dict-form)
        parts: List[str] = []
        for item in inlines or []:
            # Dict-form: {"t": "Str", "c": "Text"} or {"t": "Space"}
            if isinstance(item, dict):
                t = item.get("t")
                if t == "Str":
                    c = item.get("c")
                    if isinstance(c, str):
                        parts.append(c)
                elif t == "Space":
                    parts.append(" ")
                # Ignore other inline types for title extraction
                continue
            # List-form: ["Str", "Text"] or ["Space"]
            if isinstance(item, list) and item:
                t = item[0]
                if t == "Str" and len(item) >= 2 and isinstance(item[1], str):
                    parts.append(item[1])
                elif t == "Space":
                    parts.append(" ")
        return "".join(parts).strip()

    def slice_sections(self, ast: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Split the document into sections by top-level (level==1) headers for content bundles.
        Extract ALL headers (H1-H6) for the manifest to enable nested outline/TOC in frontend.

        Returns (manifest, section_bundles)
        - manifest: { docId, sections: [{ id, title, level, index, isAppendix }] } - includes ALL headers
        - section_bundles: list of { section: meta, doc: { blocks: [...] } } - split by H1 only
        """
        blocks = ast.get("blocks") or ast.get("pandoc-api-version") and ast.get("blocks")
        # Some Pandoc versions wrap under {"blocks": ...}; ensure we have a list
        if not isinstance(blocks, list):
            blocks = ast.get("blocks", [])

        # Section bundles: split by H1 for content delivery
        sections: List[Dict[str, Any]] = []
        current: List[Any] = []
        current_meta: Dict[str, Any] | None = None
        section_index = -1

        # All headers: for manifest (includes all levels)
        all_headers: List[Dict[str, Any]] = []
        header_index = 0

        # Track whether we've encountered the \appendix marker
        in_appendix = False

        def push_current():
            if current_meta is None:
                return
            sections.append(
                {
                    "section": current_meta,
                    "doc": {"blocks": list(current)},
                }
            )

        for blk in blocks:
            # Check for \appendix marker in RawBlock
            if isinstance(blk, dict) and blk.get("t") == "RawBlock":
                try:
                    content = blk.get("c", [])
                    if isinstance(content, list) and len(content) >= 2:
                        raw_text = content[1]
                        if isinstance(raw_text, str) and "\\appendix" in raw_text:
                            in_appendix = True
                except Exception:
                    pass

            level = None
            attrs: Any = None
            inlines: List[Any] = []

            # Dict-form header detection
            if isinstance(blk, dict) and blk.get("t") == "Header":
                try:
                    content = blk.get("c", [])
                    if isinstance(content, list) and len(content) >= 3:
                        level = int(content[0])
                        attrs = content[1]
                        inlines = content[2]
                except Exception:
                    level = 1
            # List-form header detection
            elif isinstance(blk, list) and blk and blk[0] == "Header":
                try:
                    level = int(blk[1])
                except Exception:
                    level = 1
                attrs = blk[2] if len(blk) > 2 else ["", [], []]
                inlines = blk[3] if len(blk) > 3 else []

            # If this is any header level, add to all_headers for manifest
            if level is not None:
                # Extract id from attrs for both forms
                try:
                    if isinstance(attrs, list) and attrs:
                        sec_id = attrs[0] or f"sec-{header_index}"
                    elif isinstance(attrs, dict):
                        sec_id = attrs.get("id") or f"sec-{header_index}"
                    else:
                        sec_id = f"sec-{header_index}"
                except Exception:
                    sec_id = f"sec-{header_index}"

                title = self._header_text(inlines)
                all_headers.append(
                    {
                        "id": sec_id,
                        "title": title or f"Section {header_index + 1}",
                        "level": level,
                        "index": header_index,
                        "isAppendix": in_appendix,
                    }
                )
                header_index += 1

            # H1 headers create new section bundles
            if level == 1:
                # Finish previous
                push_current()
                current = []
                section_index += 1
                # Reuse the header metadata we just added
                current_meta = all_headers[-1].copy()
                current_meta["index"] = section_index  # Section bundle index (different from header index)

            # Accumulate blocks into current H1 section bundle
            if current_meta is None:
                # Before first H1, skip content (optional: could create a preface section)
                continue
            current.append(blk)

        # Flush tail
        push_current()

        # Fallback: if no H1 sections found, wrap entire document
        if not sections:
            all_blocks = ast.get("blocks", [])
            # Try to find first header of any level for title/id
            title = "Document"
            sec_id = "sec-0"
            for blk in all_blocks:
                try:
                    if isinstance(blk, dict) and blk.get("t") == "Header":
                        content = blk.get("c", [])
                        attrs = content[1] if isinstance(content, list) and len(content) >= 2 else ["", [], []]
                        inlines = content[2] if isinstance(content, list) and len(content) >= 3 else []
                        if isinstance(attrs, list) and attrs:
                            maybe_id = attrs[0]
                        elif isinstance(attrs, dict):
                            maybe_id = attrs.get("id")
                        else:
                            maybe_id = None
                        if maybe_id:
                            sec_id = str(maybe_id)
                        title = self._header_text(inlines) or title
                        break
                    if isinstance(blk, list) and blk and blk[0] == "Header":
                        attrs = blk[2] if len(blk) > 2 else ["", [], []]
                        inlines = blk[3] if len(blk) > 3 else []
                        maybe_id = attrs[0] if isinstance(attrs, list) and attrs else ""
                        if maybe_id:
                            sec_id = str(maybe_id)
                        title = self._header_text(inlines) or title
                        break
                except Exception:
                    continue
            sections.append(
                {
                    "section": {"id": sec_id, "title": title, "level": 1, "index": 0, "isAppendix": False},
                    "doc": {"blocks": list(all_blocks)},
                }
            )

        # Build manifest with ALL headers (not just H1s)
        doc_id = self._infer_doc_id()
        manifest = {
            "docId": doc_id,
            "sections": all_headers if all_headers else [s["section"] for s in sections],
        }
        return manifest, sections

    def _infer_doc_id(self) -> str:
        # Best-effort doc id from folder name
        try:
            return self.one_doc.source_dir.name or "doc"
        except Exception:
            return "doc"

    # -------------------------------
    # Image embedding utilities
    # -------------------------------
    def _extract_image_paths(self, blocks: List[Any]) -> List[str]:
        """Recursively extract all image paths from Pandoc blocks."""
        image_paths = []

        def extract_from_inlines(inlines: List[Any]):
            for inline in inlines or []:
                if isinstance(inline, dict) and inline.get("t") == "Image":
                    try:
                        # Image: c = [Attr, [alt inlines], [src, title]]
                        content = inline.get("c", [])
                        if isinstance(content, list) and len(content) >= 3:
                            src_info = content[2]
                            if isinstance(src_info, list) and len(src_info) >= 1:
                                src = src_info[0]
                                if isinstance(src, str) and not src.startswith(("http://", "https://", "data:")):
                                    image_paths.append(src)
                    except Exception:
                        pass

        def extract_from_blocks(blks: List[Any]):
            for blk in blks or []:
                if not isinstance(blk, dict):
                    continue

                t = blk.get("t")
                c = blk.get("c", [])

                # Handle different block types that might contain images
                if t == "Para" or t == "Plain":
                    extract_from_inlines(c)
                elif t == "Figure":
                    # Figure: c = [Attr, caption, content_blocks]
                    if isinstance(c, list) and len(c) >= 3:
                        content_blocks = c[2]
                        extract_from_blocks(content_blocks)
                elif t == "Div":
                    # Div: c = [Attr, blocks]
                    if isinstance(c, list) and len(c) >= 2:
                        extract_from_blocks(c[1])
                elif t == "BulletList" or t == "OrderedList":
                    # Lists contain list of block lists
                    if t == "BulletList" and isinstance(c, list):
                        for item in c:
                            if isinstance(item, list):
                                extract_from_blocks(item)
                    elif t == "OrderedList" and isinstance(c, list) and len(c) >= 2:
                        items = c[1]
                        for item in items:
                            if isinstance(item, list):
                                extract_from_blocks(item)
                elif t == "BlockQuote":
                    extract_from_blocks(c)

        extract_from_blocks(blocks)
        return list(set(image_paths))  # Remove duplicates

    def _embed_images_in_bundle(self, bundle: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """
        Extract image paths from bundle and return embedded image data.
        Uses source file tracking to resolve images relative to their original markdown file.
        Returns dict mapping image path -> {data: base64_data, mimeType: mime_type}
        """
        import base64

        embedded_images = {}
        doc = bundle.get("doc", {})
        blocks = doc.get("blocks", [])

        # Extract images along with their source context
        images_with_context = self._extract_images_with_source(blocks)

        if images_with_context:
            logger.info(f"Found {len(images_with_context)} images to embed")

        for img_info in images_with_context:
            img_path = img_info["path"]
            source_dir = img_info.get("source_dir")

            try:
                # Normalize path: remove leading ./ if present
                normalized_path = img_path.replace("./", "", 1) if img_path.startswith("./") else img_path

                # Try to resolve image path
                resolved_path = None

                # Strategy 1: If we have source_dir info, try relative to the source markdown file
                if source_dir:
                    source_dir_path = pathlib.Path(source_dir)
                    for path_variant in [img_path, normalized_path]:
                        candidate = source_dir_path / path_variant
                        if candidate.exists() and candidate.is_file():
                            resolved_path = candidate
                            logger.debug(f"Resolved {img_path} using source dir: {source_dir}")
                            break

                # Strategy 2: Fall back to searching in dist_dir, build_dir, source_dir
                if resolved_path is None:
                    for base in [self.one_doc.dist_dir, self.one_doc.build_dir, self.one_doc.source_dir]:
                        for path_variant in [img_path, normalized_path]:
                            # Try direct path first
                            candidate = base / path_variant
                            if candidate.exists() and candidate.is_file():
                                resolved_path = candidate
                                break

                            # Try searching in subdirectories (for images in 00-main/images/, etc.)
                            # Extract just the filename from the path
                            filename = pathlib.Path(path_variant).name
                            for subdir_candidate in base.rglob(filename):
                                if subdir_candidate.is_file():
                                    resolved_path = subdir_candidate
                                    logger.debug(f"Resolved {img_path} via recursive search: {subdir_candidate}")
                                    break

                            if resolved_path:
                                break
                        if resolved_path:
                            break

                if resolved_path is None:
                    logger.warning(
                        f"Could not find image file: {img_path} (source_dir: {source_dir}, also tried: {normalized_path})"
                    )
                    continue

                # Read and encode image (no caching for static images - they're typically small)
                with open(resolved_path, "rb") as f:
                    img_data = f.read()

                b64_data = base64.b64encode(img_data).decode("ascii")
                mime_type = mimetypes.guess_type(str(resolved_path))[0] or "application/octet-stream"

                # Store with normalized path (without ./)
                embedded_images[normalized_path] = {"data": b64_data, "mimeType": mime_type}

                logger.debug(f"Embedded image: {img_path} -> {normalized_path} ({len(img_data)} bytes, {mime_type})")

            except Exception as e:
                logger.warning(f"Failed to embed image {img_path}: {e}")

        return embedded_images

    def _extract_images_with_source(self, blocks: List[Any]) -> List[Dict[str, str]]:
        """
        Recursively extract all image paths from Pandoc blocks along with their source file context.
        Returns list of dicts with 'path' and 'source_dir' keys.
        """
        images_with_context = []

        def extract_from_inlines(inlines: List[Any], source_dir: str = None):
            for inline in inlines or []:
                if isinstance(inline, dict) and inline.get("t") == "Image":
                    try:
                        # Image: c = [Attr, [alt inlines], [src, title]]
                        content = inline.get("c", [])
                        if isinstance(content, list) and len(content) >= 3:
                            src_info = content[2]
                            if isinstance(src_info, list) and len(src_info) >= 1:
                                src = src_info[0]
                                if isinstance(src, str) and not src.startswith(("http://", "https://", "data:")):
                                    images_with_context.append({"path": src, "source_dir": source_dir})
                    except Exception:
                        pass

        def extract_from_blocks(blks: List[Any]):
            for blk in blks or []:
                if not isinstance(blk, dict):
                    continue

                # Extract source directory from block metadata
                source_info = blk.get("_paradoc_source", {})
                source_dir = source_info.get("source_dir")

                t = blk.get("t")
                c = blk.get("c", [])

                # Handle different block types that might contain images
                if t == "Para" or t == "Plain":
                    extract_from_inlines(c, source_dir)
                elif t == "Figure":
                    # Figure: c = [Attr, caption, content_blocks]
                    if isinstance(c, list) and len(c) >= 3:
                        content_blocks = c[2]
                        extract_from_blocks(content_blocks)
                elif t == "Div":
                    # Div: c = [Attr, blocks]
                    if isinstance(c, list) and len(c) >= 2:
                        extract_from_blocks(c[1])
                elif t == "BulletList" or t == "OrderedList":
                    # Lists contain list of block lists
                    if t == "BulletList" and isinstance(c, list):
                        for item in c:
                            if isinstance(item, list):
                                extract_from_blocks(item)
                    elif t == "OrderedList" and isinstance(c, list) and len(c) >= 2:
                        items = c[1]
                        for item in items:
                            if isinstance(item, list):
                                extract_from_blocks(item)
                elif t == "BlockQuote":
                    extract_from_blocks(c)

        extract_from_blocks(blocks)
        return images_with_context

    # -------------------------------
    # WebSocket streaming
    # -------------------------------
    def send_to_frontend(
        self,
        host: str = "localhost",
        port: int = 13579,
        embed_images: bool = True,
        use_static_html: bool = False,
        frontend_id: str | None = None,
        auto_open_frontend: bool = True,
    ) -> bool:
        """
        Build AST, slice it into sections, and stream manifest + sections over the
        Paradoc WebSocket broadcast server.

        Args:
            host: WebSocket server host
            port: WebSocket server port
            embed_images: If True, embed images as base64 in WebSocket messages instead of serving via HTTP
            use_static_html: If True, extract frontend.zip to resources folder and open in browser
            frontend_id: Optional frontend ID to send to specific frontend. If None, sends to all connected frontends.
            auto_open_frontend: If True, automatically open a local frontend if none connected. Default True.

        Returns:
            True if successful, False otherwise
        """
        # If use_static_html is True, use the FrontendHandler for static HTML mode
        if use_static_html:
            return self._send_to_static_frontend(host=host, port=port, embed_images=embed_images)

        # For WebSocket mode, ensure server is running and frontend is ready
        from paradoc.frontend.frontend_handler import FrontendHandler
        from paradoc.frontend.ws_server import ensure_ws_server

        # Ensure WebSocket server is running
        if not ensure_ws_server(host=host, port=port):
            logger.error("WebSocket server could not be started or reached")
            return False

        # Use FrontendHandler to ensure a frontend is ready
        frontend_handler = FrontendHandler(self.one_doc, host=host, port=port)

        # Check if specific frontend_id is requested
        if frontend_id:
            connected = frontend_handler.get_connected_frontends()
            if frontend_id not in connected:
                logger.warning(f"Frontend ID '{frontend_id}' not found. Connected frontends: {connected}")
                print(f"Warning: Frontend ID '{frontend_id}' not found. Connected: {connected}")
                return False
            print(f"Sending document to frontend: {frontend_id}")
        else:
            # Ensure at least one frontend is ready
            if not frontend_handler.ensure_frontend_ready(
                auto_open=auto_open_frontend, wait_for_connection=auto_open_frontend
            ):
                logger.warning("No active frontends and could not open new frontend")
                print("Warning: No active frontends connected. Please open a Paradoc Reader frontend first.")
                return False

            connected = frontend_handler.get_connected_frontends()
            print(f"Sending document to {len(connected)} connected frontend(s): {connected}")

        # Build AST and prepare data
        ast = self.build_ast()
        manifest, sections = self.slice_sections(ast)
        doc_id = manifest.get("docId") or self._infer_doc_id()

        # Extract plot and table data
        plot_data_dict = self._extract_plot_data_from_db()
        table_data_dict = self._extract_table_data_from_db()

        # Setup HTTP server if not embedding images
        if not embed_images:
            self._setup_http_server(host, port, doc_id, manifest, sections)

        # Send document via WebSocket
        return self._send_via_websocket(
            host=host,
            port=port,
            manifest=manifest,
            sections=sections,
            embed_images=embed_images,
            plot_data_dict=plot_data_dict,
            table_data_dict=table_data_dict,
        )

    def _send_to_static_frontend(self, host: str, port: int, embed_images: bool) -> bool:
        """
        Send document to a static HTML frontend (opens in browser).

        Args:
            host: WebSocket server host
            port: WebSocket server port
            embed_images: If True, embed images as base64

        Returns:
            True if successful, False otherwise
        """
        from paradoc.frontend.frontend_handler import FrontendHandler
        from paradoc.frontend.ws_server import ensure_ws_server

        # Ensure WebSocket server is running
        if not ensure_ws_server(host=host, port=port):
            logger.error("WebSocket server could not be started")
            return False

        # Use FrontendHandler to manage frontend
        frontend_handler = FrontendHandler(self.one_doc, host=host, port=port)

        # Extract and open frontend
        if not frontend_handler.ensure_frontend_extracted():
            return False

        if not frontend_handler.open_frontend():
            return False

        # Wait for frontend to connect
        if not frontend_handler.wait_for_frontend_connection(timeout=10):
            logger.warning("Frontend opened but did not connect - sending anyway")

        # Build and send document
        ast = self.build_ast()
        manifest, sections = self.slice_sections(ast)
        doc_id = manifest.get("docId") or self._infer_doc_id()

        # Extract plot and table data
        plot_data_dict = self._extract_plot_data_from_db()
        table_data_dict = self._extract_table_data_from_db()

        # Setup HTTP server if not embedding images
        if not embed_images:
            self._setup_http_server(host, port, doc_id, manifest, sections)

        # Send via WebSocket
        success = self._send_via_websocket(
            host=host,
            port=port,
            manifest=manifest,
            sections=sections,
            embed_images=embed_images,
            plot_data_dict=plot_data_dict,
            table_data_dict=table_data_dict,
        )

        if success:
            frontend_handler.print_frontend_status(embed_images=embed_images)

        return success

    def _setup_http_server(
        self, host: str, port: int, doc_id: str, manifest: Dict[str, Any], sections: List[Dict[str, Any]]
    ):
        """
        Setup HTTP server for serving assets and JSON artifacts.

        Args:
            host: HTTP server host
            port: WebSocket port (HTTP port will be port+1)
            doc_id: Document ID
            manifest: Document manifest
            sections: List of section bundles
        """
        try:
            from paradoc.frontend.http_server import ensure_http_server

            http_port = int(port) + 1

            # Ensure dist_dir exists
            self.one_doc.dist_dir.mkdir(exist_ok=True, parents=True)

            # Write JSON artifacts
            base_dir = self.one_doc.dist_dir / "doc" / doc_id
            section_dir = base_dir / "section"
            section_dir.mkdir(parents=True, exist_ok=True)

            # Write manifest
            (base_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            # Write sections
            for bundle in sections:
                sec = bundle["section"]
                idx = sec.get("index")
                sid = sec.get("id")
                data = json.dumps(bundle, ensure_ascii=False)

                if idx is not None:
                    (section_dir / f"{idx}.json").write_text(data, encoding="utf-8")
                if sid:
                    safe_sid = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in str(sid))
                    (section_dir / f"{safe_sid}.json").write_text(data, encoding="utf-8")

            # Start HTTP server
            ensure_http_server(host=host, port=http_port, directory=str(self.one_doc.dist_dir))

            # Update manifest with asset URLs
            manifest["assetBase"] = f"http://{host}:{http_port}/"
            manifest["httpDocBase"] = f"http://{host}:{http_port}/doc/{doc_id}/"

            logger.info(f"HTTP server serving assets at http://{host}:{http_port}/")
        except Exception as e:
            logger.error(f"Failed to setup HTTP server: {e}", exc_info=True)

    def _send_via_websocket(
        self,
        host: str,
        port: int,
        manifest: Dict[str, Any],
        sections: List[Dict[str, Any]],
        embed_images: bool,
        plot_data_dict: Dict[str, Any],
        table_data_dict: Dict[str, Any],
    ) -> bool:
        """
        Send document data via WebSocket using WSClient.

        Args:
            host: WebSocket host
            port: WebSocket port
            manifest: Document manifest
            sections: List of section bundles
            embed_images: If True, embed images in messages
            plot_data_dict: Plot data dictionary
            table_data_dict: Table data dictionary

        Returns:
            True if successful, False otherwise
        """
        from paradoc.frontend.ws_client import WSClient

        # Prepare embedded images if requested
        embedded_images_list = []
        if embed_images:
            for bundle in sections:
                embedded_images = self._embed_images_in_bundle(bundle)
                embedded_images_list.append(embedded_images)

        # Send using WSClient
        try:
            with WSClient(host=host, port=port) as ws_client:
                if not ws_client._ws:  # Connection failed
                    return False

                return ws_client.send_complete_document(
                    manifest=manifest,
                    sections=sections,
                    embedded_images=embedded_images_list if embed_images else None,
                    plot_data=plot_data_dict,
                    table_data=table_data_dict,
                )
        except Exception as e:
            logger.error(f"Failed to send document via WebSocket: {e}")
            return False

    def _extract_plot_data_from_db(self) -> Dict[str, Any]:
        """
        Extract all plot data from the database and return as a dictionary.
        Converts plot data to Plotly figure dictionaries for frontend rendering.
        Uses timestamp-based caching for efficient figure generation.

        Returns:
            Dictionary mapping plot keys to their data (compatible with Plotly.js)
        """
        try:
            plot_keys = self.one_doc.db_manager.list_plots()
            plot_data_dict = {}

            for key in plot_keys:
                # Get plot data with timestamp for cache validation
                result = self.one_doc.db_manager.get_plot_with_timestamp(key)
                if result:
                    plot_data, db_timestamp = result

                    # Convert plot data to Plotly figure using the renderer
                    try:
                        # Create figure directly (caching is handled elsewhere for file output)
                        fig = self.one_doc.plot_renderer._create_figure(plot_data)

                        # Convert figure to JSON-compatible dict
                        # Use plotly's to_json() then parse to ensure all numpy arrays are converted
                        #
                        # Retry logic for transient kaleido/choreographer errors:
                        # Kaleido (plotly's image export library) uses choreographer to communicate
                        # with a Chrome subprocess via pipes. Sometimes this communication fails with
                        # JSONDecodeError when:
                        # - Previous interrupted runs left stale data in the pipe
                        # - Chrome subprocess is in a bad state
                        # - First-time initialization hasn't completed
                        # Solution: Retry with scope reset to reinitialize the subprocess
                        import time

                        import plotly

                        max_retries = 2
                        retry_delay = 0.5
                        fig_json_str = None
                        last_error = None

                        for attempt in range(max_retries):
                            try:
                                fig_json_str = plotly.io.to_json(fig)
                                break
                            except Exception as e:
                                last_error = e
                                error_msg = str(e)
                                # Check if this is a choreographer/kaleido communication error
                                if "choreographer" in error_msg.lower() or "JSONDecodeError" in str(type(e).__name__):
                                    if attempt < max_retries - 1:
                                        logger.warning(
                                            f"Kaleido communication error for plot {key} (attempt {attempt + 1}/{max_retries}): {e}"
                                        )
                                        time.sleep(retry_delay)
                                        # Reset kaleido scope to clear stale subprocess state
                                        _reset_kaleido_scope()
                                        continue
                                raise

                        if fig_json_str is None:
                            raise last_error if last_error else Exception("Failed to convert figure to JSON")

                        fig_dict = json.loads(fig_json_str)

                        plot_data_dict[key] = {
                            "key": plot_data.key,
                            "plot_type": plot_data.plot_type,
                            "figure": fig_dict,  # Plotly figure dict ready for Plotly.js
                            "caption": plot_data.caption,
                            "width": plot_data.width or 800,
                            "height": plot_data.height or 600,
                            "metadata": plot_data.metadata,
                        }
                        logger.debug(f"Successfully converted plot {key} to Plotly figure")
                    except Exception as e:
                        logger.warning(f"Failed to convert plot {key} to figure: {e}")
                        # Fall back to sending raw data
                        plot_data_dict[key] = {
                            "key": plot_data.key,
                            "plot_type": plot_data.plot_type,
                            "data": plot_data.data,
                            "caption": plot_data.caption,
                            "width": plot_data.width,
                            "height": plot_data.height,
                            "metadata": plot_data.metadata,
                        }

            logger.info(f"Extracted {len(plot_data_dict)} plots from database")
            return plot_data_dict
        except Exception as e:
            logger.error(f"Failed to extract plot data from database: {e}")
            return {}

    def _extract_table_data_from_db(self) -> Dict[str, Any]:
        """
        Extract all table data from the database and return as a dictionary.

        Returns:
            Dictionary mapping table keys to their data
        """
        try:
            table_keys = self.one_doc.db_manager.list_tables()
            table_data_dict = {}

            for key in table_keys:
                table_data = self.one_doc.db_manager.get_table(key)
                if table_data:
                    # Convert TableData model to dict for JSON serialization
                    # Keep cells as array to match frontend interface
                    table_data_dict[key] = {
                        "key": table_data.key,
                        "caption": table_data.caption,
                        "columns": [{"name": col.name, "data_type": col.data_type} for col in table_data.columns],
                        "cells": [
                            {"row_index": cell.row_index, "column_name": cell.column_name, "value": cell.value}
                            for cell in table_data.cells
                        ],
                        "show_index_default": table_data.show_index_default,
                        "default_sort": (
                            {
                                "column_name": table_data.default_sort.column_name,
                                "ascending": table_data.default_sort.ascending,
                            }
                            if table_data.default_sort
                            else None
                        ),
                        "default_filter": (
                            {
                                "column_name": table_data.default_filter.column_name,
                                "pattern": table_data.default_filter.pattern,
                                "is_regex": table_data.default_filter.is_regex,
                            }
                            if table_data.default_filter
                            else None
                        ),
                        "metadata": table_data.metadata,
                    }

            logger.info(f"Extracted {len(table_data_dict)} tables from database")
            return table_data_dict
        except Exception as e:
            logger.error(f"Failed to extract table data from database: {e}")
            return {}

    # -------------------------------
    # Static file export
    # -------------------------------
    def export_to_static_files(
        self,
        output_dir: pathlib.Path,
        embed_images: bool = True,
        include_frontend: bool = True,
        header_links: List[Dict[str, str]] | None = None,
    ) -> bool:
        """
        Export document to static JSON files for static web hosting.

        This method generates all the data files needed to render the document
        in a static web environment without requiring a WebSocket server.

        Args:
            output_dir: Directory to write the static files to
            embed_images: If True, embed images as base64 in the data files
            include_frontend: If True, copy the frontend HTML/JS files to output_dir

        Returns:
            True if successful, False otherwise

        Output structure:
            output_dir/
            ├── index.html          # Frontend (if include_frontend=True)
            ├── manifest.json       # Document manifest with section metadata
            ├── sections/
            │   ├── 0.json         # Section bundles (by index)
            │   ├── 1.json
            │   └── ...
            ├── images.json         # Embedded images (if embed_images=True)
            ├── plots.json          # Plot data for Plotly.js
            ├── tables.json         # Table data
            ├── three_d.json        # 3D asset metadata (key → camera/caption/sha)
            └── assets/3d/<key>.glb # Copied 3D assets (one per ThreeDData row)
        """

        try:
            output_dir = pathlib.Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Build AST and slice into sections
            logger.info("Building AST for static export...")
            ast = self.build_ast()
            manifest, sections = self.slice_sections(ast)
            _doc_id = manifest.get("docId") or self._infer_doc_id()

            # Stamp the manifest with the same `published_at` /
            # `paradoc_version` the BundleManifest carries — frontend
            # uses it for per-docId IndexedDB invalidation:
            # `fetchManifest` compares the fresh value to the cached
            # one and wipes manifests / sections / images / plots /
            # tables / 3d-meta entries scoped to this doc when they
            # differ. Without this, a rebuilt bundle keeps serving
            # last week's AST out of the visitor's IndexedDB.
            from datetime import datetime, timezone

            from paradoc.docstore._git import extract as _git_extract, find_repo_root
            from paradoc.docstore.manifest import _detect_paradoc_version

            now = datetime.now(timezone.utc).isoformat()
            manifest.setdefault("published_at", now)
            manifest.setdefault("paradoc_version", _detect_paradoc_version())

            # Git provenance — mirrors BundleManifest.git so the SPA's
            # AboutModal can display "branch@short_sha" + commit + dirty
            # status in static (embed) mode where there's no /api/info
            # to call. Sourced from the project's source_dir (same
            # convention as Document._write_bundle_artifacts) so the
            # provenance reflects the project repo, not paradoc itself.
            if "git" not in manifest:
                try:
                    source_dir = getattr(self.one_doc, "source_dir", None)
                    search_from = source_dir if source_dir else output_dir.parent
                    repo = find_repo_root(search_from)
                    if repo is not None:
                        g = _git_extract(repo)
                        if g is not None:
                            manifest["git"] = g.to_dict()
                except Exception as exc:
                    logger.warning("git provenance extract failed: %s", exc)

            # Create sections directory
            sections_dir = output_dir / "sections"
            sections_dir.mkdir(exist_ok=True)

            # Write manifest
            manifest_path = output_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"Wrote manifest to {manifest_path}")

            # Write sections (image files are copied separately below
            # so the frontend can lazy-fetch each one via <img src> rather
            # than waiting on a 10MB images.json on the critical path).
            for bundle in sections:
                sec = bundle["section"]
                idx = sec.get("index", 0)
                section_path = sections_dir / f"{idx}.json"
                section_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.debug(f"Wrote section {idx} to {section_path}")

            logger.info(f"Wrote {len(sections)} sections to {sections_dir}")

            # Copy image files into the static bundle at their markdown-
            # referenced relative paths so resolveAssetUrl can construct
            # `<basePath>/<path>` directly. Replaces the legacy bulk
            # images.json (base64 dict) which gated the React render on
            # a ~10MB upfront fetch — see plan/v1/notes_frontend_render_pipelines.md.
            if embed_images:
                self._export_images_for_static(output_dir, sections)

            # Extract and write plot data
            plot_data_dict = self._extract_plot_data_from_db()
            if plot_data_dict:
                plots_path = output_dir / "plots.json"
                plots_path.write_text(json.dumps(plot_data_dict, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info(f"Wrote {len(plot_data_dict)} plots to {plots_path}")

            # Extract and write table data
            table_data_dict = self._extract_table_data_from_db()
            if table_data_dict:
                tables_path = output_dir / "tables.json"
                tables_path.write_text(json.dumps(table_data_dict, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info(f"Wrote {len(table_data_dict)} tables to {tables_path}")

            # Copy 3D assets + metadata. WS/REST docstore modes serve these
            # via the server API; static-web has no server, so we ship the
            # GLBs alongside the JSON and let the frontend fetch by URL.
            self._export_three_d_assets_for_static(output_dir)

            # Camera presets. ThreeDRenderer fetches `assets/presets.json`
            # on mount; without it the renderer falls back to a single
            # hardcoded `iso_3` and the canvas can't frame the model.
            self._export_presets_for_static(output_dir)

            # Copy frontend files if requested
            if include_frontend:
                self._copy_frontend_for_static(output_dir)
                self._inject_static_runtime_config(
                    output_dir, header_links=header_links or None,
                )

            # Bundle-files manifest for the static-mode "Bundle files"
            # panel. REST mode hits the server's
            # /api/docs/{id}/manifest/files endpoint; static-served
            # bundles have no server to query, so we enumerate every
            # shipped file here and write the same JSON shape the
            # backend would emit. Walk after the frontend has been
            # extracted so the index also covers the SPA assets and
            # the user can see exactly what nginx is serving. Excludes
            # the manifest_files.json itself to keep the list stable
            # across re-runs (otherwise the file would grow / shrink
            # depending on whether the prior export wrote it).
            self._export_bundle_files_manifest(output_dir)

            logger.info(f"Successfully exported static files to {output_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to export static files: {e}", exc_info=True)
            return False

    def _export_bundle_files_manifest(self, output_dir: pathlib.Path) -> None:
        """Write `manifest_files.json` with every file under `output_dir`.

        Mirrors the REST-mode `/api/docs/{id}/manifest/files` payload so
        the frontend's BundleFilesModal can use the same `{files: [
        {rel_path, size, content_type}]}` shape in both modes — no
        separate code path to maintain.
        """
        import mimetypes

        out_path = output_dir / "manifest_files.json"
        entries: list[dict] = []
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(output_dir).as_posix()
            # Skip the manifest itself so re-runs are idempotent — the
            # list shouldn't shift just because a previous export
            # left a `manifest_files.json` behind.
            if rel == "manifest_files.json":
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            ctype, _ = mimetypes.guess_type(rel)
            entries.append(
                {"rel_path": rel, "size": int(size), "content_type": ctype or ""}
            )
        doc_id = self.one_doc.source_dir.name or "doc"
        out_path.write_text(
            json.dumps({"doc_id": doc_id, "files": entries}, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Wrote {len(entries)} bundle file entries to {out_path}")

    def _copy_frontend_for_static(self, output_dir: pathlib.Path):
        """
        Copy frontend files for static hosting.

        Args:
            output_dir: Directory to copy frontend files to
        """
        import zipfile

        # Get the frontend.zip from paradoc resources
        frontend_zip = pathlib.Path(__file__).parent.parent.parent / "frontend" / "resources" / "frontend.zip"

        if not frontend_zip.exists():
            logger.warning(f"Frontend zip not found at {frontend_zip}, skipping frontend copy")
            return

        try:
            # Extract frontend.zip to output directory
            with zipfile.ZipFile(frontend_zip) as archive:
                archive.extractall(output_dir)
            logger.info(f"Extracted frontend to {output_dir}")
        except Exception as e:
            logger.warning(f"Failed to extract frontend: {e}")

    def _export_presets_for_static(self, output_dir: pathlib.Path) -> None:
        """Write `assets/presets.json` next to the 3D assets.

        `compile()` routes this through `_write_bundle_artifacts`, but the
        static export goes straight from `build_ast` to the JSON dump and
        skipped this step — leaving the frontend with a 404 and a single
        hardcoded fallback preset that can't frame arbitrary models.
        """
        from paradoc.camera.presets import export_presets_json, load_camera_presets

        try:
            paradoc_toml = self.one_doc.source_dir / "paradoc.toml"
            presets = load_camera_presets(paradoc_toml if paradoc_toml.exists() else None)
            export_presets_json(presets, output_dir / "assets" / "presets.json")
            logger.info(f"Wrote {len(presets)} camera preset(s) to {output_dir / 'assets' / 'presets.json'}")
        except Exception as exc:
            logger.warning(f"Failed to export presets.json: {exc}")

    def _export_images_for_static(
        self, output_dir: pathlib.Path, sections: List[Dict[str, Any]]
    ) -> None:
        """Copy referenced image files into the static bundle.

        Each `<img src>` in the markdown maps to a path like
        ``_images/foo.png`` or ``files/figs/cad.png``. The frontend's
        ``resolveAssetUrl`` in static mode just appends that path to the
        base directory, so we copy the source file to exactly that
        relative location under ``output_dir``. Image resolution reuses
        the same source-dir / dist-dir / build-dir search strategy that
        the legacy ``_embed_images_in_bundle`` used.
        """
        import shutil

        all_paths: List[Dict[str, str]] = []
        for bundle in sections:
            doc = bundle.get("doc", {})
            blocks = doc.get("blocks", [])
            all_paths.extend(self._extract_images_with_source(blocks))

        if not all_paths:
            return

        # Dedupe by (normalized_path, source_dir) — the same image can
        # be referenced from multiple sections; we only need to copy it
        # once per destination path.
        seen: set = set()
        copied = skipped = 0
        for img_info in all_paths:
            img_path = img_info["path"]
            source_dir = img_info.get("source_dir")
            normalized_path = img_path.replace("./", "", 1) if img_path.startswith("./") else img_path
            if normalized_path in seen:
                continue
            seen.add(normalized_path)

            resolved: pathlib.Path | None = None
            if source_dir:
                source_dir_path = pathlib.Path(source_dir)
                for variant in (img_path, normalized_path):
                    candidate = source_dir_path / variant
                    if candidate.exists() and candidate.is_file():
                        resolved = candidate
                        break
            if resolved is None:
                for base in (self.one_doc.dist_dir, self.one_doc.build_dir, self.one_doc.source_dir):
                    for variant in (img_path, normalized_path):
                        candidate = base / variant
                        if candidate.exists() and candidate.is_file():
                            resolved = candidate
                            break
                        # Recursive fallback by filename — matches the
                        # legacy embed path so we don't regress on docs
                        # that rely on sphinx-style `_images/<name>` refs
                        # where the source file lives elsewhere on disk.
                        filename = pathlib.Path(variant).name
                        for found in base.rglob(filename):
                            if found.is_file():
                                resolved = found
                                break
                        if resolved is not None:
                            break
                    if resolved is not None:
                        break

            if resolved is None:
                logger.warning(
                    f"Could not find image file: {img_path} (source_dir: {source_dir})"
                )
                skipped += 1
                continue

            dest = output_dir / normalized_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copyfile(resolved, dest)
                copied += 1
            except Exception as exc:
                logger.warning(f"image copy {resolved} → {dest} failed: {exc}")
                skipped += 1

        logger.info(f"Copied {copied} images into static bundle ({skipped} skipped)")

    def _export_three_d_assets_for_static(self, output_dir: pathlib.Path) -> None:
        """Copy ThreeDData GLBs into the static bundle + write three_d.json.

        The DbManager carries `glb_path` strings that are usually bundle-
        relative (`assets/3d/<key>.glb` written by figure-source filters)
        but legacy / external producers may register paths relative to
        the source dir or as absolute paths. Try several base dirs to
        locate the GLB on disk; skip with a warning if none resolve.
        """
        import shutil

        try:
            keys = self.one_doc.db_manager.list_three_d()
        except Exception as exc:
            logger.warning(f"list_three_d() failed: {exc}; skipping 3D asset export")
            return
        if not keys:
            return

        assets_dir = output_dir / "assets" / "3d"
        assets_dir.mkdir(parents=True, exist_ok=True)

        manifest: Dict[str, Dict[str, Any]] = {}

        search_bases: List[pathlib.Path] = []
        for cand in (
            self.one_doc.build_dir,
            self.one_doc.source_dir,
            getattr(self.one_doc.source_dir, "parent", None),
            self.one_doc.dist_dir,
        ):
            if cand is None:
                continue
            p = pathlib.Path(cand).resolve()
            if p not in search_bases:
                search_bases.append(p)

        copied = skipped = 0
        for key in keys:
            try:
                meta = self.one_doc.db_manager.get_three_d(key)
            except Exception as exc:
                logger.warning(f"get_three_d({key!r}) failed: {exc}; skipping")
                skipped += 1
                continue
            if meta is None:
                logger.warning(f"3d key {key!r} listed but get_three_d returned None")
                skipped += 1
                continue

            src = pathlib.Path(meta.glb_path)
            resolved: pathlib.Path | None = None
            if src.is_absolute():
                if src.exists():
                    resolved = src
            else:
                for base in search_bases:
                    candidate = (base / src).resolve()
                    if candidate.exists():
                        resolved = candidate
                        break

            if resolved is None:
                logger.warning(
                    f"3d asset {key!r}: glb_path {meta.glb_path!r} not found "
                    f"(searched: {[str(b) for b in search_bases]})"
                )
                skipped += 1
                continue

            dest = assets_dir / f"{key}.glb"
            try:
                shutil.copyfile(resolved, dest)
            except Exception as exc:
                logger.warning(f"copy {resolved} → {dest} failed: {exc}; skipping")
                skipped += 1
                continue

            # Optional poster PNG sibling: the producer may have rendered
            # a raster preview alongside the GLB (e.g. via pygfx
            # offscreen). Two sources, in order: an explicit `image_path`
            # in the metadata dict, then a same-name `.png` next to the
            # GLB. If found, copy as `<key>.png` and record the relative
            # URL in the manifest so the frontend can use it as a poster.
            poster_src: pathlib.Path | None = None
            meta_image = (meta.metadata or {}).get("image_path") if hasattr(meta, "metadata") else None
            if meta_image:
                im_path = pathlib.Path(meta_image)
                if im_path.is_absolute() and im_path.exists():
                    poster_src = im_path
                else:
                    for base in search_bases:
                        cand = (base / im_path).resolve()
                        if cand.exists():
                            poster_src = cand
                            break
            if poster_src is None:
                sibling = resolved.with_suffix(".png")
                if sibling.exists():
                    poster_src = sibling

            poster_url: str | None = None
            if poster_src is not None:
                poster_dest = assets_dir / f"{key}.png"
                try:
                    shutil.copyfile(poster_src, poster_dest)
                    poster_url = f"assets/3d/{key}.png"
                except Exception as exc:
                    logger.warning(f"poster copy {poster_src} → {poster_dest} failed: {exc}")

            manifest[key] = {
                "key": key,
                "format": meta.format or "glb",
                "camera_pos": meta.camera_pos or "iso_3",
                "caption": meta.caption or "",
                "sha256": meta.sha256 or "",
                "size": meta.size or dest.stat().st_size,
                "source_type": meta.source_type or "",
            }
            if poster_url is not None:
                manifest[key]["image_path"] = poster_url

            # FEA artefact bundle: the writer ships a sibling directory
            # next to the mesh GLB (`fea.manifest.json`, `fea.<field>.bin`,
            # etc.) that drives the streaming-FEA viewer. Copy the whole
            # directory under `assets/3d/<key>/` so paradoc-serve can
            # expose it via the doc-files endpoint and the frontend's
            # `load_fea_streaming.ts` mount path can hit it. Recorded in
            # the three_d manifest as `fea_bundle_dir` so the frontend
            # knows to dispatch to the artefact path instead of plain
            # `mountViewer`.
            if (meta.source_type or "") == "fea_artefact_bundle":
                bundle_src = resolved.parent
                bundle_dest = assets_dir / key
                try:
                    if bundle_dest.exists():
                        shutil.rmtree(bundle_dest)
                    shutil.copytree(bundle_src, bundle_dest)
                    bundle_url = f"assets/3d/{key}"
                    manifest[key]["fea_bundle_dir"] = bundle_url
                    manifest[key]["fea_manifest_path"] = f"{bundle_url}/fea.manifest.json"
                except Exception as exc:
                    logger.warning(
                        f"FEA artefact bundle copy {bundle_src} → {bundle_dest} failed: {exc}"
                    )

            # Mode-view row: share the canonical bundle's files (no
            # extra copy — that's the whole point of the artefact
            # design) and surface `fea_bundle_key` + `fea_mode_index`
            # so the renderer can build a manifest URL pointing at
            # the bundle's directory and ask the embed to render the
            # right mode. Bundle key + mode index live in the row's
            # ``metadata`` dict; the adapy bake writes them when it
            # registers per-mode views alongside the canonical bundle
            # row.
            if (meta.source_type or "") == "fea_artefact_bundle_mode_view":
                md = meta.metadata if isinstance(meta.metadata, dict) else {}
                bundle_key = md.get("fea_bundle_key")
                mode_idx = md.get("fea_mode_index")
                if bundle_key:
                    bundle_url = f"assets/3d/{bundle_key}"
                    manifest[key]["fea_bundle_dir"] = bundle_url
                    manifest[key]["fea_manifest_path"] = f"{bundle_url}/fea.manifest.json"
                    manifest[key]["fea_bundle_key"] = bundle_key
                if isinstance(mode_idx, int):
                    manifest[key]["fea_mode_index"] = mode_idx
            copied += 1

        if manifest:
            three_d_path = output_dir / "three_d.json"
            three_d_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(
                f"Wrote {copied} 3D asset(s) → {assets_dir} (skipped {skipped}) and {three_d_path}"
            )
        elif skipped:
            logger.info(f"3D export: {skipped} key(s) skipped, none successfully copied")

    def _inject_static_runtime_config(
        self,
        output_dir: pathlib.Path,
        header_links: List[Dict[str, str]] | None,
    ) -> None:
        """Seed ``window.__PARADOC_CONFIG__`` in the bundled ``index.html``.

        Always sets ``transport: 'static'`` so the React app picks the
        ``StaticTransport`` (relative-URL fetches for plots/tables/3D)
        instead of trying to open a WebSocket to a non-existent server.
        Optionally also seeds ``headerLinks`` for host-supplied nav.

        The bundled frontend ``index.html`` is a single self-contained
        file; we splice an inline script right after the first ``<head>``
        tag so the config is set before any module script executes.
        """
        index_path = output_dir / "index.html"
        if not index_path.exists():
            logger.warning("Cannot inject runtime config — %s not found.", index_path)
            return

        cfg: Dict[str, Any] = {"transport": "static"}

        if header_links:
            clean_links: List[Dict[str, str]] = []
            for raw in header_links:
                if not isinstance(raw, dict) or "label" not in raw or "href" not in raw:
                    logger.warning("Skipping malformed header link: %r", raw)
                    continue
                entry: Dict[str, str] = {"label": str(raw["label"]), "href": str(raw["href"])}
                if raw.get("target"):
                    entry["target"] = str(raw["target"])
                if raw.get("rel"):
                    entry["rel"] = str(raw["rel"])
                clean_links.append(entry)
            if clean_links:
                cfg["headerLinks"] = clean_links

        payload = json.dumps(cfg, ensure_ascii=False)
        snippet = (
            "<script>"
            "(function(){var c=window.__PARADOC_CONFIG__=window.__PARADOC_CONFIG__||{};"
            f"Object.assign(c,{payload});"
            "})();"
            "</script>"
        )

        html = index_path.read_text(encoding="utf-8")
        head_open = html.find("<head")
        if head_open == -1:
            logger.warning("Cannot inject runtime config — no <head> tag in %s.", index_path)
            return
        head_close = html.find(">", head_open)
        if head_close == -1:
            logger.warning("Cannot inject runtime config — malformed <head> in %s.", index_path)
            return
        new_html = html[: head_close + 1] + snippet + html[head_close + 1 :]
        index_path.write_text(new_html, encoding="utf-8")
        logger.info(
            "Injected runtime config (transport=static, %d headerLinks) into %s",
            len(cfg.get("headerLinks", [])),
            index_path,
        )
