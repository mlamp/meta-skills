# Measured raw artifact workflow

This policy applies to measured batches created after D-032. It does not rewrite E-07, E-08, or existing E-09 smoke and qualification history.

## What goes where

Git contains the frozen inputs, packager, verifier, expected inventory, released manifest, compact results, claim changes, and ledger lines. The full measured raw directory stays in ignored local staging. Its durable copy is one deterministic archive on an immutable GitHub Release. The manifest uploaded with the archive and the manifest committed later must have identical bytes.

There is no required external mirror in v1. A committed manifest detects a missing or changed release. It cannot recover one. The tooling never deletes local raw staging. A later manual deletion is a separate operator decision after release and manifest verification; this policy neither requires nor automates it.

## E-09 sequence

Run these only from the exact frozen commit after it has landed on the default branch. Complete qualification, adapter smoke, interviews, tasks, judgments, and blind human adjudication first.

```sh
python3 experiments/e09/harness.py artifact-pack
E09_BATCH_ID=m-... # paste the id printed by artifact-pack
python3 experiments/artifacts.py verify-local \
  --manifest "experiments/e09/.artifacts/${E09_BATCH_ID}.manifest.json" \
  --archive "experiments/e09/.artifacts/${E09_BATCH_ID}.raw.tar.gz"
python3 experiments/artifacts.py stage-release \
  --manifest "experiments/e09/.artifacts/${E09_BATCH_ID}.manifest.json" \
  --archive "experiments/e09/.artifacts/${E09_BATCH_ID}.raw.tar.gz"
```

`stage-release` checks the repository's immutable-release setting through the GitHub API. It refuses to create or resume a draft when the setting is disabled.

After `stage-release` finishes, inspect the GitHub draft and both local files. Expected and actual inventory must match, sanitization and digests must pass, and every error, retry, and exclusion must agree with the frozen protocol and raw records. Inventory includes failed and excluded records; their separate status counts preserve those outcomes. Any unexplained outcome, configured credential, frozen secret or host pattern, or other sensitive value blocks publication. There is no sanitizer waiver. Correct the frozen input and start a new batch. Publishing is the human approval point.

```sh
python3 experiments/artifacts.py publish-release \
  --manifest "experiments/e09/.artifacts/${E09_BATCH_ID}.manifest.json" \
  --archive "experiments/e09/.artifacts/${E09_BATCH_ID}.raw.tar.gz" \
  --confirm-tag "evidence-e09-${E09_BATCH_ID}" \
  --committed-copy "experiments/e09/artifacts/${E09_BATCH_ID}.json"
python3 experiments/e09/harness.py finalize
```

`publish-release` publishes the draft, waits for it to become immutable, downloads and verifies both assets and attestations, then writes the tracked manifest copy. `finalize` independently repeats the fresh-download, tag, member, and attestation checks against that tracked copy before it writes results or ledger lines.

Commit the new manifest, compact result, claim changes, and harness-written ledger lines in the results PR. Do not commit the raw directory or local archive.

If a published bundle is wrong, change the frozen input that caused it and run a new batch. Pass the old tag to `artifact-pack --supersedes <old-tag>`. Use `supersedes` only for a published bundle; unpublished or abandoned work is not evidence. Never replace a release, reuse a tag, or edit an existing manifest or ledger line.

## Smoke retention

Smoke records stay small and reviewable in Git. Preserve the four legacy reader smokes. For each content-addressed current reader or adapter key, retain only its highest numbered `attempt-NNN` directory before opening a PR.
