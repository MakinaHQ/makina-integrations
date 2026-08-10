"""Security invariants for GitHub Actions workflow configuration."""

from __future__ import annotations

import re
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
CODEOWNERS_PATH = REPO_ROOT / ".github" / "CODEOWNERS"

# GitHub treats .yml and .yaml identically, so both must be covered or a workflow
# can escape every invariant below simply by choosing the other spelling.
WORKFLOW_GLOBS = ("*.yaml", "*.yml")

# Allows the `owner/repo/path/to/action@sha` form as well as `owner/repo@sha`.
SHA_PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9a-f]{40}$")

# `${{secrets.X}}` and `${{ SECRETS.X }}` are both valid GitHub syntax, so matching
# a fixed substring such as "${{ secrets." would let a secret slip past unnoticed.
SECRET_EXPRESSION_RE = re.compile(r"\$\{\{\s*secrets\s*\.", re.IGNORECASE)

# Every expression that resolves to the untrusted pull-request head commit.
# `github.head_ref` and `refs/pull/<n>/head` are exactly as dangerous as
# `github.event.pull_request.head.sha` in a pull_request_target workflow.
FORK_HEAD_REF_MARKERS = (
    "github.event.pull_request.head",
    "github.head_ref",
    "github.event.pull_request.number",
    "refs/pull/",
)

REVIEWED_ENVIRONMENT = "pr-validation"
DEFAULT_BRANCH_REF = "${{ github.event.repository.default_branch }}"
DEFAULT_BRANCH_ONLY_CONDITION = (
    "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
)

# The always-running gate job per privileged workflow, and the required status
# check name it must carry. Branch protection reads a skipped required check as a
# success, so the required check may never be a job with a conditional `if`.
STATUS_GATE_JOBS = {
    "token-lists.yaml": ("token-lists-status", "Validate changed token lists"),
    "open-positions.yaml": (
        "open-positions-status",
        "Validate open positions coverage in latest added rootfiles",
    ),
}


def workflow_paths() -> list[Path]:
    paths: set[Path] = set()
    for pattern in WORKFLOW_GLOBS:
        paths.update(WORKFLOWS_DIR.glob(pattern))
    return sorted(paths)


def workflows() -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in workflow_paths():
        data = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        assert isinstance(data, dict), f"{path} must contain a workflow mapping"
        yield path, data


def triggers(workflow: dict[str, Any]) -> set[str]:
    event_config = workflow.get("on")
    if isinstance(event_config, str):
        return {event_config}
    if isinstance(event_config, list):
        return {event for event in event_config if isinstance(event, str)}
    if isinstance(event_config, dict):
        return set(event_config)
    return set()


