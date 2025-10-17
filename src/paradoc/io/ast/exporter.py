import json
import pathlib
from typing import Any, Dict, List, Tuple

import pypandoc

from paradoc import OneDoc
from paradoc.config import logger


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
        """Concatenate main and appendix md (with \appendix marker) and obtain Pandoc JSON AST."""
        one = self.one_doc

        md_main_str = "\n\n".join([md.read_built_file() for md in one.md_files_main])
        app_str = """\n\n\\appendix\n\n"""
        md_app_str = "\n\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str

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
        return ast

    @staticmethod
    def _header_text(inlines: List[Any]) -> str:
        # Extract plain text from a list of Pandoc inline elements
        parts: List[str] = []
        for item in inlines or []:
            t = item[0] if isinstance(item, list) and item else None
            if t == "Str" and len(item) >= 2:
                parts.append(item[1])
            elif t == "Space":
                parts.append(" ")
        return "".join(parts).strip()

    def slice_sections(self, ast: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Split the document into sections by top-level (level==1) headers.

        Returns (manifest, section_bundles)
        - manifest: { docId, sections: [{ id, title, level, index }] }
        - section_bundles: list of { section: meta, doc: { blocks: [...] } }
        """
        blocks = ast.get("blocks") or ast.get("pandoc-api-version") and ast.get("blocks")
        # Some Pandoc versions wrap under {"blocks": ...}; ensure we have a list
        if not isinstance(blocks, list):
            blocks = ast.get("blocks", [])

        sections: List[Dict[str, Any]] = []
        current: List[Any] = []
        current_meta: Dict[str, Any] | None = None
        section_index = -1

        def push_current():
            if current_meta is None:
                return
            sections.append({
                "section": current_meta,
                "doc": {"blocks": list(current)},
            })

        for blk in blocks:
            if isinstance(blk, list) and blk and blk[0] == "Header":
                # Pandoc JSON compact form: ["Header", level, [id, classes, kv], inlines]
                try:
                    level = int(blk[1])
                except Exception:
                    level = 1
                attrs = blk[2] if len(blk) > 2 else ["", [], []]
                inlines = blk[3] if len(blk) > 3 else []

                if level == 1:
                    # Finish previous
                    push_current()
                    current = []
                    section_index += 1
                    sec_id = ""
                    try:
                        sec_id = attrs[0] or f"sec-{section_index}"
                    except Exception:
                        sec_id = f"sec-{section_index}"
                    title = self._header_text(inlines)
                    current_meta = {"id": sec_id, "title": title or f"Section {section_index+1}", "level": level, "index": section_index}
            # Accumulate
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
                if isinstance(blk, list) and blk and blk[0] == "Header":
                    try:
                        attrs = blk[2] if len(blk) > 2 else ["", [], []]
                        inlines = blk[3] if len(blk) > 3 else []
                        maybe_id = attrs[0] if isinstance(attrs, list) and attrs else ""
                        if maybe_id:
                            sec_id = str(maybe_id)
                        title = self._header_text(inlines) or title
                    except Exception:
                        pass
                    break
            sections.append({
                "section": {"id": sec_id, "title": title, "level": 1, "index": 0},
                "doc": {"blocks": list(all_blocks)},
            })

        # Build manifest
        doc_id = self._infer_doc_id()
        manifest = {
            "docId": doc_id,
            "sections": [s["section"] for s in sections],
        }
        return manifest, sections

    def _infer_doc_id(self) -> str:
        # Best-effort doc id from folder name
        try:
            return self.one_doc.source_dir.name or "doc"
        except Exception:
            return "doc"

    # -------------------------------
    # WebSocket streaming
    # -------------------------------
    def send_to_frontend(self, host: str = "localhost", port: int = 13579) -> bool:
        """
        Build AST, slice it into sections, and stream manifest + sections over the
        Paradoc WebSocket broadcast server.
        """
        # Ensure WS background server is running
        try:
            from paradoc.frontend.ws_server import ensure_ws_server  # lazy import
            _ = ensure_ws_server(host=host, port=port)
        except Exception as e:
            logger.error(f"Could not ensure WebSocket server is running: {e}")
            # Continue; we might still connect to an external server

        try:
            import websocket  # type: ignore
        except Exception:
            print("websocket-client is not installed. Please add it to your environment to use ASTExporter.send_to_frontend().")
            return False

        # Build and slice
        ast = self.build_ast()
        manifest, sections = self.slice_sections(ast)

        # Ensure a static HTTP server is serving assets from dist_dir so relative image paths load in the SPA
        try:
            from paradoc.frontend.http_server import ensure_http_server  # lazy import
            http_port = int(port) + 1
            # Make sure dist_dir exists
            try:
                self.one_doc.dist_dir.mkdir(exist_ok=True, parents=True)
            except Exception:
                pass
            _ = ensure_http_server(host=host, port=http_port, directory=str(self.one_doc.dist_dir))
            # Advertise asset base to the frontend manifest so it can resolve relative URLs
            try:
                manifest["assetBase"] = f"http://{host}:{http_port}/"
            except Exception:
                logger.error("Could not advertise asset base to frontend manifest", exc_info=True)
                pass
        except Exception:
            # Non-fatal if HTTP server cannot be started; images may fail to load
            logger.error("Could not ensure HTTP server is running", exc_info=True)
            pass

        ws_url = f"ws://{host}:{port}"
        try:
            ws = websocket.create_connection(ws_url, timeout=3)
        except Exception as e:
            print(f"Could not connect to frontend WebSocket at {ws_url}: {e}")
            return False

        try:
            # Send manifest first
            ws.send(json.dumps({"kind": "manifest", "manifest": manifest}))
            # Then each section
            for bundle in sections:
                msg = {"kind": "ast_section", "section": bundle["section"], "doc": bundle["doc"]}
                ws.send(json.dumps(msg))
            return True
        except Exception as e:
            print(f"Failed to send AST to frontend over WebSocket: {e}")
            return False
        finally:
            try:
                ws.close()
            except Exception:
                pass
