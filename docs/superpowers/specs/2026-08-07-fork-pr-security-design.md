# Secure fork pull requests and privileged validation

## Purpose

Allow outside contributors to open pull requests from forks without exposing
credentials, executing contributor-controlled code with repository authority, or
creating an unmanageable review queue. This repository controls DeFi integrations,
so CI is treated as a production security boundary rather than a convenience
feature.

## Threat model

An attacker can create a public fork, open a pull request, change every file in
that fork (including workflow files, scripts, tests and dprint configuration), and
push additional commits after a maintainer has looked at the original diff. They
may attempt to:

- make a privileged GitHub Actions job execute their code and read a repository
  secret or write-capable `GITHUB_TOKEN`;
- change validation code or an action reference to exfiltrate a credential;
- submit many pull requests to consume maintainer attention or Actions capacity;
- merge a configuration or workflow change without review by the appropriate
  maintainers.

The design protects repository and environment secrets from that attacker. It does
not treat public RPC endpoints as confidential, and it cannot make a malicious
change safe after it has been approved and merged; branch review and validation are
the controls for that case.

## Decisions

### Ownership and merge governance

Create `.github/CODEOWNERS` with the following ownership model:

```text
# Protocol configuration and documentation
*                    @MakinaHQ/dialectic @platykurtic-icu

# CI, privileged validation, and their tests
/.github/            @MakinaHQ/makina_dev @platykurtic-icu
/scripts/            @MakinaHQ/makina_dev @platykurtic-icu
/tests/              @MakinaHQ/makina_dev @platykurtic-icu
/.github/CODEOWNERS  @MakinaHQ/makina_dev @platykurtic-icu
```

Owners on one line are alternatives: either the listed team or `@platykurtic-icu`
can supply the Code Owner approval. This lets the active maintainer handle ordinary
work without waiting for a particular person, while still assigning the CI and
security-sensitive paths to the engineering team.

Repository rules must require Code Owner review and two approving reviews for
`main`. Existing requirements to dismiss stale approvals, require approval of the
latest push, require resolved conversations, signed commits, linear history, and
block force pushes remain enabled. A pull request authored by an owner still needs
two other people: authors cannot approve their own pull requests. There is no
native GitHub setting that requires one reviewer from _each_ team for a single file;
the path split above is the simple, auditable alternative.

### Unprivileged pull-request CI

The existing linting, transpiler, address, token-chain and unit-validation workflows
remain normal `pull_request` workflows. They may check out and execute fork code,
but they must receive neither repository nor environment secrets and must use only a
read-only `GITHUB_TOKEN`.

Every workflow declares the least privilege it needs, normally:

```yaml
permissions:
  contents: read
```

Every checkout disables credential persistence:

```yaml
with:
  persist-credentials: false
```

All third-party actions are pinned to immutable full commit SHAs, with an inline
comment naming the released version. GitHub repository settings allow only the
actions actually used by these workflows and verified GitHub-authored actions, and
require SHA pinning. `dprint` and other tools may download public dependencies but
never run with a credential.

### Privileged live validation

The two current `pull_request_target` workflows are unsafe because they check out a
fork head SHA and execute fork-controlled Python while passing `ALCHEMY_API_KEY`.
Replace them with one trusted validation workflow that has these invariants:

1. Its workflow definition, validation scripts and tests are checked out from the
   base commit only (`github.event.pull_request.base.sha`). It never checks out,
   imports, shells out to, or executes code from the contributor's head commit.
2. It obtains only a fixed allowlist of changed data files from the pull request head
   through GitHub's contents API, addressed by the immutable head SHA. Workflow
   files, scripts, action references, tests and executable files can never become
   input to the privileged job.
3. It parses those files as data and feeds them to trusted base-revision validation
   code. File paths are validated before access; no pull-request value is used as a
   shell fragment or executable path.
4. It receives a dedicated, low-quota RPC key only through the `pr-validation`
   environment. The repository-level `ALCHEMY_API_KEY` is not passed to any
   `pull_request_target` job.
5. The job references `environment: pr-validation`. The environment requires review
   by `@MakinaHQ/makina_dev` or `@platykurtic-icu`, disallows self-review, and
   disallows administrator bypass. Its branch policy admits protected branches only.

