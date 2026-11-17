"""Compare the v1 and current trackers on pinned upstream histories."""

import json
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


def run(*command, cwd=ROOT, check=True):
    return subprocess.run(
        command, cwd=cwd, check=check, capture_output=True, encoding="utf-8", errors="replace"
    )


def outcome(script, repository, case):
    result = run(sys.executable, str(script), str(repository), case["file"], case["function"],
                 check=False)
    if result.returncode:
        return f"error ({result.stderr.splitlines()[0] if result.stderr else result.returncode})"
    commits = re.findall(r"^Commit ([0-9a-f]+)\s", result.stdout, re.MULTILINE)
    return "found" if any(case["expected"].startswith(commit) for commit in commits) else "missed"


def main():
    cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="tracker-evaluation-") as folder:
        temp = Path(folder)
        baseline = temp / "v1.py"
        baseline.write_text(run("git", "show", "v1.0.0:trace_history.py").stdout, encoding="utf-8")
        repositories = {}
        for case in cases:
            upstream = case["repo"]
            if upstream not in repositories:
                clone = temp / upstream.split("/")[-1]
                print(f"Cloning {upstream}...", flush=True)
                run("git", "clone", "--quiet", "--no-checkout", f"https://github.com/{upstream}.git",
                    str(clone))
                repositories[upstream] = clone

        print("| Case | Expected commit | v1 | v2 |")
        print("|---|---|---|---|")
        totals = [0, 0]
        for case in cases:
            clone = repositories[case["repo"]]
            run("git", "checkout", "--quiet", "--detach", case["start"], cwd=clone)
            results = [outcome(script, clone, case) for script in [baseline, ROOT / "trace_history.py"]]
            for index, result in enumerate(results):
                totals[index] += result == "found"
            url = f'https://github.com/{case["repo"]}/commit/{case["expected"]}'
            print(f'| {case["label"]} | [`{case["expected"][:7]}`]({url}) | '
                  f'{results[0]} | {results[1]} |', flush=True)
        print(f"\nHits in the first five results: v1 {totals[0]}/{len(cases)}, "
              f"v2 {totals[1]}/{len(cases)}.")


if __name__ == "__main__":
    main()
