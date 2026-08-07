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
SHA_PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


def workflows() -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in sorted(WORKFLOWS_DIR.glob("*.yaml")):
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


def job_steps(workflow: dict[str, Any]) -> Iterator[dict[str, Any]]:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict):
                yield step


def contains_secret_expression(value: object) -> bool:
    if isinstance(value, str):
        return "${{ secrets." in value
    if isinstance(value, dict):
        return any(contains_secret_expression(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_secret_expression(item) for item in value)
    return False


class WorkflowSecurityTests(unittest.TestCase):
    def test_all_actions_are_pinned_to_full_commit_shas(self) -> None:
        """Changing an action tag must not silently change code trusted by CI."""
        for path, workflow in workflows():
            for step in job_steps(workflow):
                uses = step.get("uses")
                if isinstance(uses, str):
                    with self.subTest(workflow=path.name, uses=uses):
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
                settings = step.get("with")
                if not isinstance(settings, dict):
                    continue
                with self.subTest(workflow=path.name):
                    self.assertNotIn(
                        "github.event.pull_request.head",
                        settings.get("ref", ""),
                    )

    def test_privileged_validators_use_base_code_and_an_approved_environment(self) -> None:
        """Removing the environment or base-SHA checkout would reintroduce secret exfiltration."""
        validators = {
            "token-lists.yaml": "validate-token-lists",
            "open-positions.yaml": "validate-open-positions",
        }
        for workflow_name, job_name in validators.items():
            path = WORKFLOWS_DIR / workflow_name
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            assert isinstance(workflow, dict)
            jobs = workflow.get("jobs")
            assert isinstance(jobs, dict)
            job = jobs.get(job_name)
            assert isinstance(job, dict)

            with self.subTest(workflow=workflow_name):
                self.assertEqual(job.get("environment"), "pr-validation")
                self.assertTrue(contains_secret_expression(job))
                self.assertIn("ALCHEMY_PR_VALIDATION_KEY", str(job))
                self.assertIn("materialize_pr_validation_inputs.py", str(job))

                checkout_steps = [
                    step
                    for step in job_steps({"jobs": {job_name: job}})
                    if isinstance(step.get("uses"), str)
                    and step["uses"].startswith("actions/checkout@")
                ]
                self.assertEqual(len(checkout_steps), 1)
                settings = checkout_steps[0].get("with")
                self.assertIsInstance(settings, dict)
                self.assertEqual(settings.get("ref"), "${{ github.event.pull_request.base.sha }}")

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
