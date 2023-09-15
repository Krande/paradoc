import pathlib

import git
from dotenv import load_dotenv

load_dotenv()


def example_initializer(user_name: str, repo_name: str):
    try:
        # Path to the local directory
        repo_path = pathlib.Path(__file__).parent.parent.absolute() / "example"

        # Check if the directory is already a Git repository
        try:
            repo = git.Repo(repo_path)
        except git.InvalidGitRepositoryError:
            # Initialize a new git repository
            repo = git.Repo.init(repo_path)

        # Check if the Gitea remote is already added, if not, add it
        if "origin" not in [remote.name for remote in repo.remotes]:
            repo.create_remote("origin", f"http://localhost:3000/{user_name}/{repo_name}.git")

        # Stage all files
        repo.git.add(A=True)

        # Try to Commit the staged files if not done already
        try:
            repo.git.commit("-m", "Initial commit from example_initializer")
        except git.GitCommandError:
            pass

        # Push to the Gitea server
        repo.git.push("--set-upstream", "origin", "master")

    except git.GitCommandError as e:
        print(f"Error occurred: {e}")


if __name__ == '__main__':
    # Assumes you've already created the repository on your Gitea server
    example_initializer("krande", "git-doc")