def jobs(workflow: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    workflow_jobs = workflow.get("jobs")
    if not isinstance(workflow_jobs, dict):
        return
    for name, job in workflow_jobs.items():
        if isinstance(job, dict):
            yield str(name), job


def steps_of(job: dict[str, Any]) -> Iterator[dict[str, Any]]:
    job_steps = job.get("steps")
    if not isinstance(job_steps, list):
        return
    for step in job_steps:
        if isinstance(step, dict):
            yield step


def job_steps(workflow: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for _name, job in jobs(workflow):
        yield from steps_of(job)


def action_references(workflow: dict[str, Any]) -> Iterator[str]:
    """Every third-party reference CI trusts, including reusable workflows.

    A job may carry a top-level `uses:` and no `steps:` at all, so walking only
    `jobs.*.steps` would leave reusable workflows entirely unpinned.
    """
    for _name, job in jobs(workflow):
        job_uses = job.get("uses")
        if isinstance(job_uses, str):
            yield job_uses
        for step in steps_of(job):
            step_uses = step.get("uses")
            if isinstance(step_uses, str):
                yield step_uses


def contains_secret_expression(value: object) -> bool:
    if isinstance(value, str):
        return SECRET_EXPRESSION_RE.search(value) is not None
    if isinstance(value, dict):
        return any(contains_secret_expression(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_secret_expression(item) for item in value)
    return False


class WorkflowSecurityTests(unittest.TestCase):
    def test_workflow_discovery_is_not_silently_empty(self) -> None:
        """An invariant suite that iterates nothing would report a green no-op."""
        discovered = workflow_paths()
        self.assertTrue(discovered)
        on_disk = sorted(
            path for path in WORKFLOWS_DIR.iterdir() if path.suffix in {".yaml", ".yml"}
        )
        self.assertEqual(discovered, on_disk)

    def test_all_actions_are_pinned_to_full_commit_shas(self) -> None:
        """Changing an action tag must not silently change code trusted by CI."""
        for path, workflow in workflows():
            for uses in action_references(workflow):
                with self.subTest(workflow=path.name, uses=uses):
                    if uses.startswith("./"):
                        continue  # local action from the checked-out trusted ref
                    self.assertRegex(uses, SHA_PIN_RE)

    def test_all_checkouts_disable_persisted_credentials(self) -> None:
        """A PR-controlled command must not be able to reuse checkout credentials."""
        for path, workflow in workflows():
            for step in job_steps(workflow):
                uses = step.get("uses")
                if isinstance(uses, str) and uses.startswith("actions/checkout@"):
                    with self.subTest(workflow=path.name):
                        settings = step.get("with")
                        self.assertIsInstance(settings, dict)
                        self.assertEqual(settings.get("persist-credentials"), "false")

    def test_normal_pull_request_workflows_have_read_only_contents_and_no_secret(self) -> None:
        """An external contribution must run without repository credentials."""
        for path, workflow in workflows():
            if "pull_request" not in triggers(workflow):
                continue
            with self.subTest(workflow=path.name):
                self.assertEqual(workflow.get("permissions"), {"contents": "read"})
                self.assertFalse(contains_secret_expression(workflow))

    def test_privileged_workflows_never_checkout_a_pull_request_head(self) -> None:
        """Checking out a fork head in pull_request_target would execute attacker code with secrets."""
        for path, workflow in workflows():
            if "pull_request_target" not in triggers(workflow):
                continue
            for step in job_steps(workflow):
                uses = step.get("uses")
                if not isinstance(uses, str) or not uses.startswith("actions/checkout@"):
                    continue
                with self.subTest(workflow=path.name):
                    settings = step.get("with")
                    self.assertIsInstance(
                        settings, dict, "a privileged checkout must pin its ref explicitly"
                    )
                    ref = settings.get("ref", "")
                    self.assertIsInstance(ref, str)
                    self.assertTrue(ref, "a privileged checkout must pin its ref explicitly")
                    for marker in FORK_HEAD_REF_MARKERS:
                        self.assertNotIn(marker, ref)
                    for marker in FORK_HEAD_REF_MARKERS:
                        self.assertNotIn(marker, str(settings.get("repository", "")))

    def test_privileged_jobs_with_secrets_require_a_reviewed_environment(self) -> None:
        """Moving a secret into an ungated job would hand it to every fork PR automatically."""
        for path, workflow in workflows():
            if "pull_request_target" not in triggers(workflow):
                continue
            with self.subTest(workflow=path.name):
                # A workflow-level env or defaults block reaches ungated jobs too.
                self.assertFalse(contains_secret_expression(workflow.get("env")))
                self.assertFalse(contains_secret_expression(workflow.get("defaults")))
            for name, job in jobs(workflow):
                if not contains_secret_expression(job):
                    continue
                with self.subTest(workflow=path.name, job=name):
                    self.assertEqual(job.get("environment"), REVIEWED_ENVIRONMENT)

    def test_manual_secret_workflows_only_run_trusted_default_branch(self) -> None:
        """A manual run must not check out a caller-selected ref with a live secret."""
        for path, workflow in workflows():
            if "workflow_dispatch" not in triggers(workflow):
                continue
            for name, job in jobs(workflow):
                if not contains_secret_expression(job):
                    continue
                with self.subTest(workflow=path.name, job=name):
                    self.assertEqual(job.get("environment"), REVIEWED_ENVIRONMENT)
                    self.assertIn("${{ secrets.ALCHEMY_API_KEY }}", str(job))
                    self.assertEqual(job.get("if"), DEFAULT_BRANCH_ONLY_CONDITION)
                    checkout_steps = [
                        step
                        for step in steps_of(job)
                        if isinstance(step.get("uses"), str)
                        and step["uses"].startswith("actions/checkout@")
                    ]
                    self.assertEqual(len(checkout_steps), 1)
                    settings = checkout_steps[0].get("with")
                    self.assertIsInstance(settings, dict)
                    self.assertEqual(settings.get("ref"), DEFAULT_BRANCH_REF)

    def test_privileged_validators_use_base_code_and_an_approved_environment(self) -> None:
        """Removing the environment or base-SHA checkout would reintroduce secret exfiltration."""
        validators = {
            "token-lists.yaml": "validate-token-lists",
            "open-positions.yaml": "validate-open-positions",
        }
        for workflow_name, job_name in validators.items():
            path = WORKFLOWS_DIR / workflow_name
            self.assertTrue(path.exists(), f"{workflow_name} must exist")
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            self.assertIsInstance(workflow, dict)
            workflow_jobs = workflow.get("jobs")
            self.assertIsInstance(workflow_jobs, dict)
            job = workflow_jobs.get(job_name)
            self.assertIsInstance(job, dict, f"{workflow_name} must define job {job_name}")

            with self.subTest(workflow=workflow_name):
                self.assertEqual(job.get("environment"), REVIEWED_ENVIRONMENT)
                self.assertTrue(contains_secret_expression(job))
                self.assertIn("${{ secrets.ALCHEMY_API_KEY }}", str(job))
                self.assertIn("materialize_pr_validation_inputs.py", str(job))

                checkout_steps = [
                    step
                    for step in steps_of(job)
                    if isinstance(step.get("uses"), str)
                    and step["uses"].startswith("actions/checkout@")
                ]
                self.assertEqual(len(checkout_steps), 1)
                settings = checkout_steps[0].get("with")
                self.assertIsInstance(settings, dict)
                self.assertEqual(settings.get("ref"), "${{ github.event.pull_request.base.sha }}")

    def test_required_status_checks_are_unconditional_gate_jobs(self) -> None:
        """Branch protection reads a skipped required check as a success.

        The required check must therefore be a job that always runs and inspects
        its dependencies' results, never the conditional privileged job itself.
        """
        for workflow_name, (gate_job_name, check_name) in STATUS_GATE_JOBS.items():
            path = WORKFLOWS_DIR / workflow_name
            self.assertTrue(path.exists(), f"{workflow_name} must exist")
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            self.assertIsInstance(workflow, dict)
            workflow_jobs = workflow.get("jobs")
            self.assertIsInstance(workflow_jobs, dict)
            gate = workflow_jobs.get(gate_job_name)
            self.assertIsInstance(gate, dict, f"{workflow_name} must define job {gate_job_name}")

            with self.subTest(workflow=workflow_name):
                self.assertEqual(gate.get("name"), check_name)
                self.assertEqual(gate.get("if"), "always()")
                # The gate must observe the classifier, otherwise a failed
                # classification would still be reported as a passing check.
                needs = gate.get("needs")
                self.assertIsInstance(needs, list)
                self.assertIn("detect-inputs", needs)
                self.assertTrue(
                    any(need.startswith("validate-") for need in needs),
                    "the gate must observe the validation job result",
                )
                self.assertIn("needs.detect-inputs.result", str(gate))

                # No other job may claim the required status check name.
                duplicates = [
                    name
                    for name, job in jobs(workflow)
                    if name != gate_job_name and job.get("name") == check_name
                ]
                self.assertEqual(duplicates, [])

    def test_codeowners_assigns_protocol_and_security_paths(self) -> None:
        """Missing ownership would let security-critical changes bypass the designated reviewers."""
        self.assertTrue(CODEOWNERS_PATH.exists())
        lines = {
            line.strip()
            for line in CODEOWNERS_PATH.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertTrue(
            {
                "*                    @MakinaHQ/dialectic @platykurtic-icu",
                "/.github/            @MakinaHQ/makina_dev @platykurtic-icu",
                "/scripts/            @MakinaHQ/makina_dev @platykurtic-icu",
                "/tests/              @MakinaHQ/makina_dev @platykurtic-icu",
                "/.github/CODEOWNERS  @MakinaHQ/makina_dev @platykurtic-icu",
            }.issubset(lines)
        )


if __name__ == "__main__":
    unittest.main()