The environment approval is a second, explicit decision to use the RPC credential.
The job has no write permissions and produces only validation results. A new push
creates a new deployment/approval point, so a prior approval cannot authorize
changed fork content.

The trusted workflow triggers for pull-request open, reopen and synchronization,
limited to paths relevant to token-list and open-position validation. Its required
status is designed as an always-present gate: it reports a clear no-op only when no
relevant data changed, rather than using a job-level `if` that GitHub would count as
a successful skipped required check.

### Abuse controls

Set GitHub's fork-workflow approval policy to **all external contributors**, rather
than only first-time contributors. This ensures even ordinary unprivileged CI on a
fork needs an explicit maintainer approval to consume Actions capacity.

Enable the repository's external-contributor pull-request limit at **one open PR per
user**. This prevents a single account from filling the queue; maintainers retain
normal access and GitHub's temporary interaction limits remain an incident-response
tool rather than a permanent barrier to good contributors.

Set the repository default `GITHUB_TOKEN` permission to **read-only** and keep the
setting that prevents Actions from approving pull-request reviews. Individual jobs
must not add write scopes unless a future, separately reviewed design requires it.

### Secrets

The current source tree uses only `ALCHEMY_API_KEY`. The following repository
secrets have no reference in current tracked source and are candidates for deletion
only after confirming that no external/manual process still relies on them:

- `ARBITRUM_RPC_URL`
- `BASE_RPC_URL`
- `ETHEREUM_MAINNET_RPC_URL`
- `ETHERSCAN_API_KEY`
- `MAKINA_RS_DEPLOY_KEY`
- `MONAD_RPC_URL`

`MAKINA_RS_DEPLOY_KEY` needs special handling: identify it with its provider and
revoke it there after deletion, because deleting the GitHub secret does not revoke a
possibly copied private key.

Replace `ALCHEMY_API_KEY` with a new dedicated, limited `ALCHEMY_PR_VALIDATION_KEY`
stored as an **environment secret** on `pr-validation`. Apply provider-side
allowlisting, quota and monitoring where available. Rotate the old key after the
new workflow has been merged and verified. Secret values are never printed, logged,
committed, or passed to ordinary fork CI.

## Implementation boundaries

The repository change consists of `.github/CODEOWNERS`, hardened workflow YAML,
small trusted helper code/tests needed to fetch and validate allowlisted PR data,
and action SHA pins. It does not change generated rootfiles or protocol integration
content.

GitHub repository settings and secret lifecycle are separate administrative steps,
applied only after the hardened workflow is merged. This prevents a configuration
window in which fork PRs can run privileged code with a migrated credential.

## Safe rollout order

1. Merge the repository change containing Code Owners, SHA-pinned actions,
   read-only workflow declarations, and the trusted privileged validator.
2. Confirm the new required check runs successfully on an internal test PR and that
   it does not execute a fork head checkout.
3. Update the `main` ruleset: two approvals and required Code Owner review.
4. Set repository Actions defaults to read-only, enable SHA pinning and configure
   the action allowlist to match the pinned actions.
5. Configure `pr-validation` reviewers, no self-review, no admin bypass, and add
   the new environment-scoped limited RPC secret.
6. Set fork approval to all external contributors and enable the one-open-PR limit.
7. Rotate the former Alchemy key and, after a final dependency check and explicit
   approval, delete/revoke the six unused secrets.
8. Exercise the process with a throwaway fork PR: ordinary CI remains pending until
   approved, privileged validation uses only base code and awaits environment
   approval, Code Owner review is required, and a new fork push invalidates both
   reviews and privileged validation approval.

## Verification criteria

- No `pull_request_target` job checks out or executes a pull request head ref.
- No ordinary `pull_request` job receives a secret, a write token, or persisted git
  credentials.
- All action invocations resolve to full immutable SHAs.
- A protected-path pull request cannot merge without Code Owner review and two
  independent approvals.
- A fork contributor cannot start ordinary Actions work or access the privileged
  validation environment without a maintainer decision.
- The privileged job can read only the allowlisted PR data, validates it with trusted
  base-revision code, and can use only the dedicated environment-scoped RPC key.
- Each repository secret has a known live consumer; unused credentials are removed
  and provider-side credentials are revoked or rotated.
