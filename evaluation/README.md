# Evaluation on real Git histories

v2 found the expected commit in the first five results for **14 of 15** cases. v1 found **11 of 15**. All three gains came from functions moved between files that continued to exist in the repository.

## Method

Each case pins a Click or Packaging checkout, a file and function at that checkout, and an earlier commit to find. I inspected the upstream diffs to verify the expected edits, original definitions, and moves. Both versions received the same inputs and had the same five-result limit. A case counts as found when the report contains the expected commit ID.

The sample is a handpicked set of regression cases. It includes related cases from the same refactor and some controls where the expected commit is the starting revision. The counts measure recovery on these examples. They do not measure false matches, runtime, or accuracy on an arbitrary repository.

## Results

| Case | Expected commit | v1 | v2 |
|---|---|---|---|
| Packaging layout move, earlier name annotation | [`ae891fd`](https://github.com/pypa/packaging/commit/ae891fd74d6dd4c6063bb04f2faeadaac6fc6313) | Found | Found |
| Packaging layout move, earlier wheel signature formatting | [`745bb0a`](https://github.com/pypa/packaging/commit/745bb0a763517a21422e74e936a24b043e8dc225) | Found | Found |
| Packaging function move, original base-release helper | [`3f4f5d4`](https://github.com/pypa/packaging/commit/3f4f5d46808f51709aba8341d4121f20752b3235) | Missed | Found |
| Packaging function move, original empty-range helper | [`3f4f5d4`](https://github.com/pypa/packaging/commit/3f4f5d46808f51709aba8341d4121f20752b3235) | Missed | Found |
| Packaging rename, earlier version formatting change | [`2c885fe`](https://github.com/pypa/packaging/commit/2c885fe91a54559e2382902dce28428ad2887be5) | Found | Found |
| Packaging rename with another definition removed | [`40d76fb`](https://github.com/pypa/packaging/commit/40d76fbedf22519d73229bc8c4c6a6dbfddea44e) | Found | Found |
| Packaging wheel parser, invalid-tag handling | [`c5b253b`](https://github.com/pypa/packaging/commit/c5b253b24ba5d4c242a73ff19b02ef0833ba5859) | Found | Found |
| Packaging source distribution parser, empty-name handling | [`84833cc`](https://github.com/pypa/packaging/commit/84833cc16be84bc7f1d9f64e2818afe0dd48aade) | Found | Found |
| Packaging wheel parser, regex changed outside the function | [`0625596`](https://github.com/pypa/packaging/commit/0625596e502163179b9a82796aee82c178efc16d) | Missed | Missed |
| Click layout move, earlier bytes support | [`970364d`](https://github.com/pallets/click/commit/970364db257039bd5fbf3ffabfba1c183e7c97ac) | Found | Found |
| Click argument splitter move, earlier type annotations | [`0103c95`](https://github.com/pallets/click/commit/0103c9570650daa59560baf42ad0a27e57b3157f) | Missed | Found |
| Click short-help rename, earlier docstring change | [`790ebd6`](https://github.com/pallets/click/commit/790ebd665ce03f25990e037b3e9f16951a2723aa) | Found | Found |
| Click safe-call rename with docstring edit, earlier typing change | [`ec258fe`](https://github.com/pallets/click/commit/ec258fef824347e61bd563e8d194ee726224e453) | Found | Found |
| Click short help, abbreviation handling | [`f67c2bb`](https://github.com/pallets/click/commit/f67c2bb6c2f055c1c7a57cd46c3697fc26a7742e) | Found | Found |
| Click echo, empty-bytes handling introduced through a merge | [`4d3db84`](https://github.com/pallets/click/commit/4d3db84b251518e97299a38a5ca4bab3d01873a2) | Found | Found |

Git already recovered the earlier commits in the whole-package layout moves. The new matching helped when the original file stayed behind, as it did when Packaging moved helpers out of `specifiers.py` and Click moved `split_arg_string` out of `parser.py`.

An early v2 run found 10 cases. Walking only first parents attributed changes to merge commits and hid some original commits. The release asks Git for the line history introduced through those merges, and the test suite includes a regression case for that behavior.

Both releases miss the wheel parser fix because the change is to `_build_tag_regex` outside the function body. Tracing changes to dependencies such as module-level constants requires additional analysis.

## Reproduce

From a Git checkout with the `v1.0.0` tag available and network access, run:

```sh
python -B evaluation/run.py
```

The runner clones both upstream histories into temporary directories, uses the revisions in [cases.json](cases.json), and compares the current tracker with the script from the v1 tag. The recorded run used Python 3.13.3 and Git 2.47.1 on Windows.
