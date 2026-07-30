import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compute_affected_calibers as cac


ALL_CALIBERS = [
    ("dbit", "mainnet"),
    ("dusd", "mainnet"),
    ("dusd", "base"),
]


class TestAffectedCalibers(unittest.TestCase):
    def test_local_caliber_file_change_affects_only_that_caliber(self):
        changed = ["machines/dusd/mainnet/caliber.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [("dusd", "mainnet")])

    def test_local_instruction_change_affects_only_that_caliber(self):
        changed = ["machines/dusd/mainnet/instructions/merkl.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [("dusd", "mainnet")])

    def test_global_instructions_change_affects_all_calibers(self):
        changed = ["instructions/makina.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_global_blueprints_change_affects_all_calibers(self):
        changed = ["blueprints/aave/deposit.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_global_instructions_x_change_affects_all_calibers(self):
        changed = ["instructions-x/morpho-market-debt.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_blueprints_x_change_affects_all_calibers(self):
        changed = ["blueprints-x/aave-horizon/deposit.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_token_list_change_affects_all_calibers(self):
        changed = ["token-lists/prod-token-list.json"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_rootfile_change_is_excluded(self):
        changed = ["machines/dusd/mainnet/rootfiles/20260722-x.toml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_machine_level_config_change_is_excluded(self):
        changed = ["machines/dusd/config.toml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_unrelated_path_is_excluded(self):
        changed = [".github/workflows/linting.yaml", "README.md", "scripts/foo.py"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_composite_action_change_affects_all_calibers(self):
        # The transpile-validate action defines HOW every caliber is transpiled,
        # including the pinned transpiler version, so a change there must sweep
        # everything — otherwise a version bump validates nothing.
        changed = [".github/actions/transpile-validate/action.yml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_workflow_change_affects_no_calibers(self):
        # Workflows orchestrate WHEN transpiling happens and cannot change its
        # output, so the narrower `.github/actions/` scoping is deliberate.
        changed = [
            ".github/workflows/rootfiles-guard.yaml",
            ".github/workflows/release.yaml",
            ".github/workflows/transpiler.yaml",
        ]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_unknown_machine_chain_pair_is_ignored(self):
        changed = ["machines/doesnotexist/mainnet/caliber.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_mixed_local_and_global_returns_all(self):
        changed = ["machines/dusd/mainnet/caliber.yaml", "blueprints/aave/deposit.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_empty_input_returns_empty(self):
        self.assertEqual(cac.affected_calibers([], ALL_CALIBERS), [])

    def test_blank_lines_are_ignored(self):
        changed = ["", "  ", "machines/dusd/mainnet/caliber.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [("dusd", "mainnet")])

    def test_deprecated_caliber_change_is_excluded(self):
        changed = ["machines/.deprecated/mteth/mainnet/caliber.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_deprecated_instruction_change_is_excluded(self):
        changed = ["machines/.deprecated/mteth/mainnet/instructions/foo.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])


INCLUDE_RE = re.compile(r'!include\s+"([^"]+)"')
BLUEPRINT_PATH_RE = re.compile(r'^\s*path:\s*"([^"]+)"', re.MULTILINE)


class TestGlobalPrefixesCoverRealSourceGraph(unittest.TestCase):
    """GLOBAL_PREFIXES is an allowlist, so a shared source directory nobody adds to it is
    silently skipped by the PR gate — a caliber depending on it would not be re-transpiled,
    and the drift would only surface at release time. Instead of trusting the tuple to be
    maintained by hand, walk the real dependency graph of every caliber and assert that every
    shared path it reaches is covered.

    Both `!include` targets in a caliber.yaml and the blueprint `path:` refs inside the files
    they pull in resolve relative to the caliber.yaml's own directory.
    """

    def _shared_deps(self, repo_root):
        """Yield (caliber, repo-relative dependency) for every dep outside machines/."""
        for caliber in sorted(repo_root.glob("machines/*/*/caliber.yaml")):
            rel_caliber = caliber.relative_to(repo_root).as_posix()
            if rel_caliber.startswith(cac.DEPRECATED_PREFIX):
                continue

            for include in INCLUDE_RE.findall(caliber.read_text()):
                included = (caliber.parent / include).resolve()
                deps = [included]
                if included.is_file():
                    deps += [
                        (caliber.parent / ref.rsplit(":", 1)[0]).resolve()
                        for ref in BLUEPRINT_PATH_RE.findall(included.read_text())
                    ]

                for dep in deps:
                    try:
                        rel_dep = dep.relative_to(repo_root).as_posix()
                    except ValueError:  # escapes the repo entirely — not our concern here
                        continue
                    if not rel_dep.startswith("machines/"):
                        yield rel_caliber, rel_dep

    def test_every_shared_source_reachable_from_a_caliber_is_covered(self):
        repo_root = Path(__file__).resolve().parents[1]
        uncovered = sorted(
            {
                (dep, caliber)
                for caliber, dep in self._shared_deps(repo_root)
                if not dep.startswith(cac.GLOBAL_PREFIXES)
            }
        )
        self.assertEqual(
            uncovered,
            [],
            "shared source(s) reachable from a caliber are not covered by GLOBAL_PREFIXES — "
            "add the missing top-level prefix to scripts/compute_affected_calibers.py:\n"
            + "\n".join(f"  {dep}  (via {caliber})" for dep, caliber in uncovered),
        )

    def test_every_shared_source_reachable_from_a_caliber_exists(self):
        repo_root = Path(__file__).resolve().parents[1]
        missing = sorted(
            {
                (dep, caliber)
                for caliber, dep in self._shared_deps(repo_root)
                if not (repo_root / dep).is_file()
            }
        )
        self.assertEqual(
            missing,
            [],
            "caliber references a shared source that does not exist:\n"
            + "\n".join(f"  {dep}  (via {caliber})" for dep, caliber in missing),
        )


class TestDiscoverCalibers(unittest.TestCase):
    def test_discovers_all_caliber_yaml_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet").mkdir(parents=True)
            (root / "machines" / "dusd" / "mainnet" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / "dbit" / "base").mkdir(parents=True)
            (root / "machines" / "dbit" / "base" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / "dbit" / "base" / "instructions").mkdir()

            result = cac.discover_calibers(root)
            self.assertEqual(result, [("dbit", "base"), ("dusd", "mainnet")])

    def test_ignores_directories_without_caliber_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet" / "rootfiles").mkdir(parents=True)
            result = cac.discover_calibers(root)
            self.assertEqual(result, [])

    def test_excludes_deprecated_machines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet").mkdir(parents=True)
            (root / "machines" / "dusd" / "mainnet" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / ".deprecated" / "mteth" / "mainnet").mkdir(parents=True)
            (root / "machines" / ".deprecated" / "mteth" / "mainnet" / "caliber.yaml").write_text(
                "config: {}\n"
            )

            result = cac.discover_calibers(root)
            self.assertEqual(result, [("dusd", "mainnet")])


class TestMainCli(unittest.TestCase):
    def test_main_prints_affected_pairs_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet").mkdir(parents=True)
            (root / "machines" / "dusd" / "mainnet" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / "dbit" / "base").mkdir(parents=True)
            (root / "machines" / "dbit" / "base" / "caliber.yaml").write_text("config: {}\n")

            script = Path(__file__).resolve().parents[1] / "scripts" / "compute_affected_calibers.py"
            proc = subprocess.run(
                [sys.executable, str(script), "instructions/makina.yaml"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(proc.stdout.splitlines(), ["dbit/base", "dusd/mainnet"])

    def test_main_all_prints_every_caliber_sorted_ignoring_other_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet").mkdir(parents=True)
            (root / "machines" / "dusd" / "mainnet" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / "dbit" / "base").mkdir(parents=True)
            (root / "machines" / "dbit" / "base" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / ".deprecated" / "mteth" / "mainnet").mkdir(parents=True)
            (root / "machines" / ".deprecated" / "mteth" / "mainnet" / "caliber.yaml").write_text(
                "config: {}\n"
            )

            script = Path(__file__).resolve().parents[1] / "scripts" / "compute_affected_calibers.py"
            proc = subprocess.run(
                [sys.executable, str(script), "--all", "machines/dusd/mainnet/caliber.yaml"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(proc.stdout.splitlines(), ["dbit/base", "dusd/mainnet"])


if __name__ == "__main__":
    unittest.main()
