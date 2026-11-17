# Function History Tracker

Find the commits that changed a function in a local Git repository. The report shows up to five commits, with the commit subject, the function diff, and test files changed in the same commit.

## Requirements

- Python 3.9 or later
- Git available on your command path

The tracker uses Python's standard library and runs locally.

## Run the demo

From the tracker checkout, clone the bundled demo into a new directory and run the tracker:

```sh
git clone delivery-demo.bundle delivery-demo
python trace_history.py ./delivery-demo shipping.py estimate_delivery
```

The bundle preserves the demo's three original commits. If you already have the demo checked out in `delivery-demo`, start with the Python command.

The report starts with `b3c4d1c`, where delivery switched from calendar days to weekdays and `tests/test_shipping.py` was added. It then shows `237fc5c`, where the function was introduced. The README-only commit is excluded.

To verify the demo tests:

```sh
cd delivery-demo
python -B -m unittest discover -s tests -v
```

## Trace a function in your own repository

```sh
python trace_history.py path/to/repository path/to/file.py function_name
```

Use a file path relative to the target repository's root. The tracker starts at `HEAD`, so the file and function need to exist in the current commit. Function detection depends on Git's `git log -L` matching rules. History across function renames or moves between files falls outside this release's supported scope.

The test list uses common directory and filename conventions. It shows which test files changed in the same commit. Use the diff and commit subject to interpret the change.
