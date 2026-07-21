# Contributing

Changes to decoder heuristics, rendering profiles, examples, and benchmarks are
welcome. Changes to the ORTM v0 logical layout require a written compatibility
impact analysis and new conformance vectors; incompatible layouts must use a new
version number.

Before submitting a change, run:

```bash
make test
```

Do not regenerate golden vectors merely to make a failing test pass. Compare the
new bytes and matrices with `spec/ORTM-v0.md` first.
