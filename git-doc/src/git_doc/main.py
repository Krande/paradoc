import requests
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

GITEA_API_URL = "http://localhost:3000/api/v1/repos/your_username/your_repo/contents"


class RefreshRequest(BaseModel):
    git_server: str
    directory: str | None = None


@app.get("/")
def read_root():
    return templates.TemplateResponse("index.html", {"request": {}})


@app.post("/refresh")
def refresh_content(data: RefreshRequest):
    # Fetch the directory structure from the Gitea server's "main" branch
    response = requests.get(f"{GITEA_API_URL}/{data.directory}", params={"ref": "main"})
    directories = response.json()

    # Use the provided function to convert markdown files to HTML
    markdown_files = [file["name"] for file in directories if file["type"] == "file" and file["name"].endswith(".md")]
    html_content = convert_directories_with_markdown_files_to_html(markdown_files)

    return {"content": html_content}


def convert_directories_with_markdown_files_to_html(markdown_files: list[str]) -> str:
    # This is a placeholder for your function that uses pandoc to convert markdown files to HTML
    return "<br>".join(markdown_files)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
