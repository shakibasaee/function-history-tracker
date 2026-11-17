# Function History Tracker

Find the commits that changed a function in a local Git repository, even after a Python function was renamed or moved. See the function diff, evidence for each match, and test files changed in the same commit.

## One-minute demo

From a fresh tracker checkout with Python 3.9+ and Git, run:

```sh
git clone delivery-demo.bundle delivery-demo
python trace_history.py ./delivery-demo fulfillment.py calculate_delivery_date
```

The function once lived at `shipping.py::estimate_delivery`. v1 finds the move commit. v2 follows the old name and file to find the earlier switch from calendar days to weekdays and the original implementation.

```text
3452a15  Move delivery date calculation into fulfillment
         shipping.py::estimate_delivery → fulfillment.py::calculate_delivery_date
         Exact syntax-tree match after ignoring the function name
b3c4d1c  Count only weekdays when estimating delivery
237fc5c  Estimate delivery in calendar days
```

See the [evaluation report](evaluation/README.md) for 15 reproducible cases from Click and Packaging, including misses.

## Trace a function in your own repository

```sh
python trace_history.py path/to/repository path/to/file.py function_name
```

Use a file path relative to the target repository's root. The tracker uses Python's standard library and reports up to five commits starting from the function at `HEAD`.

For top-level Python functions, the tracker follows the first parent to detect moves and uses Git line history to recover changes introduced through merges. When a definition disappears, it compares the removed definitions in changed Python files with the new definition. The report shows the old and new locations and either an exact syntax-tree match or a similarity score. Comparisons ignore the function name and formatting.

For longer definitions, approximate matching can follow a rename with a small code edit. It requires at least 15 syntax-tree nodes on each side and a score of at least 90%. Exact matches take priority. If multiple matches of the same kind are within five percentage points of the top score, the report lists them and stops at that commit. The score measures similarity in the code structure. Other inputs use Git's `git log -L` matching rules.

The test list uses common directory and filename conventions. It shows which test files changed in the same commit. Use the diff and commit subject to interpret the change.

## Run the tracker tests

```sh
python -B -m unittest discover -s tests -v
```

GitHub Actions runs the suite on pushes and pull requests on Linux and Windows.
