# makina-integrations

Prod source of truth for public Makina machines: instructions, blueprints and calibers, transpiled into the rootfiles applied on-chain. Positions are authored and tested in `MakinaHQ/config` (staging) first, then mirrored here with prod addresses. See `README.md` for the layout and formatting (`dprint fmt`).

`AGENTS.md` is a symlink to this file; skills live in `.claude/skills/` and are symlinked from `.agents/skills/`.

## Linear

Every change is tracked in the DIA [Makina Integrations](https://linear.app/dialectic/project/makina-integrations-aa74418efc11) project. A mirror reuses the issue of the config PR it imports; do not open a second issue. Before the first edit, read [linear-workflow](.claude/skills/linear-workflow/SKILL.md). Put the issue ID in the branch, every commit subject and the PR title. From Augustin's laptop, assign `37fa8581-6877-4a51-bc33-657a12b0ed13`, never `assignee="me"`.
