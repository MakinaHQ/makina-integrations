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
   rootfiles`. The trusted validation jobs may skip only when base-revision
   classification finds no relevant data change; GitHub treats that case as a
   successful check.
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
