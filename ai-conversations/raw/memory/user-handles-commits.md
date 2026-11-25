---
name: user-handles-commits
description: Never run git commit in this project; the user commits every step themselves after review
metadata:
  node_type: memory
  type: feedback
  originSessionId: dc158628-2a5f-4498-b362-bd408155626e
  modified: 2026-11-25T18:53:50.860Z
---

Do not create git commits in this repo. Leave changes in the working tree and suggest a commit message; the user reviews and commits each step themselves.

**Why:** User said (2026-11-25, RBAC work on feat/role-based-access) "From now on I'll handle all commits, so don't commit." They review each step's diff before committing.

**How to apply:** After finishing a step, stop with the diff uncommitted, report what changed and verification results, and optionally propose a commit message. Related: [[rbac-step-by-step-review]]
