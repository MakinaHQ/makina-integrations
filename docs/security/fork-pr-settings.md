# Fork PR security settings

This runbook completes the repository change in the fork-PR security pull
request. It is intentionally ordered: enabling Code Owner enforcement or
SHA-only Actions before that PR is merged would block the repository's current
workflows or leave their unsafe fork-head execution in place.

## Before merge

Do these immediately; they do not depend on the new workflow files:

1. **Do not apply `safe-to-test` to a fork pull request.** Remove that label from
   every existing fork PR. In the current default branch, it causes a privileged
   workflow to check out and execute fork code with `ALCHEMY_API_KEY`.
2. Set **Actions > General > Workflow permissions** to **Read repository
   contents and packages permissions**. Keep **Allow GitHub Actions to create and
   approve pull requests** disabled. This reduces the current token's blast radius,
   but does not by itself make the old privileged workflows safe.
3. Set **Actions > General > Fork pull request workflows** to **Require approval
   for all external contributors**. Note that this does not gate
   `pull_request_target`; the code change in this PR is the protection for that
   event.
4. Enable **Limit the number of open pull requests from external contributors**
   with a maximum of **1**. This limits queue abuse without preventing a legitimate
   contributor from opening a PR.

## Immediately after merge

Perform these steps as one change window, before inviting broad fork
contributions.

1. **Configure the `pr-validation` environment.** Keep the existing required
   reviewers `@MakinaHQ/makina_dev` and `@platykurtic-icu`; change **Prevent
   self-review** to enabled and **Allow administrators to bypass configured
   protection rules** to disabled. Keep the protected-branches deployment policy.
   Create an environment secret named `ALCHEMY_PR_VALIDATION_KEY`, using a new
   low-quota Alchemy key dedicated to read-only PR validation. Do not store it as a
   repository secret.
2. **Update the `main protection` ruleset.** Require two approving reviews and
   **Require review from Code Owners**. Preserve the existing stale-review
   dismissal, latest-push approval, resolved-conversation, signed-commit, linear
   history and force-push restrictions. Keep the bypass list empty for normal
   maintainers; if an emergency bypass is operationally necessary, restrict it to
   a documented break-glass role with a post-incident review.
3. **Update required status checks.** Retain `Verify new rootfiles correctness
   with the transpiler`, `formatting`, and `Validate changed token lists`. Add
   `Run validator unit tests` and `Validate open positions coverage in latest added
   rootfiles`.

   Both validation check names belong to always-running gate jobs
   (`token-lists-status` and `open-positions-status`), not to the privileged
   validation jobs themselves. This matters: GitHub reports a _skipped_ required
   check as a success, so a required check attached to a conditional job would go
   green whenever classification failed. The gate jobs run unconditionally,
   inspect the classifier and validator results, and fail unless the outcome is
   conclusively "validated" or "there was nothing to validate". Do not make the
   privileged `validate-*` jobs the required checks, and do not add an `if:` to a
   gate job — `tests/test_workflow_security.py` enforces both.
4. **Lock down Actions supply chain.** Under **Actions > General > Actions
   permissions**, select only the action repositories used by this repository:
   `actions/checkout`, `astral-sh/setup-uv`, `dprint/check`, and
   `dtolnay/rust-toolchain`. Enable **Require actions to be pinned to a full-length
   commit SHA**. The PR pins every use to a 40-character commit, so this setting
   should not break the new workflows.
5. **Exercise the new workflow with a throwaway fork PR.** A normal fork workflow
   must wait for maintainer approval; the privileged validator must check out the
   base SHA, wait for a `pr-validation` reviewer, and report against only the
   changed allowlisted data. Push one new commit to confirm it creates a fresh
   environment approval point.
6. **Run `Validator Integration Tests` once from the Actions tab.** The RPC-backed
   test in `tests/test_validate_open_positions.py` cannot run in `Validator Tests`,
   which is `pull_request`-triggered and executes fork-authored test code, so it
   must never hold a secret. The manual workflow runs the same test against a live
   RPC using the `pr-validation` environment and sets `REQUIRE_LIVE_RPC_TESTS`, so a
   missing key fails the run instead of skipping silently. Run it after any change
   to `RpcCaliberReader`, the Caliber ABI, or the Alchemy chain-slug map.

## Operational consequences

**Internal pull requests also wait for a deployment approval.** The privileged
validation jobs carry `environment: pr-validation` regardless of whether the head
branch is a fork, so a maintainer's own PR that touches a token list or adds a
rootfile is held at "Waiting for review" until a _second_ maintainer approves the
deployment — "Prevent self-review" is enabled and admin bypass is disabled. This is
deliberate: `ALCHEMY_PR_VALIDATION_KEY` is an environment secret, and making
same-repo PRs skip the gate would require either a second environment or a
repository-level copy of the key, which widens the blast radius the environment
exists to contain. Budget for the second approver on routine token-list and
rootfile changes.

**Pushing during an approval wait invalidates the run.** The materializer compares
the pull request's current head against the approved head SHA and fails if they
differ, rather than classifying one commit and downloading another. A push creates
a fresh run and a fresh approval point; the stale run's failure is expected.

## Secret lifecycle

After the throwaway PR has passed, rotate the old `ALCHEMY_API_KEY` at Alchemy and
delete it from repository secrets. It is no longer used by tracked workflow code.

The following repository secrets have no reference in current tracked source:

- `ARBITRUM_RPC_URL`
- `BASE_RPC_URL`
- `ETHEREUM_MAINNET_RPC_URL`
- `ETHERSCAN_API_KEY`
- `MAKINA_RS_DEPLOY_KEY`
- `MONAD_RPC_URL`

Before deleting them, confirm that no manual deployment, external repository, or
provider integration still needs each credential. Delete and provider-revoke the
six confirmed-unused credentials. Treat `MAKINA_RS_DEPLOY_KEY` as a private deploy
key: identify and revoke its corresponding provider-side key as part of its removal.
Never paste a secret value into an issue, PR, workflow log, terminal recording, or
repository file.
