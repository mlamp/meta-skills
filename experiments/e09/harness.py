#!/usr/bin/env python3
"""E-09 frozen experiment harness.

Commands:
  validate                         validate frozen inputs and matchers
  freeze                           write freeze.json once after final review
  preflight [--profiles N ...]     check configured model identities
  cold-reader --tier smoke|qualification [--profiles N ...]
  adapter-smoke                    exercise every measured adapter on disjoint inputs
  render --arm control|treatment  print the exact interview prompt
  schedule                         print the seeded measured call order
  interviews                      run the gated measured interview batch
  tasks                           run gated downstream task calls
  judge                           run blinded task and substitute judgments
  finalize                        compute metrics and append ledger records

Claude-family calls use the CLI's provider-enforced `StructuredOutput` tool.
DeepInfra calls use a required `submit_evaluation` function tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


E09 = Path(__file__).resolve().parent
ROOT = E09.parent.parent
LEDGER = ROOT / "ledger" / "runs.jsonl"
RAW = E09 / "raw"
DATA_FILES = {
    name: E09 / name
    for name in (
        "catalog.json",
        "cold_reader_cases.json",
        "models.json",
        "persona-stage1.json",
        "persona.json",
        "prompts.json",
        "substitutes.json",
        "tasks.json",
    )
}
FREEZE_INPUTS = tuple(DATA_FILES.values()) + (E09 / "design.md", E09 / "harness.py", E09 / "reviews.md", E09 / "test_harness.py")
REPS = 5
SEED = 20260821
JUDGE_SEED = 20260822
TOOL_NAME = "submit_evaluation"
CLAUDE_STRUCTURED_TOOL = "StructuredOutput"
LEXICAL = re.compile(r"\b[\w'-]+\b", re.UNICODE)
HOST_METADATA_KEYS = {"cwd", "memory_paths", "plugins", "request_id", "session_id", "thread_id", "uuid"}
SECRET_METADATA_KEYS = {
    "accesstoken", "apikey", "authorization", "clientsecret", "credential", "credentials",
    "password", "privatekey", "refreshtoken", "secret", "token", "xapikey",
}
HOST_PATH = re.compile(
    r"(?<![A-Za-z0-9:])/(?:Users|home)/[^/\s\"']+(?:/[^\s\"']*)?"
    r"|(?<![A-Za-z0-9:])/(?:private/)?var/folders/[^\s\"']+"
    r"|(?<![A-Za-z0-9:])/tmp/[^\s\"']+"
    r"|\b[A-Za-z]:\\Users\\[^\\\s\"']+(?:\\[^\s\"']*)?"
)
HOST_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
SECRET_ASSIGNMENT = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD))\s*=\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)
BEARER_SECRET = re.compile(r"\b(Bearer)\s+[A-Za-z0-9][A-Za-z0-9._~+/=-]*", re.IGNORECASE)


class HarnessError(RuntimeError):
    def __init__(self, message, evidence=None):
        super().__init__(message)
        self.evidence = evidence


class TransportError(HarnessError):
    pass


class RequestError(HarnessError):
    pass


class FormatError(HarnessError):
    pass


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sanitize_host_metadata(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
            if key in HOST_METADATA_KEYS or normalized_key in SECRET_METADATA_KEYS:
                continue
            if key == "executable" and isinstance(item, str):
                cleaned[key] = Path(item).name
            else:
                cleaned[key] = sanitize_host_metadata(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_host_metadata(item) for item in value]
    if isinstance(value, str):
        value = SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<SECRET>", value)
        value = BEARER_SECRET.sub(lambda match: f"{match.group(1)} <SECRET>", value)
        return HOST_UUID.sub("<ID>", HOST_PATH.sub("<HOST_PATH>", value))
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value, length=16) -> str:
    raw = value if isinstance(value, bytes) else canonical(value).encode()
    return hashlib.sha256(raw).hexdigest()[:length]


def sha256_value(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json_atomic(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def write_json_exclusive(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise HarnessError(f"immutable attempt already exists: {path}") from exc
    try:
        os.write(fd, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def jsonl_run_ids(path: Path):
    data = path.read_bytes() if path.exists() else b""
    if data and not data.endswith(b"\n"):
        raise HarnessError(f"{path} does not end in a newline")
    run_ids = set()
    for number, raw in enumerate(data.splitlines(), 1):
        try:
            row = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HarnessError(f"{path}:{number} is not valid JSON") from exc
        if not isinstance(row, dict):
            raise HarnessError(f"{path}:{number} is not a JSON object")
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise HarnessError(f"{path}:{number} requires a non-empty string run_id")
        run_ids.add(run_id)
    return run_ids


def append_jsonl(path: Path, value):
    run_id = value.get("run_id") if isinstance(value, dict) else None
    if not isinstance(run_id, str) or not run_id:
        raise HarnessError("JSONL records require a non-empty string run_id")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        os.close(fd)
    except FileExistsError:
        pass
    if run_id in jsonl_run_ids(path):
        raise HarnessError(f"duplicate run_id {run_id}")
    encoded = canonical(value).encode() + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines without shell evaluation."""
    result = {}
    if not path.exists():
        return result
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise HarnessError(f".env:{number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise HarnessError(f".env:{number}: invalid key name")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key] = value
    return result


def credential(name: str) -> str:
    value = os.environ.get(name) or read_dotenv(ROOT / ".env").get(name)
    if not value:
        raise HarnessError(f"missing credential {name}; set it in the environment or ignored .env")
    return value


def catalog_markdown(catalog=None) -> str:
    catalog = catalog or load_json(DATA_FILES["catalog.json"])
    lines = ["## Candidate recognition catalog", "", "Purpose: " + catalog["purpose"], "", catalog["introduction"], ""]
    for entry in catalog["entries"]:
        suffix = ""
        if entry["sublabels"]:
            definitions = catalog["sublabel_definitions"]
            suffix = " Sublabels: " + "; ".join(
                f"{name} = {definitions[name]}" for name in entry["sublabels"]
            ) + "."
        lines += [
            f"- {entry['id']} · {entry['label']}: {entry['prompt']}",
            f"  Boundary: {entry['boundary']}{suffix}",
        ]
    lines += ["", "Overlap precedence: " + " > ".join(catalog["overlap_precedence"]) + "."]
    return "\n".join(lines) + "\n"


def render_interview(arm: str) -> str:
    if arm not in ("control", "treatment"):
        raise HarnessError(f"unknown arm {arm}")
    prompts = load_json(DATA_FILES["prompts.json"])["interview"]
    persona = load_json(DATA_FILES["persona-stage1.json"])
    inventory = [
        {"id": "I01", "text": f"Verbosity: {persona['inventory']['verbosity']}"},
        {"id": "I02", "text": "Unaided recall: " + "; ".join(
            next(p["preference"] for p in persona["preferences"] if p["id"] == item)
            for item in persona["unaided_recall_ids"]
        )},
        {"id": "I03", "text": "Limits: " + "; ".join(persona["limits"])},
        {"id": "I04", "text": "Opt-ins selected: none. Opt-ins rejected: reference codes."},
    ]
    slot = prompts["control_slot"]
    if arm == "treatment":
        slot = prompts["treatment_slot"] + "\n\n" + catalog_markdown().rstrip()
    sections = [
        prompts["shared_instruction"],
        "## Frozen inventory\n\n" + "\n".join(f"- {row['id']}: {row['text']}" for row in inventory),
        "## Shared observations\n\n" + "\n".join(f"- {row['id']}: {row['text']}" for row in prompts["shared_observations"]),
        "## Interview attachment\n\n" + slot,
        "## Contract format\n\n" + prompts["contract_format"],
    ]
    return "\n\n".join(sections) + "\n"


def schema_type_ok(value, expected) -> bool:
    choices = expected if isinstance(expected, list) else [expected]
    for choice in choices:
        if choice == "null" and value is None:
            return True
        if choice == "object" and isinstance(value, dict):
            return True
        if choice == "array" and isinstance(value, list):
            return True
        if choice == "string" and isinstance(value, str):
            return True
        if choice == "boolean" and isinstance(value, bool):
            return True
        if choice == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if choice == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
    return False


def validate_schema(value, schema, path="$", errors=None):
    errors = errors if errors is not None else []
    if "type" in schema and not schema_type_ok(value, schema["type"]):
        errors.append(f"{path}: expected {schema['type']}")
        return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is outside the closed vocabulary")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing {key}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: unexpected {key}")
        for key, child in value.items():
            if key in props:
                validate_schema(child, props[key], f"{path}.{key}", errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: too many items")
        if schema.get("uniqueItems") and len({canonical(v) for v in value}) != len(value):
            errors.append(f"{path}: duplicate items")
        for index, child in enumerate(value):
            if "items" in schema:
                validate_schema(child, schema["items"], f"{path}[{index}]", errors)
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        errors.append(f"{path}: string is too short")
    return errors


def object_schema(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


def array_schema(items, count=None, unique=False):
    schema = {"type": "array", "items": items}
    if unique:
        schema["uniqueItems"] = True
    if count is not None:
        schema.update({"minItems": count, "maxItems": count})
    return schema


def case_schema(case):
    ids = ["U01", "U02", "U03", "U04", "U05", "U06"]
    sublabels = ["opener", "closer", "filler", "hedge_stack", "abstraction", "promotion", "unsupported_result"]
    base = {"case_id": {"type": "string", "const": case["id"]}}
    if case["kind"] == "semantics":
        base.update({
            "purpose": {"type": "string", "enum": ["recognition_aid", "default_rule_set", "effectiveness_evidence"]},
            "automatic_bans": {"type": "boolean"},
            "contract_eligibility": {"type": "string", "enum": ["selected_only", "all_entries", "selected_and_automatic"]},
            "unselected_reaches_contract": {"type": "boolean"},
            "precedence": array_schema({"type": "string", "enum": ids}, 6, True),
            "sublabels": object_schema({
                uid: array_schema({"type": "string", "enum": sublabels}, unique=True) for uid in ids
            }),
        })
        return object_schema(base)
    if case["kind"] in ("classifications", "smoke_classifications"):
        allowed = ids if case["kind"] == "classifications" else ["M01", "M02"]
        labels = sublabels + [None] if case["kind"] == "classifications" else [None]
        answer = object_schema({
            "item_id": {"type": "string", "minLength": 1},
            "pattern_id": {"type": ["string", "null"], "enum": allowed + [None]},
            "sublabel": {"type": ["string", "null"], "enum": labels},
        })
        base["answers"] = array_schema(answer, len(case["items"]), unique=True)
        return object_schema(base)
    if case["kind"] == "selections":
        answer = object_schema({
            "item_id": {"type": "string"},
            "selected_ids": array_schema({"type": "string", "enum": ids}, unique=True),
            "rejected_ids": array_schema({"type": "string", "enum": ids}, unique=True),
            "automatic_bans": array_schema({"type": "string", "enum": ids}, unique=True),
        })
        base["answers"] = array_schema(answer, len(case["items"]))
        return object_schema(base)
    raise HarnessError(f"unknown case kind {case['kind']}")


def contract_schema(arm: str):
    evidence_ids = [f"I{i:02d}" for i in range(1, 5)] + [f"O{i:02d}" for i in range(1, 10)]
    uids = [f"U{i:02d}" for i in range(1, 7)]
    rule_props = {
        "text": {"type": "string", "minLength": 3},
        "evidence_ids": array_schema({"type": "string", "enum": evidence_ids}, unique=True),
    }
    if arm == "treatment":
        rule_props["catalog_ids"] = array_schema({"type": "string", "enum": uids}, unique=True)
    props = {
        "selected_evidence_ids": array_schema({"type": "string", "enum": evidence_ids}, unique=True),
        "rules": array_schema(object_schema(rule_props), unique=True),
        "contract": {"type": "string", "minLength": 3},
    }
    if arm == "treatment":
        props.update({
            "selected_catalog_ids": array_schema({"type": "string", "enum": uids}, unique=True),
            "rejected_catalog_ids": array_schema({"type": "string", "enum": uids}, unique=True),
            "automatic_bans": array_schema({"type": "string", "enum": uids}, unique=True),
        })
    return object_schema(props)


def contract_violations(arm: str, payload):
    """Return measured semantic violations without converting them to transport errors."""
    selected_evidence = set(payload.get("selected_evidence_ids", []))
    selected_catalog = set(payload.get("selected_catalog_ids", []))
    rejected_catalog = set(payload.get("rejected_catalog_ids", []))
    violations = []
    contract = payload.get("contract", "")
    if re.search(r"\b[UV]\d{2}\b", contract):
        violations.append("contract_exposes_internal_id")
    if payload.get("automatic_bans"):
        violations.append("automatic_bans_nonempty")
    if selected_catalog & rejected_catalog:
        violations.append("selected_and_rejected_catalog_overlap")
    contract_tokens = [token.lower() for token in LEXICAL.findall(contract)]
    rule_set_tokens = [
        token.lower()
        for rule in payload.get("rules", [])
        for token in LEXICAL.findall(rule.get("text", ""))
    ]
    if contract_tokens != rule_set_tokens:
        violations.append("contract_does_not_exactly_match_rules")
    for index, rule in enumerate(payload.get("rules", []), 1):
        evidence_ids = set(rule.get("evidence_ids", []))
        catalog_ids = set(rule.get("catalog_ids", []))
        if not evidence_ids and not catalog_ids:
            violations.append(f"rule_{index}_has_no_source")
        if not evidence_ids <= selected_evidence:
            violations.append(f"rule_{index}_uses_unselected_evidence")
        if evidence_ids & {"I04", "O09"}:
            violations.append(f"rule_{index}_uses_rejected_evidence")
        if arm == "treatment":
            if not catalog_ids <= selected_catalog:
                violations.append(f"rule_{index}_uses_unselected_catalog_id")
            if catalog_ids & rejected_catalog:
                violations.append(f"rule_{index}_uses_rejected_catalog_id")
        rule_tokens = [token.lower() for token in LEXICAL.findall(rule.get("text", ""))]
        present = any(contract_tokens[start:start + len(rule_tokens)] == rule_tokens
                      for start in range(0, len(contract_tokens) - len(rule_tokens) + 1)) if rule_tokens else False
        if rule_tokens and not present:
            violations.append(f"rule_{index}_missing_from_contract")
    return sorted(set(violations))


def task_judge_schema(task_id: str, required_count: int, fatal_count: int):
    return object_schema({
        "task_id": {"type": "string", "const": task_id},
        "required_pass": array_schema({"type": "boolean"}, required_count),
        "fatal_hits": array_schema({"type": "boolean"}, fatal_count),
    })


def substitute_judge_schema(candidate_ids):
    verdict = object_schema({
        "candidate_id": {"type": "string", "enum": candidate_ids},
        "pattern_id": {"type": ["string", "null"], "enum": [f"U{i:02d}" for i in range(1, 7)] + [None]},
    })
    return object_schema({"verdicts": array_schema(verdict, len(candidate_ids))})


def validate_substitute_payload(payload, candidate_ids):
    actual = [row.get("candidate_id") for row in payload.get("verdicts", [])]
    if actual != candidate_ids:
        raise FormatError("substitute verdicts must cover each candidate once in frozen order", {"payload": payload})


def parse_claude_stream(stdout: str, expected_tool: str):
    calls = []
    result_event = None
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    calls.append({"name": block.get("name"), "input": block.get("input")})
        if event.get("type") == "result":
            result_event = event
    matching = [call for call in calls if call["name"] == expected_tool]
    if len(calls) != 1 or len(matching) != 1:
        raise FormatError(f"expected one {expected_tool} call; received {[call['name'] for call in calls]}")
    return matching[0]["input"], result_event, events


def call_claude_tool(profile, prompt, schema):
    executable = "claude" if profile["adapter"] == "claude_cli" else "claude-kimi"
    with tempfile.TemporaryDirectory(prefix="e09-tool-") as tmp_name:
        tmp = Path(tmp_name)
        cmd = [
            executable, "-p", "--model", profile["model"],
            "--no-session-persistence", "--safe-mode", "--disable-slash-commands",
            "--tools", "", "--json-schema", canonical(schema),
            "--permission-mode", "dontAsk", "--output-format", "stream-json", "--verbose",
        ]
        if profile.get("effort") not in (None, "default"):
            cmd += ["--effort", profile["effort"]]
        call_env = dict(os.environ)
        slot_path = tmp / "kimi-slot"
        if profile["adapter"] == "kimi_cli":
            call_env["CLAUDE_KIMI_SLOT_FILE"] = str(slot_path)
        try:
            proc = subprocess.run(
                cmd, input=prompt, text=True, capture_output=True, cwd=tmp,
                timeout=profile["timeout_seconds"], env=call_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportError(f"{executable} timed out") from exc
        if proc.returncode:
            raise TransportError(f"{executable} exited {proc.returncode}: {proc.stderr[-500:]}")
        try:
            payload, result_event, events = parse_claude_stream(proc.stdout, CLAUDE_STRUCTURED_TOOL)
        except FormatError as exc:
            result_events = []
            for line in proc.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "result":
                    result_events.append(event)
            if result_events and (result_events[-1].get("is_error") or result_events[-1].get("subtype") != "success"):
                raise TransportError("Claude-family provider returned an error result",
                                     {"result": result_events[-1], "stderr_tail": proc.stderr[-1000:]}) from exc
            exc.evidence = {"stdout": proc.stdout, "stderr_tail": proc.stderr[-1000:]}
            raise
        if not result_event or result_event.get("is_error") or result_event.get("subtype") != "success":
            raise TransportError("Claude-family provider did not return a success envelope",
                                 {"result": result_event, "stderr_tail": proc.stderr[-1000:]})
        if result_event.get("structured_output") != payload:
            raise FormatError("Claude structured result disagrees with its tool arguments",
                              {"payload": payload, "result": result_event})
        errors = validate_schema(payload, schema)
        if errors:
            raise FormatError("; ".join(errors), {"payload": payload, "events": events, "stderr_tail": proc.stderr[-1000:]})
        model_usage = (result_event or {}).get("modelUsage", {})
        return payload, {
            "adapter": profile["adapter"],
            "requested_model": profile["model"],
            "reported_models": sorted(model_usage),
            "reported_providers": sorted({row.get("provider") for row in model_usage.values() if row.get("provider")}),
            "usage": (result_event or {}).get("usage"),
            "stop_reason": (result_event or {}).get("stop_reason"),
            "configuration_isolation": "safe_mode_ephemeral_cwd_explicit_effort",
            "structured_interface": "claude_cli_StructuredOutput_tool",
            "kimi_slot": slot_path.read_text().strip() if slot_path.exists() else None,
            "events": events,
            "stderr_tail": proc.stderr[-500:],
        }


def deepinfra_request(profile, body, method="POST", path="/chat/completions"):
    api_base = profile["api_base"].rstrip("/")
    request = urllib.request.Request(
        api_base + path,
        data=canonical(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + credential(profile["credential_env"]), "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=profile["timeout_seconds"]) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RequestError(f"DeepInfra HTTP {exc.code}: authentication failed") from exc
        detail = exc.read().decode(errors="replace")[:300]
        if 400 <= exc.code < 500 and exc.code != 429:
            raise RequestError(f"DeepInfra HTTP {exc.code}: {detail}") from exc
        raise TransportError(f"DeepInfra HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TransportError(f"DeepInfra transport failure: {exc}") from exc


def call_deepinfra_tool(profile, prompt, schema):
    body = {
        "model": profile["model"],
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "function", "function": {
            "name": TOOL_NAME,
            "description": "Submit the completed evaluation. Call exactly once.",
            "parameters": schema,
        }}],
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "temperature": profile["temperature"],
        "stream": False,
    }
    raw = deepinfra_request(profile, body)
    choices = raw.get("choices", [])
    calls = choices[0].get("message", {}).get("tool_calls", []) if len(choices) == 1 else []
    if len(calls) != 1 or calls[0].get("function", {}).get("name") != TOOL_NAME:
        raise FormatError("DeepInfra model did not make exactly one required tool call", {"raw": raw})
    arguments = calls[0]["function"].get("arguments")
    try:
        payload = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as exc:
        raise FormatError("DeepInfra model returned invalid tool arguments", {"raw": raw}) from exc
    errors = validate_schema(payload, schema)
    if errors:
        raise FormatError("; ".join(errors), {"payload": payload, "raw": raw})
    return payload, {
        "adapter": "deepinfra_api",
        "provider": profile["provider"],
        "requested_model": profile["model"],
        "reported_models": [raw.get("model")],
        "usage": raw.get("usage"),
        "system_fingerprint": raw.get("system_fingerprint"),
        "raw": raw,
    }


def call_tool(profile, prompt, schema):
    if profile["adapter"] in ("claude_cli", "kimi_cli"):
        result = call_claude_tool(profile, prompt, schema)
    elif profile["adapter"] == "deepinfra_api":
        result = call_deepinfra_tool(profile, prompt, schema)
    else:
        raise HarnessError(f"adapter {profile['adapter']} has no tool-call implementation")
    payload, meta = result
    required = profile.get("reported_identity_required")
    allowed = {required, *profile.get("allowed_auxiliary_models", [])} if required else set()
    reported = set(meta.get("reported_models", []))
    if required and (required not in reported or not reported <= allowed):
        raise FormatError(f"reported model {meta.get('reported_models')} does not match required identity {required}", meta)
    provider = profile.get("reported_provider_required")
    if provider and provider not in meta.get("reported_providers", []):
        raise FormatError(f"reported provider {meta.get('reported_providers')} does not match {provider}", meta)
    return payload, meta


def call_text(profile, prompt: str, system_text: str):
    if profile["adapter"] not in ("claude_cli", "kimi_cli"):
        raise HarnessError(f"text adapter is not implemented for {profile['adapter']}")
    executable = "claude" if profile["adapter"] == "claude_cli" else "claude-kimi"
    with tempfile.TemporaryDirectory(prefix="e09-text-") as tmp_name:
        tmp = Path(tmp_name)
        system_path = tmp / "contract.md"
        system_path.write_text(system_text, encoding="utf-8")
        cmd = [
            executable, "-p", "--model", profile["model"], "--no-session-persistence",
            "--safe-mode", "--disable-slash-commands", "--tools", "", "--output-format", "json",
            "--append-system-prompt-file", str(system_path),
        ]
        if profile.get("effort") not in (None, "default"):
            cmd += ["--effort", profile["effort"]]
        call_env = dict(os.environ)
        slot_path = tmp / "kimi-slot"
        if profile["adapter"] == "kimi_cli":
            call_env["CLAUDE_KIMI_SLOT_FILE"] = str(slot_path)
        try:
            proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True, cwd=tmp,
                                  timeout=profile["timeout_seconds"], env=call_env)
        except subprocess.TimeoutExpired as exc:
            raise TransportError(f"{executable} timed out") from exc
        if proc.returncode:
            raise TransportError(f"{executable} exited {proc.returncode}: {proc.stderr[-500:]}")
        payload = None
        for line in proc.stdout.splitlines():
            if line.lstrip().startswith("{"):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
        if not payload or not isinstance(payload.get("result"), str):
            raise FormatError(f"unparseable {executable} text result", {"stdout": proc.stdout, "stderr_tail": proc.stderr[-1000:]})
        if payload.get("is_error") or payload.get("subtype") != "success":
            raise TransportError("Claude-family provider did not return a success envelope",
                                 {"result": payload, "stderr_tail": proc.stderr[-1000:]})
        model_usage = payload.get("modelUsage", {})
        meta = {
            "requested_model": profile["model"],
            "reported_models": sorted(model_usage),
            "reported_providers": sorted({row.get("provider") for row in model_usage.values() if row.get("provider")}),
            "usage": payload.get("usage"),
            "configuration_isolation": "safe_mode_ephemeral_cwd_explicit_effort",
            "kimi_slot": slot_path.read_text().strip() if slot_path.exists() else None,
            "raw": payload,
        }
        required = profile.get("reported_identity_required")
        allowed = {required, *profile.get("allowed_auxiliary_models", [])} if required else set()
        reported = set(meta["reported_models"])
        if required and (required not in reported or not reported <= allowed):
            raise FormatError(f"reported model {meta['reported_models']} does not match required identity {required}", meta)
        provider = profile.get("reported_provider_required")
        if provider and provider not in meta["reported_providers"]:
            raise FormatError(f"reported provider {meta['reported_providers']} does not match {provider}", meta)
        return payload["result"], meta


def case_prompt(case, smoke=False):
    suite = load_json(DATA_FILES["cold_reader_cases.json"])
    catalog = suite["smoke"]["catalog"] if smoke else None
    catalog_text = "\n".join(
        f"- {entry['id']} · {entry['label']}: {entry['meaning']} Boundary: {entry['boundary']}"
        for entry in catalog
    ) + "\n" if smoke else catalog_markdown()
    parts = [
        "Read the catalog and apply it literally. Do not infer a broader style policy.",
        catalog_text.rstrip(),
        case.get("question", "Classify each item against the smoke catalog."),
        canonical(case.get("items", [])),
        "Call the required submission tool exactly once. Put the answer only in its arguments. Do not answer in prose.",
    ]
    return "\n\n".join(parts) + "\n"


def grade_case(case, payload):
    assertions = []

    def add(name, actual, expected, unordered=False):
        if unordered:
            actual = sorted(actual, key=canonical)
            expected = sorted(expected, key=canonical)
        assertions.append({"assertion": name, "pass": actual == expected, "actual": actual, "expected": expected})

    add("case_id", payload.get("case_id"), case["id"])
    expected = case["expected"]
    if case["kind"] == "semantics":
        for key in ("purpose", "automatic_bans", "contract_eligibility", "unselected_reaches_contract", "precedence"):
            add(key, payload.get(key), expected[key])
        actual_labels = payload.get("sublabels", {})
        for uid, labels in expected["sublabels"].items():
            add(f"sublabels.{uid}", actual_labels.get(uid), labels, unordered=True)
    else:
        actual_rows = {row.get("item_id"): row for row in payload.get("answers", [])}
        expected_rows = {row["item_id"]: row for row in expected}
        add("item_ids", sorted(actual_rows), sorted(expected_rows))
        for item_id, row in expected_rows.items():
            actual = actual_rows.get(item_id, {})
            for key, value in row.items():
                if key == "item_id":
                    continue
                add(f"{item_id}.{key}", actual.get(key), value, unordered=isinstance(value, list))
    return assertions


def profile_map():
    return load_json(DATA_FILES["models.json"])["profiles"]


def validate_inputs(check_freeze=True):
    errors = []
    for path in DATA_FILES.values():
        if not path.exists():
            errors.append(f"missing {path.name}")
    if errors:
        return errors
    catalog = load_json(DATA_FILES["catalog.json"])
    ids = [entry["id"] for entry in catalog["entries"]]
    if ids != [f"U{i:02d}" for i in range(1, 7)]:
        errors.append("catalog IDs must be U01-U06 in precedence order")
    if catalog["overlap_precedence"] != ids:
        errors.append("catalog precedence must match entry order")
    cases = load_json(DATA_FILES["cold_reader_cases.json"])
    for case in cases["qualification"]["cases"]:
        schema_errors = validate_schema({"case_id": case["id"]}, case_schema(case))
        if not schema_errors:
            errors.append(f"{case['id']} schema unexpectedly accepts an incomplete payload")
        item_ids = [row["item_id"] for row in case.get("items", [])]
        expected_ids = [row["item_id"] for row in case.get("expected", [])] if isinstance(case.get("expected"), list) else []
        if item_ids and item_ids != expected_ids:
            errors.append(f"{case['id']} items and answer key differ")
    substitutes = load_json(DATA_FILES["substitutes.json"])
    if substitutes["precedence"] != ids:
        errors.append("matcher precedence differs from catalog")
    for family in ("listed", "substitute"):
        if sorted(substitutes[family]) != ids:
            errors.append(f"{family} matcher keys differ from catalog")
        for uid, patterns in substitutes[family].items():
            for pattern in patterns:
                try:
                    re.compile(pattern, re.IGNORECASE)
                except re.error as exc:
                    errors.append(f"invalid {family}.{uid} regex: {exc}")
    listed = {pattern for pats in substitutes["listed"].values() for pattern in pats}
    adjacent = {pattern for pats in substitutes["substitute"].values() for pattern in pats}
    if listed & adjacent:
        errors.append("listed and substitute regexes overlap exactly")
    models = load_json(DATA_FILES["models.json"])
    if models["qualification_profiles"] != ["haiku-reader", "deepseek-reader"]:
        errors.append("required reader profiles changed")
    if check_freeze and (E09 / "freeze.json").exists():
        frozen = load_json(E09 / "freeze.json")["files"]
        for path in FREEZE_INPUTS:
            rel = str(path.relative_to(ROOT))
            if frozen.get(rel) != sha256(path):
                errors.append(f"freeze mismatch: {rel}")
        extras = set(frozen) - {str(path.relative_to(ROOT)) for path in FREEZE_INPUTS}
        if extras:
            errors.append("freeze lists unexpected files: " + ", ".join(sorted(extras)))
    return errors


def cmd_validate(args):
    errors = validate_inputs()
    if errors:
        for error in errors:
            print("FAIL", error)
        raise SystemExit(1)
    suffix = ", and freeze" if (E09 / "freeze.json").exists() else " (freeze not written yet)"
    print("PASS inputs, schemas, matchers" + suffix)


def preflight_one(name, profile):
    adapter = profile["adapter"]
    if adapter in ("claude_cli", "kimi_cli"):
        executable = "claude" if adapter == "claude_cli" else "claude-kimi"
        path = shutil.which(executable)
        if not path:
            raise HarnessError(f"{executable} is not installed")
        proc = subprocess.run([path, "--version"], text=True, capture_output=True, timeout=30)
        return {"profile": name, "ok": proc.returncode == 0, "adapter": adapter,
                "executable": Path(path).name, "version": proc.stdout.strip() or proc.stderr.strip()}
    if adapter == "codex_cli":
        path = os.environ.get(profile.get("binary_env", "E09_CODEX_BIN")) or shutil.which("codex")
        if not path:
            raise HarnessError("codex is not installed")
        proc = subprocess.run([path, "--version"], text=True, capture_output=True, timeout=30)
        version_text = proc.stdout.strip() or proc.stderr.strip()
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_text)
        actual = tuple(map(int, match.groups())) if match else (0, 0, 0)
        required = tuple(map(int, profile.get("minimum_cli_version", "0.0.0").split(".")))
        return {"profile": name, "ok": proc.returncode == 0 and actual >= required, "adapter": adapter,
                "executable": Path(path).name, "version": version_text,
                "minimum_version": profile.get("minimum_cli_version")}
    if adapter == "deepinfra_api":
        raw = deepinfra_request(profile, None, method="GET", path="/models")
        available = sorted(item.get("id") for item in raw.get("data", []))
        return {"profile": name, "ok": profile["model"] in available, "adapter": adapter,
                "requested_model": profile["model"], "available_count": len(available),
                "requested_model_available": profile["model"] in available}
    raise HarnessError(f"unknown adapter {adapter}")


def cmd_preflight(args):
    profiles = profile_map()
    names = args.profiles or list(profiles)
    failed = False
    for name in names:
        if name not in profiles:
            print(canonical({"profile": name, "ok": False, "error": "unknown profile"}))
            failed = True
            continue
        try:
            result = preflight_one(name, profiles[name])
        except Exception as exc:
            result = {"profile": name, "ok": False, "error": str(exc)}
        print(canonical(result))
        failed = failed or not result.get("ok")
    if failed:
        raise SystemExit(1)


def cold_reader_namespace(tier, profile_name):
    suite = load_json(DATA_FILES["cold_reader_cases.json"])
    profile = profile_map()[profile_name]
    key = {
        "tier": tier,
        "profile": profile_name,
        "profile_sha256": sha256_value(profile),
        "harness_sha256": sha256(E09 / "harness.py"),
        "catalog_sha256": sha256(DATA_FILES["catalog.json"]),
        "suite_sha256": sha256(DATA_FILES["cold_reader_cases.json"]),
    }
    if tier == "qualification" and (E09 / "freeze.json").exists():
        key["freeze_sha256"] = sha256(E09 / "freeze.json")
    return RAW / tier / ("cr-" + digest(key)), key


def adapter_smoke_namespace():
    key = {
        "harness_sha256": sha256(E09 / "harness.py"),
        "models_sha256": sha256(DATA_FILES["models.json"]),
        "prompts_sha256": sha256(DATA_FILES["prompts.json"]),
    }
    return RAW / "smoke" / "adapters" / ("as-" + digest(key)), key


def next_smoke_attempt(base: Path) -> Path:
    numbers = []
    if base.exists():
        for path in base.glob("attempt-*"):
            match = re.fullmatch(r"attempt-(\d{3})", path.name)
            if match:
                numbers.append(int(match.group(1)))
    return base / f"attempt-{max(numbers, default=0) + 1:03d}"


def passed_smoke_attempt(base: Path):
    attempts = sorted(base.glob("attempt-*")) if base.exists() else []
    if not attempts:
        return None
    latest = attempts[-1]
    summary = latest / "summary.json"
    return latest if summary.exists() and load_json(summary).get("passed") else None


def cold_reader_ledger_line(summary, namespace):
    payload = {
        "schema_version": 2,
        "type": "experiment",
        "experiment": "E-09-cold-reader",
        "family": summary["profile"],
        "tier": summary["tier"],
        "passed": summary["passed"],
        "started_calls": summary["started_calls"],
        "assertions": summary["assertions"],
        "failed_assertions": summary["failed_assertions"],
        "errors": summary["errors"],
        "key": summary["key"],
        "raw_dir": str(namespace.relative_to(ROOT)),
        "completed_at": summary["completed_at"],
    }
    completed_day = summary["completed_at"][:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", completed_day):
        raise HarnessError("cold-reader summary requires an ISO completed_at timestamp")
    run_id = "r-" + completed_day.replace("-", "") + "-" + digest(payload, 10)
    return {"run_id": run_id, "date": summary["completed_at"], **payload}


def ensure_qualification_summary_ledger(summary_path, summary, namespace):
    if summary.get("tier") != "qualification":
        raise HarnessError("only qualification summaries are ledgered")
    line = cold_reader_ledger_line(summary, namespace)
    stored_run_id = summary.get("ledger_run_id")
    if stored_run_id not in (None, line["run_id"]):
        raise HarnessError("qualification summary ledger_run_id differs from its content")
    if stored_run_id is None or not summary_path.exists():
        summary = {**summary, "ledger_run_id": line["run_id"]}
        write_json_atomic(summary_path, summary)
    ensure_ledger_lines([line])
    return summary


def run_with_transport_retry(profile, prompt, schema):
    attempts = []
    for attempt in (1, 2):
        started = time.monotonic()
        try:
            payload, meta = call_tool(profile, prompt, schema)
            attempts.append({"attempt": attempt, "status": "ok", "elapsed_seconds": round(time.monotonic() - started, 3)})
            return payload, meta, attempts
        except FormatError as exc:
            attempts.append({"attempt": attempt, "status": "format_error", "error": str(exc),
                             "elapsed_seconds": round(time.monotonic() - started, 3)})
            exc.evidence = {"attempts": attempts, "provider": exc.evidence}
            raise
        except RequestError as exc:
            attempts.append({"attempt": attempt, "status": "request_error", "error": str(exc),
                             "elapsed_seconds": round(time.monotonic() - started, 3)})
            exc.evidence = {"attempts": attempts, "provider": exc.evidence}
            raise
        except TransportError as exc:
            attempts.append({"attempt": attempt, "status": "transport_error", "error": str(exc),
                             "elapsed_seconds": round(time.monotonic() - started, 3)})
            if attempt == 2:
                exc.evidence = {"attempts": attempts, "provider": exc.evidence}
                raise


def cmd_cold_reader(args):
    profiles = profile_map()
    configured = load_json(DATA_FILES["models.json"])["qualification_profiles"]
    names = args.profiles or configured
    if args.tier == "qualification":
        ensure_qualification_start_gate()
    suite = load_json(DATA_FILES["cold_reader_cases.json"])
    cases = [suite["smoke"]["case"]] if args.tier == "smoke" else suite["qualification"]["cases"]
    reps = 1 if args.tier == "smoke" else suite["qualification"]["repetitions_per_profile"]
    all_pass = True
    for name in names:
        profile = profiles.get(name)
        if not profile or profile.get("role") != "cold_reader":
            raise HarnessError(f"{name} is not a cold-reader profile")
        base_namespace, key = cold_reader_namespace(args.tier, name)
        if args.tier == "smoke":
            namespace = next_smoke_attempt(base_namespace)
        else:
            smoke_base, _ = cold_reader_namespace("smoke", name)
            if passed_smoke_attempt(smoke_base) is None:
                raise HarnessError(f"qualification requires a current passing reader smoke for {name}")
            namespace = base_namespace
        summary_path = namespace / "summary.json"
        marker_path = namespace / "attempt.json"
        if args.tier == "qualification":
            write_json_exclusive(marker_path, {"status": "started", "started_at": utc_now(), "key": key})
        records = []
        for rep in range(1, reps + 1):
            for case in cases:
                record = {"profile": name, "tier": args.tier, "rep": rep, "case_id": case["id"],
                          "started_at": utc_now(), "key": key}
                try:
                    payload, meta, attempts = run_with_transport_retry(
                        profile, case_prompt(case, smoke=args.tier == "smoke"), case_schema(case)
                    )
                    assertions = grade_case(case, payload)
                    record.update({"status": "pass" if all(a["pass"] for a in assertions) else "fail",
                                   "payload": payload, "assertions": assertions,
                                   "model": sanitize_host_metadata(meta),
                                   "attempts": sanitize_host_metadata(attempts)})
                except Exception as exc:
                    record.update({"status": "error", "error_type": type(exc).__name__,
                                   "error": sanitize_host_metadata(str(exc)[:1000]),
                                   "error_evidence": sanitize_host_metadata(getattr(exc, "evidence", None))})
                record_path = namespace / name / f"rep-{rep}" / f"{case['id']}.json"
                if record_path.exists():
                    raise HarnessError(f"refusing to overwrite immutable case record: {record_path}")
                write_json_atomic(record_path, record)
                records.append(record)
                print(f"{name} rep={rep} case={case['id']} {record['status']}", flush=True)
        passed = all(record["status"] == "pass" for record in records)
        summary = {"type": "cold_reader", "tier": args.tier, "profile": name, "key": key,
                   "started_calls": len(records), "passed": passed,
                   "assertions": sum(len(record.get("assertions", [])) for record in records),
                   "failed_assertions": sum(1 for record in records for item in record.get("assertions", []) if not item["pass"]),
                   "errors": sum(record["status"] == "error" for record in records), "completed_at": utc_now()}
        if args.tier == "qualification":
            summary = ensure_qualification_summary_ledger(summary_path, summary, namespace)
        else:
            write_json_atomic(summary_path, summary)
        print(canonical(summary))
        all_pass = all_pass and passed
    if not all_pass:
        raise SystemExit(1)


def cmd_adapter_smoke(args):
    base_namespace, key = adapter_smoke_namespace()
    namespace = next_smoke_attempt(base_namespace)
    profiles = profile_map()
    suite = load_json(DATA_FILES["cold_reader_cases.json"])
    case = suite["smoke"]["case"]
    records = []
    for name in ("fable-subject", "kimi-subject"):
        profile = profiles[name]
        tool_path = namespace / name / "tool.json"

        def tool_call(p=profile):
            payload, meta = call_tool(p, case_prompt(case, smoke=True), case_schema(case))
            assertions = grade_case(case, payload)
            if not all(item["pass"] for item in assertions):
                raise FormatError("adapter smoke tool call failed semantic assertions", {"assertions": assertions})
            return {"payload": payload, "assertions": assertions}, meta

        tool_record = call_record(tool_path, tool_call, {"kind": "adapter_smoke", "profile": name, "path": "tool"})
        records.append(tool_record)
        text_path = namespace / name / "text.json"

        def text_call(p=profile):
            result, meta = call_text(p, "Reply with exactly SMOKE_OK.", "Answer the smoke probe exactly.\n")
            if result.strip() != "SMOKE_OK":
                raise FormatError("adapter text smoke did not return SMOKE_OK", {"result": result})
            return result, meta

        text_record = call_record(text_path, text_call, {"kind": "adapter_smoke", "profile": name, "path": "text"})
        records.append(text_record)
        print(f"{name} tool={tool_record['status']} text={text_record['status']}", flush=True)
    judge_name = load_json(DATA_FILES["models.json"])["judge_profile"]
    judge_profile = profiles[judge_name]
    task_schema = task_judge_schema("SMOKE", 2, 1)
    task_record = call_record(
        namespace / judge_name / "task-schema.json",
        lambda: call_codex_schema(
            judge_profile,
            "Submit task_id SMOKE, required_pass [true,true], and fatal_hits [false].",
            task_schema,
        ),
        {"kind": "adapter_smoke", "profile": judge_name, "path": "task_schema"},
    )
    substitute_schema = substitute_judge_schema(["c1", "c2"])
    def smoke_substitute_call():
        payload, meta = call_codex_schema(
            judge_profile,
            "Submit verdicts for c1 and c2 in that order. Set c1 pattern_id null and c2 pattern_id U01.",
            substitute_schema,
        )
        validate_substitute_payload(payload, ["c1", "c2"])
        return payload, meta

    substitute_record = call_record(
        namespace / judge_name / "substitute-schema.json",
        smoke_substitute_call,
        {"kind": "adapter_smoke", "profile": judge_name, "path": "substitute_schema"},
    )
    records.extend((task_record, substitute_record))
    print(f"{judge_name} task_schema={task_record['status']} substitute_schema={substitute_record['status']}", flush=True)
    passed = all(record["status"] == "ok" for record in records)
    summary = {"type": "adapter_smoke", "key": key, "passed": passed, "calls": len(records),
               "errors": sum(record["status"] != "ok" for record in records), "completed_at": utc_now()}
    write_json_atomic(namespace / "summary.json", summary)
    print(canonical(summary))
    if not passed:
        raise SystemExit(1)


def measured_schedule():
    jobs = [
        {"family": family, "arm": arm, "rep": rep}
        for family in ("fable-subject", "kimi-subject")
        for arm in ("control", "treatment")
        for rep in range(1, REPS + 1)
    ]
    random.Random(SEED).shuffle(jobs)
    return [{"order": index, **job} for index, job in enumerate(jobs, 1)]


def cmd_schedule(args):
    print(json.dumps(measured_schedule(), indent=2))


def freeze_payload():
    return {
        "schema_version": 1,
        "frozen_at": "2026-08-21",
        "files": {str(path.relative_to(ROOT)): sha256(path) for path in FREEZE_INPUTS},
    }


def cmd_freeze(args):
    errors = validate_inputs(check_freeze=False)
    if errors:
        raise HarnessError("cannot freeze invalid inputs: " + "; ".join(errors))
    path = E09 / "freeze.json"
    write_json_exclusive(path, freeze_payload())
    print(f"wrote {path.relative_to(ROOT)}")


def measured_id():
    path = E09 / "freeze.json"
    if not path.exists():
        raise HarnessError("freeze.json is absent; freeze the reviewed design before measured execution")
    frozen = load_json(path)
    return "m-" + digest(frozen["files"], 16)


def git(*args):
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=60)
    if proc.returncode:
        raise HarnessError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def ledger_diff_contains_only(run_ids):
    proc = subprocess.run(["git", "diff", "HEAD", "--unified=0", "--", str(LEDGER.relative_to(ROOT))],
                          cwd=ROOT, text=True, capture_output=True, timeout=60)
    if proc.returncode:
        return False
    added = []
    for line in proc.stdout.splitlines():
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@") or line.startswith("diff ") or line.startswith("index "):
            continue
        if line.startswith("-"):
            return False
        if line.startswith("+"):
            try:
                added.append(json.loads(line[1:])["run_id"])
            except (json.JSONDecodeError, KeyError):
                return False
    return len(added) == len(set(added)) and set(added) <= set(run_ids)


def ensure_ledger_lines(lines):
    existing = {}
    raw_lines = LEDGER.read_text(encoding="utf-8").splitlines() if LEDGER.exists() else []
    for raw in raw_lines:
        if not raw.strip():
            continue
        row = json.loads(raw)
        existing[row["run_id"]] = row
    for line in lines:
        prior = existing.get(line["run_id"])
        if prior is not None:
            if canonical(prior) != canonical(line):
                raise HarnessError(f"ledger run_id collision with different content: {line['run_id']}")
            continue
        append_jsonl(LEDGER, line)
        existing[line["run_id"]] = line


def ensure_qualification_start_gate():
    freeze_path = E09 / "freeze.json"
    if not freeze_path.exists():
        raise HarnessError("qualification requires freeze.json from the reviewed design PR")
    errors = validate_inputs()
    if errors:
        raise HarnessError("qualification freeze validation failed: " + "; ".join(errors))
    head = git("rev-parse", "HEAD")
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", head, "origin/main"], cwd=ROOT)
    if proc.returncode:
        raise HarnessError("qualification requires the frozen commit to be contained in origin/main")
    allowed_prefixes = [str((RAW / "smoke").relative_to(ROOT)) + "/"]
    allowed_run_ids = []
    for name in load_json(DATA_FILES["models.json"])["qualification_profiles"]:
        namespace, _ = cold_reader_namespace("qualification", name)
        if namespace.exists():
            allowed_prefixes.append(str(namespace.relative_to(ROOT)) + "/")
            summary = namespace / "summary.json"
            if summary.exists():
                payload = ensure_qualification_summary_ledger(summary, load_json(summary), namespace)
                allowed_run_ids.append(payload["ledger_run_id"])
    remaining = []
    ledger_path = str(LEDGER.relative_to(ROOT))
    for line in git("status", "--porcelain=v1", "--untracked-files=all").splitlines():
        path = line[3:].strip('"')
        if any(path.startswith(prefix) for prefix in allowed_prefixes):
            continue
        if path == ledger_path and ledger_diff_contains_only(allowed_run_ids):
            continue
        remaining.append(line)
    if remaining:
        raise HarnessError("qualification found unrelated changes: " + " | ".join(remaining))


def ensure_measured_gate():
    if not (E09 / "freeze.json").exists():
        raise HarnessError("freeze.json is required for measured mode")
    errors = validate_inputs()
    if errors:
        raise HarnessError("frozen-input validation failed: " + "; ".join(errors))
    qualification_prefixes = []
    qualification_run_ids = []
    for name in load_json(DATA_FILES["models.json"])["qualification_profiles"]:
        qualification_namespace, _ = cold_reader_namespace("qualification", name)
        summary_path = qualification_namespace / "summary.json"
        if not summary_path.exists() or not load_json(summary_path).get("passed"):
            raise HarnessError(f"current cold-reader qualification has not passed for {name}")
        summary = ensure_qualification_summary_ledger(
            summary_path, load_json(summary_path), qualification_namespace
        )
        qualification_prefixes.append(str(qualification_namespace.relative_to(ROOT)) + "/")
        qualification_run_ids.append(summary["ledger_run_id"])
    adapter_base, _ = adapter_smoke_namespace()
    adapter_namespace = passed_smoke_attempt(adapter_base)
    if adapter_namespace is None:
        raise HarnessError("current measured-adapter smoke has not passed")
    adapter_summary = adapter_namespace / "summary.json"
    if not adapter_summary.exists() or not load_json(adapter_summary).get("passed"):
        raise HarnessError("current measured-adapter smoke has not passed")
    status = git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    namespace = RAW / "measured" / measured_id()
    allowed_prefixes = qualification_prefixes + [
        str((RAW / "smoke").relative_to(ROOT)) + "/",
        str(adapter_namespace.relative_to(ROOT)) + "/",
    ]
    if namespace.exists():
        allowed_prefixes.append(str(namespace.relative_to(ROOT)) + "/")
    allowed_ledger_ids = list(qualification_run_ids)
    results_path = namespace / "results.json"
    if results_path.exists():
        allowed_ledger_ids.extend(line["run_id"] for line in load_json(results_path).get("lines", []))
    remaining = []
    ledger_path = str(LEDGER.relative_to(ROOT))
    for line in status:
        path = line[3:].strip('"')
        if any(path.startswith(prefix) for prefix in allowed_prefixes):
            continue
        if path == ledger_path and ledger_diff_contains_only(allowed_ledger_ids):
            continue
        remaining.append(line)
    status = remaining
    if status:
        raise HarnessError("measured mode found unrelated changes: " + " | ".join(status))
    head = git("rev-parse", "HEAD")
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", head, "origin/main"], cwd=ROOT)
    if proc.returncode:
        raise HarnessError("measured mode requires the frozen commit to be contained in origin/main")
    return head


def count_lexical(text: str) -> int:
    return len(LEXICAL.findall(text))


def coverage_per_100_contract_tokens(rendered_relevant, contract_tokens):
    return (100 * len(rendered_relevant) / contract_tokens) if contract_tokens else 0


def mean_variance(values):
    if not values:
        return None
    return {
        "n": len(values),
        "values": values,
        "mean": statistics.mean(values),
        "sample_variance": statistics.variance(values) if len(values) > 1 else 0,
        "sample_stdev": statistics.stdev(values) if len(values) > 1 else 0,
    }


def measured_record_namespace(path: Path):
    try:
        relative = path.relative_to(RAW / "measured")
    except ValueError:
        return None
    if len(relative.parts) < 2:
        return None
    return RAW / "measured" / relative.parts[0]


def measured_manifest_rows(namespace: Path):
    path = namespace / "record-manifest.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def start_measured_record(path: Path):
    namespace = measured_record_namespace(path)
    if namespace is None:
        return
    relative = str(path.relative_to(namespace))
    if any(row.get("path") == relative for row in measured_manifest_rows(namespace)):
        raise HarnessError(f"measured call path was already started: {relative}")
    payload = {"event": "started", "path": relative, "started_at": utc_now()}
    append_jsonl(namespace / "record-manifest.jsonl", {
        "run_id": "record-start-" + digest({"namespace": namespace.name, **payload}, 20),
        **payload,
    })


def complete_measured_record(path: Path):
    namespace = measured_record_namespace(path)
    if namespace is None:
        return
    relative = str(path.relative_to(namespace))
    payload = {"event": "completed", "path": relative, "sha256": sha256(path)}
    append_jsonl(namespace / "record-manifest.jsonl", {
        "run_id": "record-complete-" + digest({"namespace": namespace.name, **payload}, 20),
        **payload,
    })


def verify_measured_record(path: Path):
    namespace = measured_record_namespace(path)
    if namespace is None:
        return
    relative = str(path.relative_to(namespace))
    rows = [row for row in measured_manifest_rows(namespace) if row.get("path") == relative]
    starts = [row for row in rows if row.get("event") == "started"]
    completions = [row for row in rows if row.get("event") == "completed"]
    if len(starts) != 1 or len(completions) != 1:
        raise HarnessError(f"measured call manifest is incomplete for {relative}")
    if not path.exists() or completions[0].get("sha256") != sha256(path):
        raise HarnessError(f"measured call record differs from its manifest: {relative}")


def verify_measured_manifest(namespace: Path):
    paths = {row.get("path") for row in measured_manifest_rows(namespace)}
    for relative in sorted(path for path in paths if path):
        verify_measured_record(namespace / relative)


def call_record(path, thunk, identity, finalize_record=None):
    if path.exists():
        verify_measured_record(path)
        existing = load_json(path)
        if existing.get("status") == "harness_error":
            raise HarnessError(f"recorded harness fault requires a corrected freeze: {path}")
        return existing
    start_measured_record(path)
    record = {**identity, "started_at": utc_now()}
    attempts = []
    for attempt in (1, 2):
        started = time.monotonic()
        try:
            result, meta = thunk()
            attempts.append({"attempt": attempt, "status": "ok", "elapsed_seconds": round(time.monotonic() - started, 3)})
            record.update({"status": "ok", "result": result, "model": sanitize_host_metadata(meta),
                           "attempts": sanitize_host_metadata(attempts), "completed_at": utc_now()})
            break
        except FormatError as exc:
            attempts.append({"attempt": attempt, "status": "format_error", "error": str(exc),
                             "elapsed_seconds": round(time.monotonic() - started, 3)})
            record.update({"status": "format_error", "error": sanitize_host_metadata(str(exc)),
                           "error_evidence": sanitize_host_metadata(exc.evidence),
                           "attempts": sanitize_host_metadata(attempts), "completed_at": utc_now()})
            break
        except RequestError as exc:
            attempts.append({"attempt": attempt, "status": "request_error", "error": str(exc),
                             "elapsed_seconds": round(time.monotonic() - started, 3)})
            record.update({"status": "request_error", "error": sanitize_host_metadata(str(exc)),
                           "error_evidence": sanitize_host_metadata(exc.evidence),
                           "attempts": sanitize_host_metadata(attempts), "completed_at": utc_now()})
            break
        except TransportError as exc:
            attempts.append({"attempt": attempt, "status": "transport_error", "error": str(exc),
                             "elapsed_seconds": round(time.monotonic() - started, 3)})
            if attempt == 2:
                record.update({"status": "transport_error", "error": sanitize_host_metadata(str(exc)),
                               "attempts": sanitize_host_metadata(attempts), "completed_at": utc_now()})
        except Exception as exc:
            record.update({"status": "harness_error", "error": sanitize_host_metadata(str(exc)),
                           "error_type": type(exc).__name__, "attempts": sanitize_host_metadata(attempts),
                           "completed_at": utc_now()})
            if finalize_record:
                finalize_record(record)
            write_json_atomic(path, record)
            complete_measured_record(path)
            raise
    if finalize_record:
        finalize_record(record)
    write_json_atomic(path, record)
    complete_measured_record(path)
    return record


def cmd_interviews(args):
    head = ensure_measured_gate()
    namespace = RAW / "measured" / measured_id()
    metadata = namespace / "metadata.json"
    if not metadata.exists():
        write_json_atomic(metadata, {"experiment": "E-09", "base_commit": head, "started_at": utc_now(),
                                     "freeze_sha256": sha256(E09 / "freeze.json"), "schedule": measured_schedule()})
    profiles = profile_map()
    for job in measured_schedule():
        path = namespace / "interviews" / job["family"] / job["arm"] / f"rep-{job['rep']}.json"
        profile = profiles[job["family"]]
        schema = contract_schema(job["arm"])
        def enrich_interview(record):
            if record.get("status") == "ok":
                contract = record["result"]["contract"]
                record["contract_lexical_tokens"] = count_lexical(contract)
                record["over_cap"] = record["contract_lexical_tokens"] > 60
                record["contract_violations"] = contract_violations(job["arm"], record["result"])

        record = call_record(
            path,
            lambda p=profile, a=job["arm"], s=schema: call_tool(p, render_interview(a), s),
            {"kind": "interview", **job},
            finalize_record=enrich_interview,
        )
        print(f"{job['order']:02d} {job['family']} {job['arm']} {job['rep']} {record['status']}", flush=True)


def iter_records(directory: Path):
    if not directory.exists():
        return []
    return [load_json(path) for path in sorted(directory.rglob("*.json")) if path.name != "metadata.json"]


def rendered_catalog_ids(interview):
    persona = load_json(DATA_FILES["persona.json"])
    preference_map = {row["preference_id"]: row["resolved_catalog_ids"] for row in persona["catalog_mapping"]}
    evidence_map = {row["evidence_id"]: row["preference_ids"] for row in persona["evidence_mapping"]}
    rendered = set()
    for rule in interview.get("result", {}).get("rules", []):
        rendered.update(rule.get("catalog_ids", []))
        for evidence_id in rule.get("evidence_ids", []):
            for preference_id in evidence_map.get(evidence_id, []):
                rendered.update(preference_map.get(preference_id, []))
    return rendered


def suppression_contract(interview, condition):
    prompts = load_json(DATA_FILES["prompts.json"])["downstream"]
    kept = []
    for rule in interview["result"]["rules"]:
        if condition == "suppression" or not rule.get("catalog_ids"):
            kept.append(rule["text"])
    body = "\n".join(f"- {line.lstrip('- ').strip()}" for line in kept)
    return prompts["system_boilerplate"] + ("\n\n" + body if body else "") + "\n"


def cmd_tasks(args):
    ensure_measured_gate()
    namespace = RAW / "measured" / measured_id()
    interviews = iter_records(namespace / "interviews")
    if len(interviews) != 20:
        raise HarnessError(f"expected 20 started interviews, found {len(interviews)}")
    profiles = profile_map()
    tasks = load_json(DATA_FILES["tasks.json"])["tasks"]
    jobs = [(interview, condition, task) for interview in interviews
            for condition in (("suppression", "no_suppression") if interview["arm"] == "treatment" else ("suppression",))
            for task in tasks]
    random.Random(SEED).shuffle(jobs)
    metadata_path = namespace / "metadata.json"
    metadata = load_json(metadata_path)
    schedule = [{"order": index, "family": interview["family"], "arm": interview["arm"],
                 "rep": interview["rep"], "condition": condition, "task_id": task["id"]}
                for index, (interview, condition, task) in enumerate(jobs, 1)]
    if "task_schedule" in metadata and metadata["task_schedule"] != schedule:
        raise HarnessError("stored task schedule differs from the frozen seed")
    metadata["task_schedule"] = schedule
    write_json_atomic(metadata_path, metadata)
    for order, (interview, condition, task) in enumerate(jobs, 1):
        family, arm, rep = interview["family"], interview["arm"], interview["rep"]
        path = namespace / "tasks" / family / arm / f"rep-{rep}" / condition / f"{task['id']}.json"
        if interview.get("status") != "ok" or interview.get("over_cap") or interview.get("contract_violations"):
            reason = ("interview_error" if interview.get("status") != "ok" else
                      "over_cap" if interview.get("over_cap") else "contract_violation")
            record = {"kind": "task", "family": family, "arm": arm, "rep": rep,
                      "condition": condition, "task_id": task["id"], "status": "excluded", "reason": reason}
            if not path.exists():
                write_json_atomic(path, record)
        else:
            record = call_record(
                path,
                lambda p=profiles[family], q=task["prompt"], s=suppression_contract(interview, condition): call_text(p, q, s),
                {"kind": "task", "family": family, "arm": arm, "rep": rep,
                 "condition": condition, "task_id": task["id"]},
            )
        print(f"{order:03d} {family} {arm} {rep} {condition} {task['id']} {record['status']}", flush=True)


def matcher_hits(text, matcher_family):
    config = load_json(DATA_FILES["substitutes.json"])
    occupied = []
    hits = []
    for uid in config["precedence"]:
        for expression in config[matcher_family][uid]:
            for match in re.finditer(expression, text, re.IGNORECASE):
                span = match.span()
                if any(max(span[0], old[0]) < min(span[1], old[1]) for old in occupied):
                    continue
                occupied.append(span)
                hits.append({"pattern_id": uid, "start": span[0], "end": span[1], "text": match.group(0)})
    return sorted(hits, key=lambda row: row["start"])


def call_codex_schema(profile, prompt, schema):
    binary = os.environ.get(profile.get("binary_env", "E09_CODEX_BIN")) or shutil.which("codex")
    if not binary:
        raise HarnessError("codex is not installed")
    with tempfile.TemporaryDirectory(prefix="e09-codex-") as tmp_name:
        tmp = Path(tmp_name)
        schema_path = tmp / "schema.json"
        output_path = tmp / "result.json"
        write_json_atomic(schema_path, schema)
        cmd = [binary, "exec", "-", "--model", profile["model"], "--ephemeral", "--ignore-user-config",
               "--ignore-rules", "--sandbox", "read-only", "--skip-git-repo-check", "--cd", str(tmp),
               "--output-schema", str(schema_path), "--output-last-message", str(output_path),
               "--json", "-c", f'model_reasoning_effort="{profile["effort"]}"']
        try:
            proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True,
                                  timeout=profile["timeout_seconds"])
        except subprocess.TimeoutExpired as exc:
            raise TransportError("codex timed out") from exc
        if proc.returncode:
            raise TransportError(f"codex exited {proc.returncode}: {proc.stderr[-500:]}")
        try:
            payload = load_json(output_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise FormatError("codex structured output was not valid JSON",
                              {"stdout": proc.stdout, "stderr_tail": proc.stderr[-1000:]}) from exc
        errors = validate_schema(payload, schema)
        if errors:
            raise FormatError("; ".join(errors), {"payload": payload, "stderr_tail": proc.stderr[-1000:]})
        events = []
        for line in proc.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        completed = [event for event in events if event.get("type") == "turn.completed"]
        version = subprocess.run([binary, "--version"], text=True, capture_output=True, timeout=30)
        return payload, {"requested_model": profile["model"], "reported_models": [],
                         "identity_evidence": "requested_model_plus_cli_version; CLI did not echo routed model",
                         "adapter": "codex_cli", "executable": Path(binary).name,
                         "cli_version": version.stdout.strip() or version.stderr.strip(),
                         "usage": completed[-1].get("usage") if completed else None,
                         "events": events, "stderr_tail": proc.stderr[-1000:]}


def cmd_judge(args):
    ensure_measured_gate()
    namespace = RAW / "measured" / measured_id()
    tasks_by_id = {task["id"]: task for task in load_json(DATA_FILES["tasks.json"])["tasks"]}
    profile = profile_map()[load_json(DATA_FILES["models.json"])["judge_profile"]]
    all_task_records = iter_records(namespace / "tasks")
    if len(all_task_records) != 120:
        raise HarnessError(f"judge requires all 120 task records; found {len(all_task_records)}")
    task_records = [record for record in all_task_records if record.get("status") == "ok"]
    random.Random(JUDGE_SEED).shuffle(task_records)
    metadata_path = namespace / "metadata.json"
    metadata = load_json(metadata_path)
    schedule = [{"order": index, "blind_id": digest({"text": row["result"], "task": row["task_id"]}),
                 "task_id": row["task_id"]} for index, row in enumerate(task_records, 1)]
    if "judge_schedule" in metadata and metadata["judge_schedule"] != schedule:
        raise HarnessError("stored judge schedule differs from the frozen seed")
    metadata["judge_schedule"] = schedule
    write_json_atomic(metadata_path, metadata)
    for index, task_record in enumerate(task_records, 1):
        blind_id = digest({"text": task_record["result"], "task": task_record["task_id"]})
        task = tasks_by_id[task_record["task_id"]]
        judge_path = namespace / "judgments" / "task" / f"{blind_id}.json"
        prompt = (load_json(DATA_FILES["prompts.json"])["judge"]["task"] + "\n\nRUBRIC:\n" +
                  canonical(task["rubric"]) + "\n\nCANDIDATE:\n" + task_record["result"])
        record = call_record(
            judge_path,
            lambda p=prompt, s=task_judge_schema(task["id"], len(task["rubric"]["required"]), len(task["rubric"]["fatal"])): call_codex_schema(profile, p, s),
            {"kind": "task_judgment", "blind_id": blind_id, "task_id": task["id"]},
        )
        print(f"task judge {index}/{len(task_records)} {blind_id} {record['status']}", flush=True)

        candidates = matcher_hits(task_record["result"], "substitute")
        if not candidates:
            continue
        candidate_ids = [digest({"blind": blind_id, **item}, 12) for item in candidates]
        frozen = [{"candidate_id": cid, "text": item["text"]}
                  for cid, item in zip(candidate_ids, candidates)]
        prompt = (load_json(DATA_FILES["prompts.json"])["judge"]["substitute"] +
                  "\n\nTAXONOMY:\n" + canonical(load_json(DATA_FILES["substitutes.json"])["substitute"]) +
                  "\n\nCANDIDATES:\n" + canonical(frozen) + "\n\nRESPONSE CONTEXT:\n" + task_record["result"])
        for adjudication_pass in (1, 2):
            path = namespace / "judgments" / "substitute" / blind_id / f"pass-{adjudication_pass}.json"

            def substitute_call(p=prompt, s=substitute_judge_schema(candidate_ids), ids=candidate_ids):
                payload, meta = call_codex_schema(profile, p, s)
                validate_substitute_payload(payload, ids)
                return payload, meta

            record = call_record(
                path,
                substitute_call,
                {"kind": "substitute_judgment", "blind_id": blind_id, "pass": adjudication_pass},
            )
            print(f"substitute judge {blind_id} pass={adjudication_pass} {record['status']}", flush=True)


def stats_by(records, key):
    return mean_variance([record[key] for record in records if key in record and record[key] is not None])


def pooled_rate(records, hits_key, token_key):
    usable = [record for record in records if record.get(token_key) and record.get(hits_key) is not None]
    hits = sum(record[hits_key] for record in usable)
    tokens = sum(record[token_key] for record in usable)
    return {"hits": hits, "tokens": tokens, "rate_per_1000": 1000 * hits / tokens if tokens else None}


def stats_n(stats):
    return stats["n"] if stats else 0


def screen_status(complete, passes, not_testable=False):
    if not complete:
        return "incomplete"
    if not_testable:
        return "not_testable"
    return "pass" if passes else "fail"


def derived_task_success(judgment):
    if not judgment or judgment.get("status") != "ok":
        return False
    result = judgment.get("result", {})
    return bool(result.get("required_pass")) and all(result["required_pass"]) and not any(result.get("fatal_hits", []))


def build_adjudication_pending(expected, disagreement_rows, disagreements):
    return {
        "schema_version": 1,
        "rule": "Resolve each case against the included taxonomy. The sheet contains no arm, family, repetition, or condition metadata.",
        "taxonomy": load_json(DATA_FILES["substitutes.json"])["substitute"],
        "cases": [{
            "blind_id": blind,
            "candidates": expected[blind]["candidates"],
            "response_context": expected[blind]["response_context"],
            "judge_pass_1": disagreement_rows[blind][0]["result"]["verdicts"],
            "judge_pass_2": disagreement_rows[blind][1]["result"]["verdicts"],
        } for blind in sorted(disagreements)],
        "resolutions": [],
    }


def load_substitute_verdicts(namespace: Path, task_records):
    """Return confirmed verdicts by blind task ID or stop for blinded adjudication."""
    records = iter_records(namespace / "judgments" / "substitute")
    by_blind = {}
    for record in records:
        by_blind.setdefault(record["blind_id"], []).append(record)
    expected = {}
    for task_record in task_records:
        if task_record.get("status") != "ok":
            continue
        candidates = matcher_hits(task_record["result"], "substitute")
        if not candidates:
            continue
        blind = digest({"text": task_record["result"], "task": task_record["task_id"]})
        candidate_ids = [digest({"blind": blind, **item}, 12) for item in candidates]
        expected[blind] = {
            "candidate_ids": candidate_ids,
            "candidates": [
                {"candidate_id": candidate_id, "text": item["text"]}
                for candidate_id, item in zip(candidate_ids, candidates)
            ],
            "response_context": task_record["result"],
        }
    disagreements = []
    agreed = {}
    judge_errors = []
    disagreement_rows = {}
    for blind, expected_case in expected.items():
        rows = sorted(by_blind.get(blind, []), key=lambda row: row.get("pass", 0))
        if len(rows) != 2:
            raise HarnessError(f"missing substitute judgment pass for {blind}")
        if not all(row.get("status") == "ok" for row in rows):
            agreed[blind] = None
            judge_errors.append(blind)
        elif canonical(rows[0].get("result")) == canonical(rows[1].get("result")):
            agreed[blind] = rows[0]["result"]["verdicts"]
        else:
            disagreements.append(blind)
            disagreement_rows[blind] = rows
    if not disagreements:
        judged_sets = len(expected) - len(judge_errors)
        return agreed, {"candidate_sets": len(expected), "judged_sets": judged_sets,
                        "agreement": 1.0 if judged_sets else None,
                        "judge_error_blind_ids": sorted(judge_errors), "human_resolutions": 0}

    pending = build_adjudication_pending(expected, disagreement_rows, disagreements)
    pending_path = namespace / "adjudication-pending.json"
    if not pending_path.exists():
        write_json_atomic(pending_path, pending)
    resolved_path = namespace / "adjudication-resolved.json"
    if not resolved_path.exists():
        raise HarnessError(f"substitute-judge disagreements require blinded human adjudication: {len(disagreements)}")
    resolved = load_json(resolved_path)
    rows = {row.get("blind_id"): row.get("verdicts") for row in resolved.get("resolutions", [])}
    if set(rows) != set(disagreements):
        raise HarnessError("human adjudication must resolve every and only pending blind ID")
    for blind in disagreements:
        schema = substitute_judge_schema(expected[blind]["candidate_ids"])
        payload = {"verdicts": rows[blind]}
        errors = validate_schema(payload, schema)
        if errors:
            raise HarnessError(f"invalid human adjudication for {blind}: {'; '.join(errors)}")
        try:
            validate_substitute_payload(payload, expected[blind]["candidate_ids"])
        except FormatError as exc:
            raise HarnessError(f"invalid human adjudication for {blind}: {exc}") from exc
        agreed[blind] = rows[blind]
    judged_sets = len(expected) - len(judge_errors)
    agreement = (judged_sets - len(disagreements)) / judged_sets if judged_sets else None
    return agreed, {"candidate_sets": len(expected), "judged_sets": judged_sets, "agreement": agreement,
                    "judge_error_blind_ids": sorted(judge_errors), "human_resolutions": len(disagreements)}


def cmd_finalize(args):
    ensure_measured_gate()
    namespace = RAW / "measured" / measured_id()
    verify_measured_manifest(namespace)
    results_path = namespace / "results.json"
    if results_path.exists():
        saved = load_json(results_path)
        ensure_ledger_lines(saved["lines"])
        print(json.dumps(saved, indent=2))
        return
    interviews = iter_records(namespace / "interviews")
    tasks = iter_records(namespace / "tasks")
    if len(interviews) != 20 or len(tasks) != 120:
        raise HarnessError("batch is incomplete")
    judgments = {record["blind_id"]: record for record in iter_records(namespace / "judgments" / "task")}
    for task in tasks:
        if task.get("status") != "ok":
            continue
        blind = digest({"text": task["result"], "task": task["task_id"]})
        judgment = judgments.get(blind)
        if not judgment:
            raise HarnessError(f"missing task judgment for {blind}")
    substitute_verdicts, judge_agreement = load_substitute_verdicts(namespace, tasks)
    persona = load_json(DATA_FILES["persona.json"])
    mapping = {row["preference_id"]: row["resolved_catalog_ids"] for row in persona["catalog_mapping"]}
    evidence_mapping = {row["evidence_id"]: row["preference_ids"] for row in persona["evidence_mapping"]}
    task_by_identity = {(r["family"], r["arm"], r["rep"], r["condition"], r["task_id"]): r for r in tasks}
    results = {}
    for family in ("fable-subject", "kimi-subject"):
        results[family] = {}
        for arm in ("control", "treatment"):
            arm_interviews = [r for r in interviews if r["family"] == family and r["arm"] == arm]
            per_run = []
            for interview in sorted(arm_interviews, key=lambda r: r["rep"]):
                selected_via_evidence = set()
                for evidence_id in interview.get("result", {}).get("selected_evidence_ids", []):
                    for preference_id in evidence_mapping.get(evidence_id, []):
                        selected_via_evidence.update(mapping.get(preference_id, []))
                rejected_via_catalog = set(interview.get("result", {}).get("rejected_catalog_ids", []))
                selected_via_catalog = set(interview.get("result", {}).get("selected_catalog_ids", [])) - rejected_via_catalog
                user_selected = selected_via_evidence | selected_via_catalog
                automatic = set(interview.get("result", {}).get("automatic_bans", []))
                all_selected = user_selected | automatic
                relevant = set(persona["relevant_catalog_ids"])
                usable = (interview.get("status") == "ok" and not interview.get("over_cap")
                          and not interview.get("contract_violations"))
                rendered_relevant = rendered_catalog_ids(interview) & relevant if usable else set()
                normalized_tokens = interview.get("contract_lexical_tokens", 0)
                run = {
                    "rep": interview["rep"],
                    "selected_ids": sorted(user_selected),
                    "automatic_bans": sorted(automatic),
                    "selected_relevant": len(user_selected & relevant),
                    "coverage": len(user_selected & relevant) / len(relevant),
                    "selection_precision": len(user_selected & relevant) / len(all_selected) if all_selected else 1.0,
                    "irrelevant_selections": len((user_selected - relevant) | automatic),
                    "contract_tokens": normalized_tokens,
                    "over_cap": interview.get("over_cap", False),
                    "contract_violations": interview.get("contract_violations", []),
                    "interview_status": interview.get("status"),
                    "coverage_per_100_contract_tokens": coverage_per_100_contract_tokens(
                        rendered_relevant, normalized_tokens
                    ),
                    "catalog_rules_removed_in_no_suppression": sum(
                        bool(rule.get("catalog_ids")) for rule in interview.get("result", {}).get("rules", [])
                    ) if arm == "treatment" else 0,
                    "catalog_rule_tokens_removed_in_no_suppression": sum(
                        count_lexical(rule.get("text", ""))
                        for rule in interview.get("result", {}).get("rules", [])
                        if rule.get("catalog_ids")
                    ) if arm == "treatment" else 0,
                    "conditions": {},
                }
                conditions = ("suppression", "no_suppression") if arm == "treatment" else ("suppression",)
                for condition in conditions:
                    task_rows = [task_by_identity.get((family, arm, interview["rep"], condition, tid))
                                 for tid in ("T01", "T02", "T03", "T04")]
                    listed = sum(len(matcher_hits(row.get("result", ""), "listed")) for row in task_rows if row)
                    lexical = sum(count_lexical(row.get("result", "")) for row in task_rows if row)
                    successes = 0
                    task_judge_errors = 0
                    substitutes = 0
                    outside_selected = 0
                    substitute_complete = True
                    buckets = {name: 0 for name in ("unaided_only", "catalog_mapped_only", "both")}
                    for row in task_rows:
                        if not row or row.get("status") != "ok":
                            continue
                        blind = digest({"text": row["result"], "task": row["task_id"]})
                        task_judge_errors += judgments[blind].get("status") != "ok"
                        successes += derived_task_success(judgments[blind])
                        if matcher_hits(row["result"], "substitute") and substitute_verdicts.get(blind) is None:
                            substitute_complete = False
                            continue
                        for verdict in substitute_verdicts.get(blind, []) or []:
                            if verdict["pattern_id"] is not None:
                                uid = verdict["pattern_id"]
                                if uid not in user_selected:
                                    outside_selected += 1
                                    continue
                                substitutes += 1
                                if uid in selected_via_evidence and uid in selected_via_catalog:
                                    buckets["both"] += 1
                                elif uid in selected_via_catalog:
                                    buckets["catalog_mapped_only"] += 1
                                else:
                                    buckets["unaided_only"] += 1
                    run["conditions"][condition] = {
                        "task_successes": successes,
                        "task_failures": 4 - successes,
                        "task_judge_errors": task_judge_errors,
                        "listed_hits": listed,
                        "output_tokens": lexical,
                        "listed_rate_per_1000": 1000 * listed / lexical if lexical else None,
                        "substitute_hits": substitutes if substitute_complete else None,
                        "substitute_rate_per_1000": 1000 * substitutes / lexical if lexical and substitute_complete else None,
                        "substitute_buckets": buckets,
                        "outside_selected_substitute_candidates": outside_selected if substitute_complete else None,
                        "substitute_judgment_complete": substitute_complete,
                    }
                per_run.append(run)
            suppression = [row["conditions"]["suppression"] for row in per_run]
            no_suppression = [row["conditions"]["no_suppression"] for row in per_run] if arm == "treatment" else []
            paired = [{
                "rep": row["rep"],
                "raw_difference": (row["conditions"]["suppression"]["substitute_hits"] - row["conditions"]["no_suppression"]["substitute_hits"])
                if row["conditions"]["suppression"]["substitute_hits"] is not None
                and row["conditions"]["no_suppression"]["substitute_hits"] is not None else None,
                "rate_difference": (row["conditions"]["suppression"]["substitute_rate_per_1000"] - row["conditions"]["no_suppression"]["substitute_rate_per_1000"])
                if row["conditions"]["suppression"]["substitute_rate_per_1000"] is not None
                and row["conditions"]["no_suppression"]["substitute_rate_per_1000"] is not None else None,
            } for row in per_run] if arm == "treatment" else []
            results[family][arm] = {
                "runs": per_run,
                "selected_relevant": stats_by(per_run, "selected_relevant"),
                "coverage": stats_by(per_run, "coverage"),
                "selection_precision": stats_by(per_run, "selection_precision"),
                "irrelevant_selections": stats_by(per_run, "irrelevant_selections"),
                "irrelevant_selection_median": statistics.median(row["irrelevant_selections"] for row in per_run),
                "contract_tokens": stats_by(per_run, "contract_tokens"),
                "coverage_per_100_contract_tokens": stats_by(per_run, "coverage_per_100_contract_tokens"),
                "suppression": {
                    "task_failures": stats_by(suppression, "task_failures"),
                    "listed_hits": stats_by(suppression, "listed_hits"),
                    "listed_rate_per_1000": stats_by(suppression, "listed_rate_per_1000"),
                    "listed_pooled": pooled_rate(suppression, "listed_hits", "output_tokens"),
                    "substitute_hits": stats_by(suppression, "substitute_hits"),
                    "substitute_rate_per_1000": stats_by(suppression, "substitute_rate_per_1000"),
                    "substitute_pooled": pooled_rate(suppression, "substitute_hits", "output_tokens"),
                },
                "no_suppression": {
                    "task_failures": stats_by(no_suppression, "task_failures"),
                    "listed_hits": stats_by(no_suppression, "listed_hits"),
                    "listed_rate_per_1000": stats_by(no_suppression, "listed_rate_per_1000"),
                    "listed_pooled": pooled_rate(no_suppression, "listed_hits", "output_tokens"),
                    "substitute_hits": stats_by(no_suppression, "substitute_hits"),
                    "substitute_rate_per_1000": stats_by(no_suppression, "substitute_rate_per_1000"),
                    "substitute_pooled": pooled_rate(no_suppression, "substitute_hits", "output_tokens"),
                } if no_suppression else None,
                "substitute_paired_raw_difference": stats_by(paired, "raw_difference"),
                "substitute_paired_rate_difference": stats_by(paired, "rate_difference"),
                "over_cap_count": sum(row["over_cap"] for row in per_run),
                "contract_violation_count": sum(bool(row["contract_violations"]) for row in per_run),
                "interview_error_count": sum(row["interview_status"] != "ok" for row in per_run),
            }
    lines = []
    completed_at = utc_now()
    for family, family_results in results.items():
        control = family_results["control"]
        treatment = family_results["treatment"]
        all_interviews_ok = control["interview_error_count"] == 0 and treatment["interview_error_count"] == 0
        c19_gain = treatment["selected_relevant"]["mean"] - control["selected_relevant"]["mean"]
        c19_ceiling_blocked = len(persona["relevant_catalog_ids"]) - control["selected_relevant"]["mean"] < 1
        c20_passes = (
            treatment["coverage_per_100_contract_tokens"]["mean"] >= control["coverage_per_100_contract_tokens"]["mean"]
            and treatment["irrelevant_selection_median"] <= 1
            and treatment["suppression"]["task_failures"]["mean"] - control["suppression"]["task_failures"]["mean"] <= 1
        )
        c20_judgments_complete = all(
            row["conditions"]["suppression"]["task_judge_errors"] == 0
            for row in control["runs"] + treatment["runs"]
        )
        c20_complete = all_interviews_ok and c20_judgments_complete
        paired_raw = treatment["substitute_paired_raw_difference"]
        paired_rate = treatment["substitute_paired_rate_difference"]
        c21_has_contrast = all(
            row["catalog_rules_removed_in_no_suppression"] >= 1 for row in treatment["runs"]
        )
        c21_complete = all_interviews_ok and stats_n(paired_raw) == 5 and stats_n(paired_rate) == 5 and c21_has_contrast
        c21_passes = c21_complete and paired_raw["mean"] > 0 and paired_rate["mean"] > 0
        treatment_listed = treatment["suppression"]["listed_rate_per_1000"]
        control_listed = control["suppression"]["listed_rate_per_1000"]
        c22_complete = all_interviews_ok and stats_n(treatment_listed) == 5 and stats_n(control_listed) == 5
        c22_passes = c22_complete and treatment_listed["mean"] < control_listed["mean"]
        claim_checks = {
            "C19": {
                "status": screen_status(all_interviews_ok, c19_gain >= 1, c19_ceiling_blocked),
                "mean_gain": c19_gain,
                "ceiling_blocks_one_pattern_gain": c19_ceiling_blocked,
                "passes_screen": all_interviews_ok and not c19_ceiling_blocked and c19_gain >= 1,
            },
            "C20": {
                "status": screen_status(c20_complete, c20_passes),
                "all_task_judgments_complete": c20_judgments_complete,
                "density_not_lower": treatment["coverage_per_100_contract_tokens"]["mean"] >= control["coverage_per_100_contract_tokens"]["mean"],
                "irrelevant_median_at_most_one": treatment["irrelevant_selection_median"] <= 1,
                "task_failure_increase_at_most_one": treatment["suppression"]["task_failures"]["mean"] - control["suppression"]["task_failures"]["mean"] <= 1,
            },
            "C21": {
                "status": screen_status(c21_complete, c21_passes),
                "all_five_rates": stats_n(paired_rate) == 5,
                "all_five_pairs_remove_catalog_rules": c21_has_contrast,
                "raw_higher": stats_n(paired_raw) == 5 and paired_raw["mean"] > 0,
                "rate_higher": stats_n(paired_rate) == 5 and paired_rate["mean"] > 0,
            },
            "C22": {
                "status": screen_status(c22_complete, c22_passes),
                "all_five_rates": stats_n(treatment_listed) == 5 and stats_n(control_listed) == 5,
                "treatment_rate_lower": c22_passes,
            },
        }
        payload = {
            "schema_version": 2,
            "type": "experiment",
            "experiment": "E-09",
            "family": family,
            "arms": family_results,
            "claim_checks": claim_checks,
            "judge_agreement": judge_agreement,
            "reps_per_arm": REPS,
            "sample_variance": "n-1",
            "seed": SEED,
            "judge_seed": JUDGE_SEED,
            "raw_dir": str(namespace.relative_to(ROOT)),
            "freeze_sha256": sha256(E09 / "freeze.json"),
            "completed_at": completed_at,
        }
        stable_payload = {key: value for key, value in payload.items() if key != "completed_at"}
        run_id = "r-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + digest(stable_payload, 10)
        lines.append({"run_id": run_id, "date": completed_at, **payload})
    saved = {"lines": lines}
    write_json_exclusive(results_path, saved)
    ensure_ledger_lines(lines)
    print(json.dumps(saved, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    sub.add_parser("freeze").set_defaults(func=cmd_freeze)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--profiles", nargs="+")
    preflight.set_defaults(func=cmd_preflight)
    cold = sub.add_parser("cold-reader")
    cold.add_argument("--tier", choices=("smoke", "qualification"), required=True)
    cold.add_argument("--profiles", nargs="+")
    cold.set_defaults(func=cmd_cold_reader)
    sub.add_parser("adapter-smoke").set_defaults(func=cmd_adapter_smoke)
    render = sub.add_parser("render")
    render.add_argument("--arm", choices=("control", "treatment"), required=True)
    render.set_defaults(func=lambda args: print(render_interview(args.arm), end=""))
    sub.add_parser("schedule").set_defaults(func=cmd_schedule)
    sub.add_parser("interviews").set_defaults(func=cmd_interviews)
    sub.add_parser("tasks").set_defaults(func=cmd_tasks)
    sub.add_parser("judge").set_defaults(func=cmd_judge)
    sub.add_parser("finalize").set_defaults(func=cmd_finalize)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except HarnessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
