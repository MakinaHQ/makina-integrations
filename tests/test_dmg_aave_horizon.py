"""Tests for DMG Aave V3 Horizon position wiring."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HORIZON_POOL = "0xAe05Cd22df81871bc7cC2a04BeCfb516bFe332C8"


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_dmg_caliber_contains_horizon_group_positions() -> None:
    caliber = read_text("machines/dmg/mainnet/caliber.yaml")

    assert f'value: "{HORIZON_POOL}"' in caliber
    assert sorted(set(re.findall(r'group_id: "([0-9]+)"', caliber))) == ["0", "1", "2"]

    expected_positions = [
        (
            "333271207406914509852071294122931497073",
            "AaveV3 Horizon Supply mGLOBAL",
            "./instructions/aavev3-horizon-supply-mglobal.yaml",
            "0x49d3cdE03813eE32DFD47F6aA3957d5F9CbAB985",
            "asset_address: ${token_list.mainnet.mGLOBAL}",
            'aave_token: "0x49d3cdE03813eE32DFD47F6aA3957d5F9CbAB985"',
        ),
        (
            "133495794982505815817947498041694656764",
            "AaveV3 Horizon Borrow RLUSD",
            "./instructions/aavev3-horizon-borrow.yaml",
            "0xACE8a1c0eC12aE81814377491265b47F4eE5D3dD",
            "asset_address: ${token_list.mainnet.RLUSD}",
            'debt_token: "0xACE8a1c0eC12aE81814377491265b47F4eE5D3dD"',
        ),
        (
            "317835433613879557430416658618884687921",
            "AaveV3 Horizon Borrow USDC",
            "./instructions/aavev3-horizon-borrow.yaml",
            "0x4139EcBe83d78ef5EFF0A6eDA6f894Be9D590FC7",
            "asset_address: ${token_list.mainnet.USDC}",
            'debt_token: "0x4139EcBe83d78ef5EFF0A6eDA6f894Be9D590FC7"',
        ),
    ]
    for position_id, description, instructions, token, asset_line, reserve_line in expected_positions:
        pattern = (
            rf'- id: "{position_id}".*?'
            rf'group_id: "2".*?'
            rf'description: "{re.escape(description)}".*?'
            rf'instructions: !include "{re.escape(instructions)}".*?'
            rf'position_tokens: \["{token}"\].*?'
            rf'{re.escape(asset_line)}.*?'
            rf'{re.escape(reserve_line)}'
        )
        assert re.search(pattern, caliber, re.S)


def test_dmg_horizon_supply_instruction_sets_emode_5() -> None:
    instructions = read_text(
        "machines/dmg/mainnet/instructions/aavev3-horizon-supply-mglobal.yaml"
    )

    assert re.findall(r'path: "([^"]+)"', instructions) == [
        "../../../blueprints/aave/deposit.yaml:set_e_mode",
        "../../../blueprints/aave/deposit.yaml:add_collateral",
        "../../../blueprints/aave/withdraw.yaml:withdraw_collateral",
        "../../../blueprints/aave/deposit.yaml:set_e_mode",
        "../../../blueprints/aave/account.yaml:account",
    ]
    assert instructions.count('value: "${config.aavev3_horizon_instance}"') == 4
    assert re.search(r'e_mode:\n        type: "uint8"\n        value: "5"', instructions)
    assert re.search(r'e_mode:\n        type: "uint8"\n        value: "0"', instructions)


def test_dmg_horizon_borrow_instruction_uses_horizon_pool() -> None:
    instructions = read_text("machines/dmg/mainnet/instructions/aavev3-horizon-borrow.yaml")

    assert 'path: "../../../blueprints/aave/borrow.yaml:borrow_asset"' in instructions
    assert 'value: "${config.aavev3_horizon_instance}"' in instructions
    assert 'path: "../../../blueprints/aave/repay.yaml:repay_asset"' in instructions
    assert 'path: "../../../blueprints/aave/account.yaml:account"' in instructions
    assert "value: ${position.debt_token}" in instructions


def test_aave_borrow_blueprint_pool_is_configurable() -> None:
    blueprint = read_text("blueprints/aave/borrow.yaml")

    assert "constants:" not in blueprint
    assert "aave_pool_instance:" in blueprint
    assert "target: ${inputs.aave_pool_instance}" in blueprint


def test_aave_borrow_instructions_pass_configured_pool() -> None:
    shared = read_text("instructions/aavev3-borrow.yaml")
    deth_weth = read_text("machines/deth/mainnet/instructions/aavev3-borrow-weth.yaml")

    assert 'value: "${config.aavev3_core_instance}"' in shared
    assert 'value: "${config.aavev3_core_instance}"' in deth_weth
