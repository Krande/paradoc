import pathlib
import shutil

import pypandoc

from paradoc import OneDoc
from paradoc.config import logger
from paradoc.utils import copy_figures_to_dist

THIS_DIR = pathlib.Path(__file__).parent


class HTMLExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def _build_styled_html(self, include_navbar: bool = True) -> str:
        one = self.one_doc

        md_main_str = "\n\n".join([md.read_built_file() for md in one.md_files_main])
        app_str = """\n\n\\appendix\n\n"""
        md_app_str = "\n\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str

        html_str = pypandoc.convert_text(
            combined_str,
            one.FORMATS.HTML,
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

        js_script = ""
        if include_navbar:
            js_script = "<script>\n" + open(THIS_DIR / "js/navbar.js", "r").read() + "\n</script>"

        app_head_text = ""
        if len(one.md_files_app) > 0:
            app_file1 = open(one.md_files_app[0].path, "r").read()
            for line in app_file1.splitlines():
                if line.startswith("# "):
                    app_head_text = line[2:]
                    break

        styled_html = f"""<html>
        <head>
        <meta name=\"data-appendix-start\" content=\"{app_head_text}\">
        <link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\">
        <script type=\"text/javascript\" async
            src=\"https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js\">
        </script>
        {js_script}
        </head>
        <body>
        <div class=\"content\">
        {html_str}
        </div>
        </body>
        </html>"""
        return styled_html

    def export(self, dest_file, include_navbar=True):
        one = self.one_doc

        # Ensure figures are copied
        copy_figures_to_dist(one, dest_file.parent)

        styled_html = self._build_styled_html(include_navbar=include_navbar)

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(styled_html)

        style_css_file = one.source_dir / "style.css"
        if style_css_file.exists():
            shutil.copy(style_css_file, dest_file.parent / "style.css")
        else:
            if self.one_doc.use_default_html_style:
                from paradoc.common import MY_DEFAULT_HTML_CSS

                shutil.copy(MY_DEFAULT_HTML_CSS, dest_file.parent / "style.css")

        print(f'Successfully exported HTML to "{dest_file}"')

    def send_to_frontend(
        self,
        host: str = "localhost",
        port: int = 13579,
        include_navbar: bool = False,
        assets_mode: str = "localstorage",
    ) -> bool:
        """
        Build the HTML and send it to the running frontend via WebSocket.

        When assets_mode == "http": start a lightweight HTTP static server that serves the
        dist directory and inject a <base> tag so relative URLs resolve to that server.

        When assets_mode == "localstorage": package the HTML and all referenced local assets
        (images, CSS) into a JSON bundle and send over WebSocket; the frontend will cache
        assets in localStorage and render from memory without reading OS files. This is ideal
        for development.

        Returns True if the message was sent successfully, False otherwise.
        """
        one = self.one_doc

        # Ensure WebSocket server is running in background
        ws_ready = False
        try:
            from paradoc.frontend.ws_server import ensure_ws_server  # lazy import
            ws_ready = ensure_ws_server(host=host, port=port)
            if not ws_ready:
                print(
                    "Paradoc: WebSocket server not running. Install 'websockets' and try again.\n"
                    "e.g. pip install websockets (or add to pixi env), then start the frontend and retry."
                )
        except Exception as e:
            logger.error(f"Could not ensure WebSocket server is running: {e}")
            print("Paradoc: Failed to initialize WebSocket server. See logs above.")

        try:
            # Lazy import so dependency is optional for users not using the WS flow
            import websocket  # type: ignore
        except Exception:
            # Provide a helpful error without crashing callers
            print("websocket-client is not installed. Please add it to your environment to use send_to_frontend().")
            return False

        # Build HTML
        html = self._build_styled_html(include_navbar=include_navbar)

        payload: str
        if assets_mode == "http":
            # Legacy/dev option: serve via HTTP and add <base>
            http_port = port + 1
            try:
                from paradoc.frontend.http_server import ensure_http_server  # lazy import
                # Make sure dist_dir exists
                one.dist_dir.mkdir(exist_ok=True, parents=True)

                # Ensure style.css is available under dist_dir for the HTML to reference
                style_css_file = one.source_dir / "style.css"
                try:
                    if style_css_file.exists():
                        shutil.copy(style_css_file, one.dist_dir / "style.css")
                    else:
                        if one.use_default_html_style:
                            from paradoc.common import MY_DEFAULT_HTML_CSS
                            shutil.copy(MY_DEFAULT_HTML_CSS, one.dist_dir / "style.css")
                except Exception:
                    # Non-fatal
                    pass

                _ = ensure_http_server(host=host, port=http_port, directory=str(one.dist_dir))
                # Brief readiness wait to avoid race where browser fetches before server listens
                try:
                    import socket, time
                    deadline = time.time() + 2.0  # up to 2 seconds
                    while time.time() < deadline:
                        try:
                            with socket.create_connection((host, http_port), timeout=0.2):
                                break
                        except Exception:
                            time.sleep(0.05)
                except Exception:
                    pass
            except Exception:
                # If HTTP server cannot be started, we still try to send HTML; images may fail to load.
                pass

            base_tag = f'<base href="http://{host}:{http_port}/">'
            if "<head>" in html:
                payload = html.replace("<head>", f"<head>\n{base_tag}")
            else:
                payload = base_tag + html
        else:
            # LocalStorage bundle mode
            try:
                import json, re, base64, mimetypes
            except Exception:
                print("Failed to import stdlib for bundling assets.")
                return False

            # Collect asset paths from HTML (img src and link rel=stylesheet)
            img_paths = []
            for m in re.finditer(r'<img[^>]+src=[\"\']([^\"\'>]+)', html, flags=re.IGNORECASE):
                img_paths.append(m.group(1))
            css_paths = []
            for m in re.finditer(r'<link[^>]+rel=[\"\']stylesheet[\"\'][^>]*href=[\"\']([^\"\'>]+)', html, flags=re.IGNORECASE):
                css_paths.append(m.group(1))

            # Resolve and read files
            def is_http_url(p: str) -> bool:
                return p.startswith("http://") or p.startswith("https://") or p.startswith("data:")

            assets = []
            def read_file_bytes(path_str: str) -> tuple[str | None, bytes | None]:
                p = pathlib.Path(path_str)
                # Try relative to dist_dir first, then source_dir
                candidates = [one.dist_dir / p, one.source_dir / p]
                for c in candidates:
                    try:
                        if c.exists() and c.is_file():
                            return str(p).replace('\\', '/'), c.read_bytes()
                    except Exception:
                        pass
                # Also try raw absolute
                try:
                    if p.exists() and p.is_file():
                        return str(p.name), p.read_bytes()
                except Exception:
                    pass
                return None, None

            # Style text: collect inline content of style.css (first hit) for easier injection
            styles_text: list[dict] = []

            for href in css_paths:
                if is_http_url(href):
                    continue
                key, data = read_file_bytes(href)
                if key and data is not None:
                    # capture css text; still also add as asset, but UI may inline it
                    try:
                        styles_text.append({"path": key, "text": data.decode("utf-8", errors="ignore")})
                    except Exception:
                        pass
                    mime, _ = mimetypes.guess_type(key)
                    mime = mime or "text/css"
                    b64 = base64.b64encode(data).decode("ascii")
                    assets.append({"path": key, "mime": mime, "b64": b64})

            for src in img_paths:
                if is_http_url(src):
                    continue
                key, data = read_file_bytes(src)
                if key and data is not None:
                    mime, _ = mimetypes.guess_type(key)
                    # Default binary type if unknown
                    mime = mime or "application/octet-stream"
                    b64 = base64.b64encode(data).decode("ascii")
                    assets.append({"path": key, "mime": mime, "b64": b64})

            bundle = {"kind": "html_bundle", "html": html, "assets": assets, "styles": styles_text}
            try:
                payload = json.dumps(bundle)
            except Exception as e:
                print(f"Failed to encode HTML bundle: {e}")
                return False

        ws_url = f"ws://{host}:{port}"

        try:
            ws = websocket.create_connection(ws_url, timeout=3)
        except Exception as e:
            print(f"Could not connect to frontend WebSocket at {ws_url}: {e}")
            return False

        try:
            ws.send(payload)
            return True
        except Exception as e:
            print(f"Failed to send to frontend over WebSocket: {e}")
            return False
        finally:
            try:
                ws.close()
            except Exception:
                pass
