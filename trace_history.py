"""Show the Git history of a function in a local repository."""

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath


def read_git(command: list[str]) -> str:
    return subprocess.check_output(
        command, stderr=subprocess.PIPE, encoding="utf-8", errors="replace"
    )


def is_test_file(filename: str) -> bool:
    path = PurePosixPath(filename.lower())
    return (
        any(part in {"test", "tests", "__tests__"} for part in path.parts[:-1])
        or path.stem.startswith("test_")
        or path.stem.endswith(("_test", ".test", ".spec"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="path to the local Git repository")
    parser.add_argument("file", help="file path relative to the repository root")
    parser.add_argument("function", help="function name to trace")
    args = parser.parse_args()

    path = Path(args.file)
    if path.anchor or ".." in path.parts or not path.name:
        parser.error("the file must be a path relative to the repository root")
    if not args.function.strip():
        parser.error("the function name must not be empty")
    filename = path.as_posix()

    git = ["git", "--no-pager", "-C", args.repository]
    error_context = f"Cannot open Git repository {args.repository!r}"
    try:
        root = read_git([*git, "rev-parse", "--show-toplevel"]).rstrip("\n")
        git = ["git", "--no-pager", "-C", root]
        error_context = "The repository has no readable HEAD commit"
        read_git([*git, "rev-parse", "--verify", "HEAD^{commit}"])
        error_context = f"Cannot find file {filename!r} in HEAD"
        if read_git([*git, "cat-file", "-t", f"HEAD:{filename}"]).strip() != "blob":
            parser.error(f"{filename!r} is not a regular file in HEAD")

        error_context = f"Cannot trace function {args.function!r} in {filename!r}"
        history = read_git([
            *git, "log", "--no-color", "--no-ext-diff", "--format=%x00%H %s",
            "--max-count=5", "-L", f":{args.function}:{filename}",
        ])
        print(f"History for {args.function} in {filename}")
        for record in history.split("\0")[1:]:
            header, _, diff = record.partition("\n")
            commit, _, subject = header.partition(" ")
            error_context = f"Cannot read changed files for commit {commit[:7]}"
            changed = read_git(
                [*git, "show", "--format=", "--name-only", "-z", commit, "--"]
            )
            tests = [name for name in changed.split("\0") if name and is_test_file(name)]
            print(f"\nCommit {commit[:7]}  {subject}")
            print("\nFunction diff")
            print(diff.strip("\n"))
            print("\nTest files changed in this commit")
            if tests:
                for name in tests:
                    print(f"  {name}")
            else:
                print("  None")
    except subprocess.CalledProcessError as error:
        print(f"Error: {error_context}.", file=sys.stderr)
        if error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        return error.returncode
    except FileNotFoundError:
        print("Git was not found. Install Git and add it to PATH.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
