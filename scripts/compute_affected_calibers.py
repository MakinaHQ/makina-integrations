#!/usr/bin/env python3
"""Resolve which calibers are affected by a set of changed file paths.

Used by the PR gate (transpiler.yaml) to scope which calibers get
transpiled/checked/validated for a given PR: a caliber is affected when its
own files changed, or a shared/global source it could depend on changed.
Prints one "machine/chain" pair per line, sorted.

Release scoping does NOT use this: releases sweep every caliber and detect
change by transpiler output, which can't miss a dependency this path-based
rule doesn't know about. See
docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md.

Pass `--all` to instead print every caliber discovered by discover_calibers(),
ignoring any other arguments — this is the single source of truth for "list
every caliber" used by release.yaml and transpiler.yaml's workflow_dispatch
sweep, replacing a hand-rolled `find | sed | sort` pipeline.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Any change under these prefixes could affect every caliber, since
# instructions/blueprints/blueprints-x are shared across machines and the
# token list is a transpiler input for all of them.
GLOBAL_PREFIXES = ("instructions/", "blueprints/", "blueprints-x/", "token-lists/")

# Machines under machines/.deprecated/ are retained for reference only and are
# out of scope for every CI workflow. See machines/.deprecated/README.md.
DEPRECATED_PREFIX = "machines/.deprecated/"


def discover_calibers(repo_root: Path) -> list[tuple[str, str]]:
    """Return sorted (machine, chain) pairs for every machines/*/*/caliber.yaml."""
    pairs = {
        (caliber_path.parent.parent.name, caliber_path.parent.name)
        for caliber_path in repo_root.glob("machines/*/*/caliber.yaml")
        if not caliber_path.relative_to(repo_root).as_posix().startswith(DEPRECATED_PREFIX)
    }
    return sorted(pairs)


def affected_calibers(
    changed_paths: list[str], all_calibers: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Apply the affected-set rule to a list of changed file paths."""
    all_set = set(all_calibers)
    affected: set[tuple[str, str]] = set()

    for raw_path in changed_paths:
        path = raw_path.strip()
        if not path:
            continue

        if path.startswith(DEPRECATED_PREFIX):
            continue

        if path.startswith(GLOBAL_PREFIXES):
            return sorted(all_set)

        parts = path.split("/")
        # machines/<machine>/<chain>/<rest...>, excluding machines/<m>/<c>/rootfiles/*
        if len(parts) >= 4 and parts[0] == "machines" and parts[3] != "rootfiles":
            pair = (parts[1], parts[2])
            if pair in all_set:
                affected.add(pair)

    return sorted(affected)


def main(argv: list[str]) -> int:
    all_calibers = discover_calibers(Path.cwd())
    if "--all" in argv:
        pairs = all_calibers
    else:
        pairs = affected_calibers(argv, all_calibers)
    for machine, chain in pairs:
        print(f"{machine}/{chain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
