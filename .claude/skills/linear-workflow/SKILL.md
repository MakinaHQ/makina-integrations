---
name: linear-workflow
description: >-
  Track Makina integration work (MakinaHQ/config and MakinaHQ/makina-integrations) in
  Linear before editing, and move the issue as the position goes from config PR to
  release to the prod mirror. Use at the start of any task that edits files, when
  opening or merging a PR, when mirroring into makina-integrations, and when asked
  whether an integration is already tracked.
---

# Linear workflow for Makina integrations

Linear is the source of truth for which positions are being integrated and which
are live. Every change to `MakinaHQ/config` or `MakinaHQ/makina-integrations` has an
issue. Read-only questions need none until an edit is needed. The same issue follows
a position from its config PR through the prod mirror; do not open a second issue
for the mirror.

## Routing and ownership

- Team: **Dialectic Atelier** (`DIA`), UUID `25e48900-0957-4dc5-b1f6-5c6ce3a38428`.
- Project: [Makina Integrations](https://linear.app/dialectic/project/makina-integrations-aa74418efc11),
  UUID `f1707424-3483-4dda-bc34-5c183d14de27`. Use the UUID in tool calls; do not
  file in the KGB-team "Makina machine integrations" board.
- Assign work from Augustin's laptop to **Augustin K.** (`augustin@dialectic.ch`),
  `assignee="37fa8581-6877-4a51-bc33-657a12b0ed13"`, unless another owner is
  explicitly requested. Never use `assignee="me"`: the connector account belongs to
  Theodore C., not the requesting user.
- One issue per position, titled `<Protocol>: <market or vault> (<action>) - <FUNDS>`,
  for example `Morpho: RLUSD/WBTC market (borrow) - DBIT`. A position added to
  several machines in one PR is one issue with every fund in the title and labels.
- Labels: one per machine touched, plus a type (`Feature` for a new position,
  `Bug` for a fix, `Improvement` or `Tech Debt` otherwise). Repository tooling
  (CI, scripts, agent guides) takes `Tooling` instead of a machine label.

| Machine directory    | Label                   |
| -------------------- | ----------------------- |
| `dcm`, `bfeederdcm`  | `DCM`                   |
| `dusd`               | `DUSD`                  |
| `dbit`               | `DBIT`                  |
| `deth`               | `DETH`                  |
| `dmg`                | `DMG`                   |
| `dmw`                | `DMW`                   |
| `dqaeeth`            | `DQAeETH`               |
| `intMkSrRoyUSDC`     | `DSV`                   |
| `usdSHFmk`           | `usdSHFmk`              |
| `chronograph-x`      | `Chrono MakinaX Module` |
| `y*c` stock machines | `machines/mag7`         |

A machine with no label above gets none; name it in the title. A defect in a
published APR, order path or position manager belongs to
[Nebula](https://linear.app/dialectic/project/nebula-cac05678cbf4); a defect in how
Abu sizes or dispatches the position belongs to the owning Abu project. Link those
with `relatedTo` instead of widening the integration issue.

## Start a task

1. Search the project with the protocol and market (`query="Morpho RLUSD WBTC"`,
   `limit=10`). Integration requests are usually queued in **Backlog** or **Todo**
   already; titles may differ slightly, so check the fund too. Fetch a supplied
   issue ID directly.
2. Reuse a match: set **In Progress** and the assignee in one `save_issue`. If two
   open issues describe the same position, keep the older one and mark the other
   `duplicateOf` it.
3. Otherwise create one with the template below, state **In Progress**.
4. Put the issue ID in the branch, every commit subject and the PR title, e.g.
   `feat(dbit): DIA-2371 add Morpho RLUSD/WBTC market`. A PR that ships several
   positions lists every ID in its title or first line.

## Lifecycle

| Moment                                                          | Action                                                                        |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Authoring starts in `config`                                    | **In Progress**                                                               |
| `config` PR opened                                              | **In Review**, comment with the PR link                                       |
| `config` PR merged and released                                 | Stay **In Review**, comment with the release version (`rootfiles for v1.0.x`) |
| Mirror PR opened in `makina-integrations`                       | Comment with the PR link                                                      |
| Mirror merged and the new root is live on-chain for the machine | **Done**, comment with the mirror commit and evidence the root is applied     |
| Abandoned or superseded                                         | **Canceled**, one comment saying why                                          |

`Done` means the position can be operated in production. A merge in `config` alone
is staging. If the on-chain root update is still pending, leave **In Review** and
say what remains.

## Issue template

```markdown
## Problem

The position to integrate or the defect, with protocol, chain and market.

## Why this matters

Which machine needs it and what it enables.

## Where

Machines, chains, blueprints and instruction files.

## Fix sketch

Blueprints reused or written, accounting approach, known constraints.

## Acceptance criteria

- [ ] Instructions compile and e2e tests pass in config
- [ ] Mirrored to makina-integrations with prod addresses verified
- [ ] Root live on-chain for every listed machine
```

Do not put wallet addresses, LP names, confidential figures or P&L in Linear text.

## Tools and write discipline

Use the available Linear MCP (`mcp__linear__*`, `mcp__claude_ai_Linear__*`,
`mcp__plugin_linear_linear__*` or `mcp__codex_apps__linear_*`). If none is
available, report that tracking is blocked and offer the GraphQL API with an
existing `LINEAR_API_KEY`. Never commit or print a key.

- One `save_issue` per state transition, with every changed field in that call.
- Filter reads by project plus query or label, 5–10 results.
- Do not fetch only to confirm a successful write; the response is the evidence.
- After an ambiguous failed write, re-read before retrying.
- Out-of-scope findings become their own **Backlog** issue, linked `relatedTo`.
