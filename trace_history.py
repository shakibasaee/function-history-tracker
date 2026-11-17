"""Show the Git history of a function in a local repository."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from difflib import SequenceMatcher, unified_diff
from pathlib import Path, PurePosixPath
from typing import NamedTuple


class Definition(NamedTuple):
    source: list[str]
    fingerprint: str
    structure: tuple[str, ...]
    start: int


class Predecessor(NamedTuple):
    filename: str
    name: str
    definition: Definition
    similarity: float
    exact: bool

    def evidence(self) -> str:
        if self.exact:
            return "exact syntax-tree match after ignoring the function name"
        return f"{self.similarity:.1%} syntax-tree similarity after ignoring the function name"


class Change(NamedTuple):
    commit: str
    subject: str
    diff: str
    evidence: tuple[str, ...] = ()


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


def python_definitions(git: list[str], revision: str, filename: str) -> dict[str, Definition]:
    try:
        source = read_git([*git, "show", f"{revision}:{filename}"])
    except subprocess.CalledProcessError:
        # A file introduced by the current commit has no parent version.
        if read_git([*git, "ls-tree", revision, "--", filename]):
            raise
        return {}
    lines = source.split("\n")
    definitions = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([node.lineno, *(item.lineno for item in node.decorator_list)])
            name = node.name
            node.name = ""
            structure = tuple(
                repr((type(child).__name__, [
                    (field, value) for field, value in ast.iter_fields(child)
                    if not isinstance(value, (ast.AST, list))
                ]))
                for child in ast.walk(node)
            )
            definitions[name] = Definition(
                lines[start - 1:node.end_lineno], ast.dump(node), structure, start
            )
    return definitions


def find_predecessors(
    git: list[str], parent: str, commit: str, current: Definition
) -> list[Predecessor]:
    changed = read_git([
        *git, "diff", "--name-only", "--no-renames", "--diff-filter=MDT", "-z",
        parent, commit, "--",
    ])
    matches = []
    for filename in changed.split("\0"):
        if not filename.endswith(".py"):
            continue
        try:
            before = python_definitions(git, parent, filename)
            after = python_definitions(git, commit, filename)
        except SyntaxError:
            continue
        for name, definition in before.items():
            if name in after:
                continue
            exact = definition.fingerprint == current.fingerprint
            similarity = 1.0
            if not exact:
                # Short functions have too little structure for approximate matching.
                if min(len(definition.structure), len(current.structure)) < 15:
                    continue
                similarity = SequenceMatcher(
                    None, definition.structure, current.structure, autojunk=False
                ).ratio()
                if similarity < 0.90:
                    continue
            matches.append(Predecessor(filename, name, definition, similarity, exact))
    matches.sort(key=lambda match: (not match.exact, -match.similarity, match.filename, match.name))
    if not matches:
        return []
    best = matches[0]
    return [
        match for match in matches
        if match.exact == best.exact and best.similarity - match.similarity <= 0.05
    ]


def python_history(
    git: list[str], revision: str, filename: str, name: str, current: Definition
) -> list[Change]:
    changes = []
    while len(changes) < 5:
        commits = read_git([
            *git, "log", "--first-parent", "--full-history", "--format=%H%x09%P%x09%s",
            revision, "--", filename,
        ])
        for line in commits.splitlines():
            commit, parents, subject = line.split("\t", 2)
            parent, _, other_parents = parents.partition(" ")
            previous = python_definitions(git, parent, filename).get(name) if parent else None
            old_file, old_name = filename, name
            evidence = ()
            if parent and previous is None:
                matches = find_predecessors(git, parent, commit, current)
                if len(matches) > 1:
                    evidence = (
                        f"History stops here. Multiple predecessors match {filename}::{name}.",
                        *(
                            f"  {match.filename}::{match.name} ({match.evidence()})"
                            for match in matches
                        ),
                    )
                    changes.append(Change(commit, subject, "", evidence))
                    return changes
                if matches:
                    match = matches[0]
                    old_file, old_name, previous = match.filename, match.name, match.definition
                    evidence = (
                        f"From {old_file}::{old_name}",
                        f"To   {filename}::{name}",
                        f"Match evidence: {match.evidence()}. The old definition disappeared.",
                    )

            if previous is None or previous.source != current.source:
                merged = []
                if other_parents and not evidence:
                    # Ask Git which commits introduced these lines through the merge.
                    end = current.start + len(current.source) - 1
                    merged = git_history(
                        git, f"{current.start},{end}:{filename}", f"{parent}..{commit}",
                        limit=5 - len(changes),
                    )
                if merged:
                    changes.extend(merged)
                else:
                    diff = unified_diff(
                        previous.source if previous else [],
                        current.source,
                        fromfile=f"a/{old_file}" if previous else "/dev/null",
                        tofile=f"b/{filename}",
                        lineterm="",
                    )
                    changes.append(Change(commit, subject, "\n".join(diff), evidence))
            elif old_file != filename:
                changes.append(Change(commit, subject, "", evidence))

            if previous is None or len(changes) == 5:
                return changes
            current = previous
            if (old_file, old_name) != (filename, name):
                revision, filename, name = parent, old_file, old_name
                break
        else:
            break
    return changes


def git_history(
    git: list[str], line_range: str, revision: str = "HEAD", limit: int = 5
) -> list[Change]:
    history = read_git([
        *git, "log", "--no-color", "--no-ext-diff", "--format=%x00%H %s",
        f"--max-count={limit}", "-L", line_range, revision,
    ])
    changes = []
    for record in history.split("\0")[1:]:
        header, _, diff = record.partition("\n")
        commit, _, subject = header.partition(" ")
        changes.append(Change(commit, subject, diff.strip("\n")))
    return changes


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

    git = ["git", "--no-pager", "--literal-pathspecs", "-C", args.repository]
    error_context = f"Cannot open Git repository {args.repository!r}"
    try:
        root = read_git([*git, "rev-parse", "--show-toplevel"]).rstrip("\n")
        git = ["git", "--no-pager", "--literal-pathspecs", "-C", root]
        error_context = "The repository has no readable HEAD commit"
        revision = read_git([*git, "rev-parse", "--verify", "HEAD^{commit}"]).strip()
        error_context = f"Cannot find file {filename!r} in HEAD"
        if read_git([*git, "cat-file", "-t", f"HEAD:{filename}"]).strip() != "blob":
            parser.error(f"{filename!r} is not a regular file in HEAD")

        error_context = f"Cannot trace function {args.function!r} in {filename!r}"
        definition = None
        if filename.endswith(".py"):
            try:
                definition = python_definitions(git, revision, filename).get(args.function)
            except SyntaxError:
                pass
        try:
            line_range = f":{args.function}:{filename}"
            changes = (
                python_history(git, revision, filename, args.function, definition)
                if definition is not None
                else git_history(git, line_range, revision)
            )
        except SyntaxError:
            changes = git_history(git, line_range, revision)
        print(f"History for {args.function} in {filename}")
        for commit, subject, diff, evidence in changes:
            error_context = f"Cannot read changed files for commit {commit[:7]}"
            changed = read_git(
                [*git, "show", "--format=", "--name-only", "-z", commit, "--"]
            )
            tests = [name for name in changed.split("\0") if name and is_test_file(name)]
            print(f"\nCommit {commit[:7]}  {subject}")
            if evidence:
                print()
                for line in evidence:
                    print(line)
            if diff:
                print("\nFunction diff")
                print(diff)
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
