import json
import mimetypes
import pathlib
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import pypandoc

from paradoc.config import logger

if TYPE_CHECKING:
    from paradoc import OneDoc


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
            filters=["pandoc-crossref"],
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
                        import plotly

                        fig_json_str = plotly.io.to_json(fig)
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
