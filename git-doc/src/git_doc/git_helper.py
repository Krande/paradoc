from gitdb.db import git


def get_all_files_from_a_git_repo(url):
    """Get all files from a git repository.

    Args:
        url (str): URL to the git repository.

    Returns:
        list: List of files in the git repository.
    """
    repo = git.Repo.clone_from(url, "temp")
    files = [item for item in repo.tree().traverse() if item.type == "blob"]
    return files
