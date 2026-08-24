# Measured raw artifact workflow

`freeze_sha256` is the SHA-256 of the frozen `freeze.json` bytes. A compact result is a schema-2 object. Its `lines` array equals every and only ledger row whose `results_path` names that file.

This policy applies to measured batches created after D-032. It does not rewrite E-07, E-08, or existing E-09 smoke and qualification history.

## What goes where

Git contains the frozen inputs, packager, verifier, expected inventory, released manifest, compact results, claim changes, and ledger lines. The full measured raw directory stays in ignored local staging. Its durable copy is one deterministic archive on an immutable GitHub Release. The manifest uploaded with the archive and the manifest committed later must have identical bytes.

There is no required external mirror in v1. A committed manifest detects a missing or changed release. It cannot recover one. The tooling never deletes local raw staging. A later manual deletion is a separate operator decision after release and manifest verification; this policy neither requires nor automates it.

## E-09 sequence

Run every command below only while `HEAD` equals the commit that last changed `freeze.json`, after that commit has landed on the default branch. `artifact-pack`, `stage-release`, `publish-release`, and `finalize` each require the packager and every provenance file to match that commit byte for byte. `verify-local` checks only the archive and manifest. Complete qualification, adapter smoke, interviews, tasks, judgments, and blind human adjudication first.

```sh
python3 experiments/e09/harness.py artifact-pack
E09_BATCH_ID=m-... # paste the id printed by artifact-pack
E09_RAW_ROOT="experiments/e09/raw/measured/${E09_BATCH_ID}"
E09_PLAN="experiments/e09/.artifacts/${E09_BATCH_ID}.plan.json"
python3 experiments/artifacts.py verify-local \
  --manifest "experiments/e09/.artifacts/${E09_BATCH_ID}.manifest.json" \
  --archive "experiments/e09/.artifacts/${E09_BATCH_ID}.raw.tar.gz"
python3 experiments/artifacts.py stage-release \
  --manifest "experiments/e09/.artifacts/${E09_BATCH_ID}.manifest.json" \
  --archive "experiments/e09/.artifacts/${E09_BATCH_ID}.raw.tar.gz" \
  --plan "$E09_PLAN" \
  --raw-root "$E09_RAW_ROOT" \
  --repo-root .
```

`stage-release` checks the repository's immutable-release setting through the GitHub API. It refuses to create or resume a draft when the setting is disabled.

After `stage-release` finishes, inspect the GitHub draft and the local archive, manifest, and plan. This is an exhaustive field review, not a spot-check: review every recorded error, retry, and exclusion, plus all expected and actual counts, sanitizer summaries, and digests. Inventory includes failed and excluded records; their separate status counts preserve those outcomes. Any unexplained outcome, configured credential, frozen secret or host pattern, or other sensitive value blocks publication. There is no sanitizer waiver. Every automated mismatch exits nonzero before draft creation or publication; a zero exit does not replace the human review. Correct the frozen input and start a new batch when the content or policy is wrong. Publishing is the human approval point.

```sh
python3 experiments/artifacts.py publish-release \
  --manifest "experiments/e09/.artifacts/${E09_BATCH_ID}.manifest.json" \
  --archive "experiments/e09/.artifacts/${E09_BATCH_ID}.raw.tar.gz" \
  --plan "$E09_PLAN" \
  --raw-root "$E09_RAW_ROOT" \
  --repo-root . \
  --confirm-tag "evidence-e09-${E09_BATCH_ID}" \
  --committed-copy "experiments/e09/artifacts/${E09_BATCH_ID}.json"
python3 experiments/e09/harness.py finalize
```

