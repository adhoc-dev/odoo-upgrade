# TESTING_73468 — permanent dummy PR fixture

This file has no functional effect. Its only purpose is to exist so that the
pull request that adds it can stay open and be linked permanently in the
`pull_ids` of the v19 upgrade type (`saas.upgrade.type` 18), giving every
upgrade run a test PR to apply.

Presence can be checked with a plain `ls` at the repo root.

Rules:

- **Do not merge this PR.** A merged PR in `pull_ids` is not inert: the
  duplication flow reads merged pulls to decide `update_to = "latest"` and
  `remove_merged_pulls`, so merging it would change the behaviour of the runs
  it is meant to exercise.
- **Do not delete this file** without unlinking the PR from the upgrade type
  first.

Reference: task 73468.
