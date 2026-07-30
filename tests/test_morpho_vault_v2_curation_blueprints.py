from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_ROOT = REPO_ROOT / "blueprints" / "morpho-vault-v2-curation"
INSTRUCTION_FILE = REPO_ROOT / "instructions-x" / "morpho-vault-v2-curation.yaml"
MACHINE_ROOT = REPO_ROOT / "machines" / "morpho-curator"


class MorphoVaultV2CurationBlueprintTests(unittest.TestCase):
    def test_role_partition_files_include_expected_actions(self) -> None:
        expected_actions = {
            "curator.yaml": {
                "submit_curator_call",
                "revoke_curator_call",
                "execute_add_adapter",
                "execute_remove_adapter",
                "execute_set_adapter_registry",
                "execute_set_is_allocator",
                "execute_set_receive_shares_gate",
                "execute_set_send_shares_gate",
                "execute_set_receive_assets_gate",
                "execute_set_send_assets_gate",
                "execute_increase_absolute_cap",
                "decrease_absolute_cap",
                "execute_increase_relative_cap",
                "decrease_relative_cap",
                "execute_set_performance_fee",
                "execute_set_management_fee",
                "execute_set_performance_fee_recipient",
                "execute_set_management_fee_recipient",
                "execute_increase_timelock",
                "execute_decrease_timelock",
                "execute_abdicate",
                "execute_set_force_deallocate_penalty",
            },
            "allocator.yaml": {
                "allocate",
                "deallocate",
                "set_liquidity_adapter_and_data",
                "set_max_rate",
            },
            "sentinel.yaml": {
                "revoke_pending_call",
                "deallocate",
                "decrease_absolute_cap",
                "decrease_relative_cap",
            },
            "permissionless.yaml": {
                "force_deallocate",
                "accrue_interest",
            },
        }

        for filename, actions in expected_actions.items():
            with self.subTest(filename=filename):
                text = (BLUEPRINT_ROOT / filename).read_text()
                for action in actions:
                    self.assertRegex(text, rf"(?m)^  {re.escape(action)}:", action)

    def test_owner_actions_are_not_integrated(self) -> None:
        forbidden_selectors = [
            "setOwner(address)",
            "setCurator(address)",
            "setIsSentinel(address,bool)",
            "setName(string)",
            "setSymbol(string)",
        ]

        for path in BLUEPRINT_ROOT.glob("*.yaml"):
            text = path.read_text()
            for selector in forbidden_selectors:
                with self.subTest(path=path.name, selector=selector):
                    self.assertNotIn(selector, text)

    def test_multicall_is_not_integrated(self) -> None:
        files = [
            BLUEPRINT_ROOT / "permissionless.yaml",
            INSTRUCTION_FILE,
        ]

        for path in files:
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertNotIn("multicall", text)
                self.assertNotIn("multicall(bytes[])", text)

    def test_abdicate_instruction_is_commented_out_until_bytes4_is_supported(self) -> None:
        text = INSTRUCTION_FILE.read_text()

        self.assertNotRegex(
            text,
            r'(?m)^- name: morpho_vault_v2_curator_execute_abdicate$',
        )
        self.assertNotRegex(
            text,
            r'(?m)^\s+path: "\.\./\.\./\.\./blueprints/morpho-vault-v2-curation/curator\.yaml:execute_abdicate"$',
        )
        self.assertIn("# - name: morpho_vault_v2_curator_execute_abdicate", text)
        self.assertIn("prod transpiler supports bytes4 inputs", text)

    def test_curator_timelock_helpers_are_explicit(self) -> None:
        text = (BLUEPRINT_ROOT / "curator.yaml").read_text()

        self.assertIn('selector: "submit(bytes)"', text)
        self.assertIn('selector: "revoke(bytes)"', text)
        self.assertIn("Exact ABI calldata for the underlying timelocked curator call", text)

        readme = (BLUEPRINT_ROOT / "README.md").read_text()
        self.assertIn("The operator-facing app is responsible for ABI encoding", readme)

    def test_morpho_curator_machine_uses_safe_module_instance(self) -> None:
        config = (MACHINE_ROOT / "config.toml").read_text()
        caliber = (MACHINE_ROOT / "mainnet" / "caliber.yaml").read_text()
        instructions = INSTRUCTION_FILE.read_text()

        self.assertIn('name = "morpho-curator"', config)
        self.assertIn('address = "0xD57152f21aB5E5A8b3AdFf197c73aCC2Fdbd1CbD"', config)
        self.assertIn('rootfiles = "github:MakinaHQ/config/machines/morpho-curator/mainnet/rootfiles"', config)

        self.assertIn('safe_address:', caliber)
        self.assertIn('value: "0x3470c3a0717406137dD3c94b5421C2409459b368"', caliber)
        self.assertIn('makina_lite_module:', caliber)
        self.assertIn('value: "0xD57152f21aB5E5A8b3AdFf197c73aCC2Fdbd1CbD"', caliber)
        self.assertIn('description: "Morpho Vault V2 curation - Dialectic WETH Test"', caliber)
        self.assertIn('label: "Dialectic WETH Test"', caliber)
        self.assertIn('vault_address: "0xef3ac91ec3a45f3C6913bFB0C41659919EB85062"', caliber)
        self.assertIn('instructions: !include "../../../instructions-x/morpho-vault-v2-curation.yaml"', caliber)

        self.assertIn('instruction_type: "MANAGEMENT"', instructions)
        self.assertNotIn('instruction_type: "ACCOUNTING"', instructions)
        self.assertIn("../../../blueprints/morpho-vault-v2-curation/curator.yaml:submit_curator_call", instructions)
        self.assertIn("../../../blueprints/morpho-vault-v2-curation/allocator.yaml:allocate", instructions)
        self.assertIn("../../../blueprints/morpho-vault-v2-curation/sentinel.yaml:revoke_pending_call", instructions)
        self.assertIn("../../../blueprints/morpho-vault-v2-curation/permissionless.yaml:accrue_interest", instructions)


if __name__ == "__main__":
    unittest.main()