Both release commands require local `HEAD` to remain that exact frozen commit. For E-09, `stage-release` and `publish-release` each independently run the frozen harness, derive a fresh plan, and require exact equality with the saved plan before they contact GitHub. Plan equality authenticates the expected execution, exclusions, and inventory. Each command then separately requires the manifest and current raw inventory and member bytes to match its fresh derived plan. A raw change between the commands makes `publish-release` fail. Frozen `freeze.json` defines the complete provenance key set. The sanitizer policy binds the credential-variable names and full forbidden-pattern definitions, and the release commands rederive it from its source at the frozen commit. Nested JSON strings are decoded until exhausted; a resource limit fails closed. Cross-platform traversal, links, and unexpected files fail before any raw-tree read or write. Record-manifest paths must resolve to regular files inside the measured namespace. Failed and excluded records cannot carry results. `adjudication-pending.json` and `adjudication-resolved.json` exist exactly when current substitute judgments disagree. The pending file must equal those current disagreements. The resolved file must contain one valid verdict list for every and only current disagreement blind ID. The archive verifier reproduces the deterministic archive and requires exact bytes. Before any GitHub contact, publication rejects a conflicting tracked-manifest copy. Before the irreversible publish action, it queries GitHub and rejects an existing tag that points elsewhere. `publish-release` then performs stages five and six. Stage six is the automatic first fresh-download check inside `publish-release`: after immutability, it downloads both assets, requires the release commit to remain on the current default branch, verifies the GitHub release and archive attestations, and writes the tracked manifest copy. It is not `finalize`. Stage seven is the separate `finalize` command. Immediately after that fresh download and again before it writes results or ledger lines, it requires the current packager and provenance bytes to match the frozen commit and the current raw inventory and member bytes to match the derived plan and manifest.

Commit the new manifest, compact result, claim changes, and harness-written ledger lines in the results PR. Do not commit the raw directory or local archive.

If a published bundle is wrong, change the frozen input that caused it and run a new batch. Pass the old tag to `artifact-pack --supersedes <old-tag>`. Use `supersedes` only for a published bundle; unpublished or abandoned work is not evidence. Never replace a release, reuse a tag, or edit an existing manifest or ledger line.

Pull-request code tests run on the ordinary `pull_request` event and receive no release credential. The separate `pull_request_target` job executes only the base branch's verifier. It uses a read-only token. It requires the checked-out merge commit and its second parent to match the event's merge and head SHAs. It uses GitHub to require both the manifest's numeric repository id and the current repository name. The candidate ledger must extend the trusted base ledger byte for byte. The four legacy artifactless rows are pinned by their complete canonical hashes. Every other exact numeric experiment row requires an artifact receipt. The verifier binds each row's experiment, batch, and freeze to the standard manifest and result paths. The compact result must contain exactly the full set of ledger rows that name it. It then checks the manifest hash, release tag and id, archive digest, attestation subjects, and remote release. Releases referenced by ledger rows are downloaded once. The orphan-manifest pass handles only committed manifests absent from that verified set. Main-branch CI repeats those checks against the previous main ledger.

Retry a transient or interrupted command with the identical plan, raw root, archive, manifest, and tag. The atomic packer accepts identical completed files and repairs an interrupted local pair. A retry after publication repeats remote verification and accepts only the identical tracked manifest. A content or policy failure is different: correct the frozen input and start a new batch.

## Pre-measurement lifecycle proof

After this policy merges and before the first measured E-09 provider call, run the publication lifecycle through stage six from the merged exact frozen commit on a synthetic one-record raw root. Stage seven remains the measured E-09 finalizer and does not run in this smoke. Use `experiment: artifact-storage-smoke` and a unique `artifact-storage-smoke-<frozen-sha-prefix>` tag. This smoke is not measured evidence. Do not create a result or ledger line. Record the immutable release URL, tag, archive and manifest SHA-256 values, remote receipt, and outcome on issue #10. Close the issue only after a fresh download and both GitHub attestations verify. Keep the local smoke root and do not commit it.

## Smoke retention

Smoke records stay small and reviewable in Git. Preserve the four legacy reader smokes. For each content-addressed current reader or adapter key, retain only its highest numbered `attempt-NNN` directory before opening a PR.
