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

    def send_to_frontend(self, host: str = "localhost", port: int = 13579, include_navbar: bool = False) -> bool:
        """
        Build the HTML and send it to the running frontend via WebSocket.

        Also ensures that external assets (images, CSS, etc.) referenced by the HTML
        are resolvable by starting a lightweight HTTP static server that serves the
        working distribution directory. A <base> tag is injected to make relative URLs
        resolve against that HTTP server.

        Returns True if the message was sent successfully, False otherwise.
        """
        one = self.one_doc

        # Ensure WebSocket server is running in background
        try:
            from paradoc.frontend.ws_server import ensure_ws_server  # lazy import
            ensure_ws_server(host=host, port=port)
        except Exception as e:
            logger.error(f"Could not ensure WebSocket server is running: {e}")
            pass

        # Ensure HTTP static server is running to serve assets from dist_dir
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

            ensure_http_server(host=host, port=http_port, directory=str(one.dist_dir))
        except Exception:
            # If HTTP server cannot be started, we still try to send HTML; images may fail to load.
            pass

        try:
            # Lazy import so dependency is optional for users not using the WS flow
            import websocket  # type: ignore
        except Exception:
            # Provide a helpful error without crashing callers
            print("websocket-client is not installed. Please add it to your environment to use send_to_frontend().")
            return False

        # Build HTML and inject <base> so browsers resolve relative asset URLs via HTTP server
        html = self._build_styled_html(include_navbar=include_navbar)
        base_tag = f'<base href="http://{host}:{http_port}/">'
        if "<head>" in html:
            html = html.replace("<head>", f"<head>\n{base_tag}")
        else:
            # Fallback: prepend base to start of document
            html = base_tag + html

        ws_url = f"ws://{host}:{port}"

        try:
            ws = websocket.create_connection(ws_url, timeout=3)
        except Exception as e:
            print(f"Could not connect to frontend WebSocket at {ws_url}: {e}")
            return False

        try:
            ws.send(html)
            return True
        except Exception as e:
            print(f"Failed to send HTML to frontend over WebSocket: {e}")
            return False
        finally:
            try:
                ws.close()
            except Exception:
                pass
