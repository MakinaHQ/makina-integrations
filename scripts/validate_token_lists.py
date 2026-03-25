#!/usr/bin/env python3
"""Validate changed token list files against live ERC-20 metadata via Alchemy."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


NETWORK_CONFIG_URL = "https://app-api.alchemy.com/trpc/config.getNetworkConfig"
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

NAME_SELECTOR = "0x06fdde03"
SYMBOL_SELECTOR = "0x95d89b41"
DECIMALS_SELECTOR = "0x313ce567"
TOTAL_SUPPLY_SELECTOR = "0x18160ddd"

# Tether uses ₮ (U+20AE) in name/symbol on some chains — normalize to ASCII "T"
_TETHER_TUGRIK = "\u20ae"


class ValidationError(Exception):
    """Raised for validation failures that should be surfaced in CI."""


@dataclass(frozen=True)
class TokenEntry:
    file_path: Path
    index: int
    chain_id: int
    address: str
    name: str
    symbol: str
    decimals: int


@dataclass(frozen=True)
class TokenIssue:
    file_path: Path
    index: int | None
    chain_id: int | None
    address: str | None
    message: str


@dataclass(frozen=True)
class TokenValidationResult:
    token: TokenEntry
    ok: bool
    issues: list[str]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate changed token list files against live ERC-20 metadata."
    )
    parser.add_argument(
        "token_lists",
        nargs="*",
        help="Token list JSON files relative to the repository root.",
    )
    return parser.parse_args(argv)


def load_token_entries(file_path: Path) -> list[TokenEntry]:
    try:
        raw = json.loads(file_path.read_text())
    except FileNotFoundError as exc:
        raise ValidationError(f"{file_path}: file not found") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{file_path}: invalid JSON ({exc})") from exc

    if not isinstance(raw, dict):
        raise ValidationError(f"{file_path}: expected top-level JSON object")

    tokens = raw.get("tokens")
    if not isinstance(tokens, list):
        raise ValidationError(f"{file_path}: expected top-level 'tokens' array")

    entries: list[TokenEntry] = []
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            raise ValidationError(f"{file_path}: token #{index} must be a JSON object")

        entry = TokenEntry(
            file_path=file_path,
            index=index,
            chain_id=require_int(token, "chainId", file_path, index),
            address=require_address(token, "address", file_path, index),
            name=require_str(token, "name", file_path, index),
            symbol=require_str(token, "symbol", file_path, index),
            decimals=require_int(token, "decimals", file_path, index),
        )
        entries.append(entry)

    return entries


def require_int(token: dict[str, Any], key: str, file_path: Path, index: int) -> int:
    value = token.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{file_path}: token #{index} missing integer '{key}'")
    return value


def require_str(token: dict[str, Any], key: str, file_path: Path, index: int) -> str:
    value = token.get(key)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{file_path}: token #{index} missing string '{key}'")
    return value


def require_address(token: dict[str, Any], key: str, file_path: Path, index: int) -> str:
    value = require_str(token, key, file_path, index)
    if not ADDRESS_RE.fullmatch(value):
        raise ValidationError(f"{file_path}: token #{index} has invalid address '{value}'")
    return value


def normalize_address(address: str) -> str:
    return address.lower()


def normalize_onchain_string(value: str) -> str:
    """Normalize on-chain strings for comparison (e.g. Tether's ₮ to T)."""
    return value.replace(_TETHER_TUGRIK, "T")


def fetch_network_config() -> Any:
    request = Request(
        NETWORK_CONFIG_URL,
        headers={
            "accept": "application/json",
            "user-agent": "makina-token-list-validator/1.0",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        raise ValidationError(
            f"failed to fetch Alchemy network config: HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise ValidationError(f"failed to fetch Alchemy network config: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON from Alchemy network config: {exc}") from exc


def extract_network_mapping(payload: Any) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for chain_id, kebab_case_id in iter_network_entries(payload):
        existing = mapping.get(chain_id)
        if existing is not None and existing != kebab_case_id:
            raise ValidationError(
                f"Alchemy network config returned conflicting kebabCaseId values for chainId {chain_id}: "
                f"{existing!r} vs {kebab_case_id!r}"
            )
        mapping[chain_id] = kebab_case_id

    if not mapping:
        raise ValidationError(
            "Alchemy network config did not contain any networkChainId/kebabCaseId entries"
        )
    return mapping


def iter_network_entries(node: Any) -> Iterable[tuple[int, str]]:
    if isinstance(node, dict):
        chain_id = parse_chain_id(node.get("networkChainId"))
        if chain_id is None:
            chain_id = parse_chain_id(node.get("chainId"))
        kebab_case_id = node.get("kebabCaseId")
        if chain_id is not None and isinstance(kebab_case_id, str) and kebab_case_id:
            yield chain_id, kebab_case_id
        for value in node.values():
            yield from iter_network_entries(value)
        return

    if isinstance(node, list):
        for item in node:
            yield from iter_network_entries(item)


def parse_chain_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def build_rpc_urls(chain_ids: set[int], network_mapping: dict[int, str], api_key: str) -> dict[int, str]:
    rpc_urls: dict[int, str] = {}
    missing_chain_ids = sorted(chain_id for chain_id in chain_ids if chain_id not in network_mapping)
    if missing_chain_ids:
        formatted = ", ".join(str(chain_id) for chain_id in missing_chain_ids)
        raise ValidationError(
            f"Alchemy network config did not include kebabCaseId entries for chain IDs: {formatted}"
        )

    for chain_id in sorted(chain_ids):
        rpc_urls[chain_id] = f"https://{network_mapping[chain_id]}.g.alchemy.com/v2/{api_key}"
    return rpc_urls


class RpcClient:
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.request_id = 0

    def eth_get_code(self, address: str) -> str:
        result = self._rpc("eth_getCode", [address, "latest"])
        if not isinstance(result, str):
            raise ValidationError(f"eth_getCode returned non-string result for {address}")
        return result

    def eth_call(self, address: str, data: str) -> str:
        result = self._rpc("eth_call", [{"to": address, "data": data}, "latest"])
        if not isinstance(result, str):
            raise ValidationError(f"eth_call returned non-string result for {address}")
        return result

    def _rpc(self, method: str, params: list[Any]) -> Any:
        self.request_id += 1
        body = json.dumps(
            {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
        ).encode("utf-8")
        request = Request(
            self.rpc_url,
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as exc:
            raise ValidationError(f"{method} failed with HTTP {exc.code} for {self.rpc_url}") from exc
        except URLError as exc:
            raise ValidationError(f"{method} failed for {self.rpc_url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{method} returned invalid JSON for {self.rpc_url}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValidationError(f"{method} returned unexpected payload type for {self.rpc_url}")
        if "error" in payload:
            raise ValidationError(f"{method} RPC error for {self.rpc_url}: {payload['error']}")
        if "result" not in payload:
            raise ValidationError(f"{method} RPC result missing for {self.rpc_url}")
        return payload["result"]


def decode_uint(result: str) -> int:
    raw = strip_hex_prefix(result)
    if not raw:
        raise ValidationError("expected uint return data, got empty value")
    return int(raw, 16)


def decode_string(result: str) -> str:
    raw = strip_hex_prefix(result)
    if not raw:
        raise ValidationError("expected string return data, got empty value")

    if len(raw) == 64:
        return decode_bytes32_string(raw)

    if len(raw) < 128:
        raise ValidationError(f"unexpected ABI string payload length: {len(raw)}")

    offset = int(raw[:64], 16)
    if offset * 2 > len(raw) - 64:
        raise ValidationError(f"unexpected ABI string offset: {offset}")

    length_start = offset * 2
    length_end = length_start + 64
    if length_end > len(raw):
        raise ValidationError("string length word is out of bounds")

    length = int(raw[length_start:length_end], 16)
    data_start = length_end
    data_end = data_start + (length * 2)
    if data_end > len(raw):
        raise ValidationError("string data is out of bounds")

    try:
        return bytes.fromhex(raw[data_start:data_end]).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"invalid UTF-8 string payload: {exc}") from exc


def decode_bytes32_string(raw: str) -> str:
    value = bytes.fromhex(raw).split(b"\x00", 1)[0]
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"invalid bytes32 UTF-8 payload: {exc}") from exc


def strip_hex_prefix(value: str) -> str:
    if not value.startswith("0x"):
        raise ValidationError(f"expected hex string, got {value!r}")
    return value[2:]


def validate_entries(entries: list[TokenEntry], rpc_urls: dict[int, str]) -> tuple[list[TokenValidationResult], list[TokenIssue]]:
    results: list[TokenValidationResult] = []
    issues: list[TokenIssue] = []
    rpc_clients = {chain_id: RpcClient(url) for chain_id, url in rpc_urls.items()}

    for token in entries:
        client = rpc_clients[token.chain_id]
        token_issues: list[str] = []
        normalized_address = normalize_address(token.address)

        try:
            code = client.eth_get_code(normalized_address)
            if strip_hex_prefix(code) == "":
                token_issues.append("address has no contract bytecode")
            else:
                # totalSupply success is used as the ERC-20 capability check.
                client.eth_call(normalized_address, TOTAL_SUPPLY_SELECTOR)
                onchain_name = normalize_onchain_string(
                    decode_string(client.eth_call(normalized_address, NAME_SELECTOR))
                )
                onchain_symbol = normalize_onchain_string(
                    decode_string(client.eth_call(normalized_address, SYMBOL_SELECTOR))
                )
                onchain_decimals = decode_uint(client.eth_call(normalized_address, DECIMALS_SELECTOR))

                if onchain_name != token.name:
                    token_issues.append(
                        f"name mismatch: token list has {token.name!r}, on-chain has {onchain_name!r}"
                    )
                if onchain_symbol != token.symbol:
                    token_issues.append(
                        f"symbol mismatch: token list has {token.symbol!r}, on-chain has {onchain_symbol!r}"
                    )
                if onchain_decimals != token.decimals:
                    token_issues.append(
                        f"decimals mismatch: token list has {token.decimals}, on-chain has {onchain_decimals}"
                    )
        except ValidationError as exc:
            token_issues.append(str(exc))

        ok = not token_issues
        results.append(TokenValidationResult(token=token, ok=ok, issues=token_issues))
        for message in token_issues:
            issues.append(
                TokenIssue(
                    file_path=token.file_path,
                    index=token.index,
                    chain_id=token.chain_id,
                    address=token.address,
                    message=message,
                )
            )

    return results, issues


def print_issues(issues: list[TokenIssue]) -> None:
    for issue in issues:
        location = f"{issue.file_path}"
        if issue.index is not None:
            location += f" token #{issue.index}"
        chain_part = f" chainId={issue.chain_id}" if issue.chain_id is not None else ""
        address_part = f" address={issue.address}" if issue.address is not None else ""
        print(f"{location}:{chain_part}{address_part} {issue.message}", file=sys.stderr)


def write_github_summary(results: list[TokenValidationResult], issues: list[TokenIssue]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    by_file: dict[Path, list[TokenValidationResult]] = {}
    for result in results:
        by_file.setdefault(result.token.file_path, []).append(result)

    lines = ["## Token List Validation", ""]
    for file_path in sorted(by_file):
        file_results = by_file[file_path]
        failed = sum(1 for result in file_results if not result.ok)
        passed = len(file_results) - failed
        status = "Pass" if failed == 0 else "Fail"
        lines.append(f"### `{file_path}` - {status}")
        lines.append(f"- Tokens checked: {len(file_results)}")
        lines.append(f"- Passed: {passed}")
        lines.append(f"- Failed: {failed}")
        lines.append("")

    if issues:
        lines.append("### Failures")
        for issue in issues:
            identifier = f"`{issue.file_path}`"
            if issue.index is not None:
                identifier += f" token #{issue.index}"
            lines.append(f"- {identifier}: {issue.message}")
        lines.append("")

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.token_lists:
        print("No token list files to validate.")
        return 0

    api_key = os.getenv("ALCHEMY_API_KEY")
    if not api_key:
        print("ALCHEMY_API_KEY is required", file=sys.stderr)
        return 1

    all_entries: list[TokenEntry] = []
    preflight_issues: list[TokenIssue] = []
    for raw_path in args.token_lists:
        file_path = Path(raw_path)
        try:
            all_entries.extend(load_token_entries(file_path))
        except ValidationError as exc:
            preflight_issues.append(
                TokenIssue(
                    file_path=file_path,
                    index=None,
                    chain_id=None,
                    address=None,
                    message=str(exc),
                )
            )

    if preflight_issues:
        print_issues(preflight_issues)
        write_github_summary([], preflight_issues)
        return 1

    if not all_entries:
        print("No tokens found in changed token list files.")
        write_github_summary([], [])
        return 0

    try:
        network_mapping = extract_network_mapping(fetch_network_config())
        rpc_urls = build_rpc_urls({entry.chain_id for entry in all_entries}, network_mapping, api_key)
        results, issues = validate_entries(all_entries, rpc_urls)
    except ValidationError as exc:
        issue = TokenIssue(
            file_path=Path("."),
            index=None,
            chain_id=None,
            address=None,
            message=str(exc),
        )
        print_issues([issue])
        write_github_summary([], [issue])
        return 1

    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(
            f"[{status}] {result.token.file_path} token #{result.token.index} "
            f"chainId={result.token.chain_id} address={result.token.address}"
        )
        for message in result.issues:
            print(f"  - {message}")

    write_github_summary(results, issues)
    if issues:
        print_issues(issues)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
