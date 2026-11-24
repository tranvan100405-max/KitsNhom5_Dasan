#!/usr/bin/env python3
"""validate_output.py — Backend validator cho đầu ra của AI Log Classifier (Task 3, slide 13).

Mục đích: nhận **một file JSON là đầu ra của LLM** (không phải file input của thiết bị), kiểm tra
theo 2 tầng rồi in ra kết luận HỢP LỆ / KHÔNG HỢP LỆ kèm lý do:

    Tầng 1 — JSON Schema (nhúng trong file này, trùng với schema trong
              docs/member-d/AI_LOG_CLASSIFIER_DESIGN.md):
              kiểu dữ liệu, trường bắt buộc, additionalProperties=false, enum, biên số, pattern...
    Tầng 2 — Kiểm tra ngữ nghĩa (chỉ chạy khi có `--input`):
              mọi errorCode / deviceRef trong output phải thuộc input; deviceCount không vượt
              số task có thật; campaignId/waveId/analysisId phải khớp; không rò serial thật/email...

Chỉ dùng thư viện chuẩn (không cần `jsonschema`, không gọi mạng, không gọi API AI).

Cách dùng:
    python validate_output.py out.json
    python validate_output.py out.json --input docs/member-d/ai-samples/01_isp_wide_download.json
    python validate_output.py out.json --input in.json --min-confidence 0.6 --strict-confidence
    python validate_output.py --self-test          # 3 test mẫu (1 đúng, 2 sai) — test của validator
    python validate_output.py --print-schema       # in JSON Schema để backend/UI dùng chung

Mã thoát:
    0 = HỢP LỆ (có thể kèm cảnh báo)
    1 = KHÔNG HỢP LỆ
    2 = lỗi sử dụng (không đọc được file, JSON hỏng, thiếu tham số)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------------------
# 1. JSON SCHEMA ĐẦU RA (bản chuẩn — trùng với mục C của AI_LOG_CLASSIFIER_DESIGN.md)
# --------------------------------------------------------------------------------------

SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://dasan.local/schemas/error-classification.v1.json",
    "title": "AIErrorLogClassification",
    "description": "Goi y phan loai nhom log loi firmware cho OPERATOR. Chi la goi y, khong thuc thi.",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "analysisId",
        "campaignId",
        "waveId",
        "summary",
        "groups",
        "unclassified",
        "inputAnomalies",
        "limitations",
    ],
    "properties": {
        "schemaVersion": {"type": "integer", "const": 1},
        "analysisId": {"type": "string", "pattern": r"^anl-[A-Za-z0-9-]{4,40}$"},
        "campaignId": {"type": "string", "pattern": r"^[A-Za-z0-9._:-]{3,64}$"},
        "waveId": {"type": "string", "pattern": r"^[A-Za-z0-9._:-]{3,64}$"},
        "summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["headline", "severity", "needsHumanAttention"],
            "properties": {
                "headline": {"type": "string", "minLength": 10, "maxLength": 200},
                "severity": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                },
                "needsHumanAttention": {"type": "boolean"},
            },
        },
        "groups": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "groupId",
                    "rootCauseGroup",
                    "confidence",
                    "errorCodes",
                    "statuses",
                    "model",
                    "fromVersion",
                    "toVersion",
                    "deviceCount",
                    "deviceRefs",
                    "evidence",
                    "reasoning",
                    "suggestedAction",
                ],
                "properties": {
                    "groupId": {"type": "string", "pattern": r"^G[1-9][0-9]?$"},
                    "rootCauseGroup": {
                        "type": "string",
                        "enum": [
                            "DOWNLOAD_TRANSPORT",
                            "CHECKSUM_INTEGRITY",
                            "INSTALL_FLASH",
                            "BOOT_VERIFY",
                            "COMPATIBILITY",
                            "TIMEOUT_NO_HEARTBEAT",
                            "WAVE_DEADLINE",
                            "UNKNOWN",
                        ],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "errorCodes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 6,
                        "uniqueItems": True,
                        "items": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]{2,63}$"},
                    },
                    "statuses": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "enum": ["FAILED", "TIMEOUT", "ROLLED_BACK"],
                        },
                    },
                    "model": {"type": "string", "pattern": r"^[A-Za-z0-9._-]{3,64}$"},
                    "fromVersion": {
                        "type": "string",
                        "pattern": r"^v?[0-9]+\.[0-9]+\.[0-9]+$",
                    },
                    "toVersion": {
                        "type": "string",
                        "pattern": r"^v?[0-9]+\.[0-9]+\.[0-9]+$",
                    },
                    "deviceCount": {"type": "integer", "minimum": 1, "maximum": 100000},
                    "deviceRefs": {
                        "type": "array",
                        "maxItems": 20,
                        "uniqueItems": True,
                        "items": {"type": "string", "pattern": r"^SN-[0-9]{4,6}$"},
                    },
                    "evidence": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {
                            "type": "string",
                            "minLength": 8,
                            "maxLength": 200,
                            "pattern": r"^(campaign|firmware|stats|errorGroups|request)\b.{3,180}$",
                        },
                    },
                    "reasoning": {"type": "string", "minLength": 20, "maxLength": 600},
                    "suggestedAction": {
                        "type": "string",
                        "enum": [
                            "investigate",
                            "collect_more_evidence",
                            "retry_later",
                            "recommend_review_firmware",
                            "escalate_to_network_team",
                            "no_action_required",
                        ],
                    },
                    "suggestedActionNote": {"type": "string", "maxLength": 200},
                },
            },
        },
        "unclassified": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["errorCode", "taskCount", "reason"],
                "properties": {
                    "errorCode": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_?]{1,63}$"},
                    "taskCount": {"type": "integer", "minimum": 0, "maximum": 100000},
                    "reason": {"type": "string", "minLength": 5, "maxLength": 300},
                },
            },
        },
        "inputAnomalies": {
            "type": "array",
            "maxItems": 6,
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": [
                    "MISSING_FIELDS",
                    "EMPTY_ERROR_GROUPS",
                    "SUSPICIOUS_INSTRUCTION_TEXT",
                    "INCONSISTENT_COUNTS",
                    "UNKNOWN_ERROR_CODES",
                    "TRUNCATED_REFS",
                ],
            },
        },
        "limitations": {
            "type": "array",
            "maxItems": 5,
            "items": {"type": "string", "minLength": 10, "maxLength": 200},
        },
    },
}

# --------------------------------------------------------------------------------------
# 2. Hằng số chính sách (dùng cho kiểm tra ngữ nghĩa)
# --------------------------------------------------------------------------------------

DEFAULT_MIN_CONFIDENCE = 0.5
UNKNOWN_GROUP_MAX_CONFIDENCE = 0.4
PII_PATTERNS = [
    (r"\bDSN-[A-Za-z0-9]", "serial thiết bị thật dạng DSN-... (phải ẩn danh thành SN-####)"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "địa chỉ email (PII)"),
]
INJECTION_ECHO = re.compile(
    r"ignore\s+(all\s+)?previous\s+instructions"
    r"|bỏ qua\s+(mọi\s+|các\s+)?chỉ dẫn"
    r"|recommend(ing)?\s+abort",
    re.IGNORECASE,
)


class Issue:
    """Một lỗi (ERROR) hoặc cảnh báo (WARNING) do validator phát hiện."""

    __slots__ = ("level", "code", "path", "message")

    def __init__(self, level: str, code: str, path: str, message: str) -> None:
        self.level = level
        self.code = code
        self.path = path
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "code": self.code, "path": self.path, "message": self.message}

    def __str__(self) -> str:
        label = "LỖI" if self.level == "ERROR" else "CẢNH BÁO"
        return f"[{label}] {self.code} tại {self.path}: {self.message}"


# --------------------------------------------------------------------------------------
# 3. Bộ kiểm tra JSON Schema tối giản (chỉ các keyword schema ở trên dùng)
# --------------------------------------------------------------------------------------


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_schema(instance: Any, schema: dict[str, Any], path: str = "$") -> list[Issue]:
    issues: list[Issue] = []

    if "const" in schema and instance != schema["const"]:
        issues.append(Issue("ERROR", "SCHEMA_CONST", path,
                            f"phải bằng {schema['const']!r}, nhận {instance!r}"))
    if "enum" in schema and instance not in schema["enum"]:
        issues.append(Issue("ERROR", "SCHEMA_ENUM", path,
                            f"giá trị {instance!r} không thuộc enum cho phép {schema['enum']}"))

    expected_type = schema.get("type")
    if expected_type is not None and not _type_ok(instance, expected_type):
        issues.append(Issue("ERROR", "SCHEMA_TYPE", path,
                            f"phải là {expected_type}, nhận {type(instance).__name__}"))
        return issues  # không kiểm tra tiếp khi sai kiểu

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in instance:
                issues.append(Issue("ERROR", "SCHEMA_REQUIRED", path,
                                    f"thiếu trường bắt buộc '{required}'"))
        if schema.get("additionalProperties") is False:
            for extra in sorted(set(instance) - set(properties)):
                issues.append(Issue("ERROR", "SCHEMA_ADDITIONAL_PROPERTY", path,
                                    f"trường '{extra}' không được phép (additionalProperties=false)"))
        for key, value in instance.items():
            if key in properties:
                issues.extend(validate_schema(value, properties[key], f"{path}.{key}"))

    elif isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            issues.append(Issue("ERROR", "SCHEMA_MIN_ITEMS", path,
                                f"cần ít nhất {schema['minItems']} phần tử, có {len(instance)}"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(Issue("ERROR", "SCHEMA_MAX_ITEMS", path,
                                f"tối đa {schema['maxItems']} phần tử, có {len(instance)}"))
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for item in instance:
                key = _json_key(item)
                if key in seen:
                    issues.append(Issue("ERROR", "SCHEMA_UNIQUE_ITEMS", path,
                                        f"phần tử trùng lặp: {item!r}"))
                    break
                seen.add(key)
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for index, item in enumerate(instance):
                issues.extend(validate_schema(item, items_schema, f"{path}[{index}]"))

    elif isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            issues.append(Issue("ERROR", "SCHEMA_MIN_LENGTH", path,
                                f"cần ≥ {schema['minLength']} ký tự, có {len(instance)}"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            issues.append(Issue("ERROR", "SCHEMA_MAX_LENGTH", path,
                                f"tối đa {schema['maxLength']} ký tự, có {len(instance)}"))
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, instance) is None:
            issues.append(Issue("ERROR", "SCHEMA_PATTERN", path,
                                f"'{instance}' không khớp mẫu {pattern}"))

    elif isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            issues.append(Issue("ERROR", "SCHEMA_MINIMUM", path,
                                f"phải ≥ {schema['minimum']}, nhận {instance}"))
        if "maximum" in schema and instance > schema["maximum"]:
            issues.append(Issue("ERROR", "SCHEMA_MAXIMUM", path,
                                f"phải ≤ {schema['maximum']}, nhận {instance}"))

    return issues


# --------------------------------------------------------------------------------------
# 4. Kiểm tra ngữ nghĩa: đối chiếu output với input đã gửi cho AI
# --------------------------------------------------------------------------------------


def _norm_version(value: Any) -> str:
    return str(value).lstrip("vV").strip() if isinstance(value, str) else ""


def _walk_strings(node: Any, path: str = "$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk_strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk_strings(value, f"{path}[{index}]")
    elif isinstance(node, str):
        yield path, node


def _collect_input_facts(input_doc: dict[str, Any]) -> dict[str, Any]:
    request = input_doc.get("request") or {}
    campaign = input_doc.get("campaign") or {}
    firmware = input_doc.get("firmware") or {}
    stats = input_doc.get("stats") or {}
    error_groups = input_doc.get("errorGroups") or []

    codes: dict[str, int] = {}
    refs: set[str] = set()
    from_versions: set[str] = set()
    for group in error_groups:
        if not isinstance(group, dict):
            continue
        code = group.get("errorCode")
        count = group.get("taskCount")
        if isinstance(code, str):
            codes[code] = codes.get(code, 0) + (count if isinstance(count, int) else 0)
        for ref in group.get("deviceRefs") or []:
            if isinstance(ref, str):
                refs.add(ref)
        if isinstance(group.get("fromVersion"), str):
            from_versions.add(_norm_version(group["fromVersion"]))

    return {
        "analysisId": request.get("analysisId"),
        "campaignId": campaign.get("campaignId"),
        "waveId": campaign.get("waveId"),
        "model": firmware.get("targetModel"),
        "toVersion": _norm_version(firmware.get("toVersion")),
        "fromVersions": from_versions,
        "errorCodes": codes,
        "deviceRefs": refs,
        "tasksTerminal": stats.get("tasksTerminal"),
        "failureRatePercent": stats.get("failureRatePercent"),
        "failureThresholdPercent": campaign.get("failureThresholdPercent"),
    }


def check_semantics(
    output: dict[str, Any],
    input_doc: dict[str, Any] | None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    strict_confidence: bool = False,
) -> list[Issue]:
    issues: list[Issue] = []
    groups = output.get("groups") or []

    # 4.1. Chính sách áp dụng được cả khi không có input
    for index, group in enumerate(groups):
        path = f"$.groups[{index}]"
        confidence = group.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < min_confidence:
            issues.append(Issue(
                "ERROR" if strict_confidence else "WARNING",
                "SEM_LOW_CONFIDENCE",
                f"{path}.confidence",
                f"confidence {confidence} < ngưỡng {min_confidence}; UI không nên tô đậm gợi ý này",
            ))
        if group.get("rootCauseGroup") == "UNKNOWN" and isinstance(confidence, (int, float)):
            if confidence > UNKNOWN_GROUP_MAX_CONFIDENCE:
                issues.append(Issue(
                    "ERROR" if strict_confidence else "WARNING",
                    "SEM_UNKNOWN_TOO_CONFIDENT",
                    f"{path}.confidence",
                    f"nhóm UNKNOWN không được confidence > {UNKNOWN_GROUP_MAX_CONFIDENCE}",
                ))
        dev_count = group.get("deviceCount")
        refs = group.get("deviceRefs") or []
        if isinstance(dev_count, int) and len(refs) > dev_count:
            issues.append(Issue("ERROR", "SEM_REFS_EXCEED_COUNT", f"{path}.deviceRefs",
                                f"{len(refs)} deviceRef > deviceCount {dev_count}"))

    # 4.2. Không rò PII / serial thật trong bất kỳ chuỗi nào của output
    for path, text in _walk_strings(output):
        for pattern, label in PII_PATTERNS:
            if re.search(pattern, text):
                issues.append(Issue("ERROR", "SEM_PII_LEAK", path,
                                    f"chứa {label}: '{text[:80]}'"))
        if INJECTION_ECHO.search(text):
            issues.append(Issue("WARNING", "SEM_INJECTION_ECHO", path,
                                "có dấu hiệu lặp lại chỉ dẫn nằm trong log (prompt injection)"))

    # 4.3. Đối chiếu với input (bắt buộc nếu backend muốn chặn bịa mã lỗi / thiết bị)
    if input_doc is None:
        return issues

    facts = _collect_input_facts(input_doc)
    for key, path in (("analysisId", "$.analysisId"),
                      ("campaignId", "$.campaignId"),
                      ("waveId", "$.waveId")):
        expected = facts.get(key)
        actual = output.get(key)
        if expected is not None and actual != expected:
            issues.append(Issue("ERROR", "SEM_ID_MISMATCH", path,
                                f"phải là '{expected}' (echo từ input), nhận '{actual}'"))

    total_group_devices = 0
    all_refs: list[str] = []
    for index, group in enumerate(groups):
        path = f"$.groups[{index}]"
        total_group_devices += group.get("deviceCount") or 0
        all_refs.extend(group.get("deviceRefs") or [])

        available = 0
        for code in group.get("errorCodes") or []:
            if code not in facts["errorCodes"]:
                issues.append(Issue("ERROR", "SEM_UNKNOWN_ERROR_CODE", f"{path}.errorCodes",
                                    f"mã '{code}' không có trong input"))
            else:
                available += facts["errorCodes"][code]
        for ref in group.get("deviceRefs") or []:
            if ref not in facts["deviceRefs"]:
                issues.append(Issue("ERROR", "SEM_UNKNOWN_DEVICE_REF", f"{path}.deviceRefs",
                                    f"'{ref}' không thuộc input"))

        device_count = group.get("deviceCount") or 0
        if available and device_count > available:
            issues.append(Issue("ERROR", "SEM_COUNT_EXCEEDS_INPUT", f"{path}.deviceCount",
                                f"deviceCount {device_count} > tổng taskCount có thật trong input ({available})"))

        if facts["model"] and group.get("model") != facts["model"]:
            issues.append(Issue("ERROR", "SEM_MODEL_MISMATCH", f"{path}.model",
                                f"model phải là '{facts['model']}', nhận '{group.get('model')}'"))
        if facts["toVersion"] and _norm_version(group.get("toVersion")) != facts["toVersion"]:
            issues.append(Issue("ERROR", "SEM_VERSION_MISMATCH", f"{path}.toVersion",
                                f"toVersion phải là '{facts['toVersion']}'"))
        from_version = _norm_version(group.get("fromVersion"))
        if facts["fromVersions"] and from_version not in facts["fromVersions"]:
            issues.append(Issue("WARNING", "SEM_UNKNOWN_FROM_VERSION", f"{path}.fromVersion",
                                f"fromVersion '{group.get('fromVersion')}' không có trong input"))

    if len(all_refs) != len(set(all_refs)):
        issues.append(Issue("WARNING", "SEM_DUPLICATE_REFS", "$.groups",
                            "một deviceRef xuất hiện ở nhiều nhóm — có thể đếm trùng"))
    tasks_terminal = facts["tasksTerminal"]
    if isinstance(tasks_terminal, int) and total_group_devices > tasks_terminal:
        issues.append(Issue("ERROR", "SEM_SUM_EXCEEDS_TERMINAL", "$.groups",
                            f"tổng deviceCount {total_group_devices} > tasksTerminal {tasks_terminal}"))

    failure_rate = facts["failureRatePercent"]
    threshold = facts["failureThresholdPercent"]
    severity = (output.get("summary") or {}).get("severity")
    if isinstance(failure_rate, (int, float)) and isinstance(threshold, (int, float)):
        if failure_rate > threshold and severity == "LOW":
            issues.append(Issue("WARNING", "SEM_SEVERITY_UNDERSTATED", "$.summary.severity",
                                f"failureRate {failure_rate}% > ngưỡng {threshold}% nhưng severity=LOW"))

    input_codes = set(facts["errorCodes"])
    for index, item in enumerate(output.get("unclassified") or []):
        code = item.get("errorCode")
        if code not in input_codes:
            issues.append(Issue("WARNING", "SEM_UNCLASSIFIED_UNKNOWN_CODE",
                                f"$.unclassified[{index}].errorCode",
                                f"mã '{code}' không có trong input"))
    return issues


# --------------------------------------------------------------------------------------
# 5. API chính
# --------------------------------------------------------------------------------------


def validate_document(
    output: Any,
    input_doc: dict[str, Any] | None = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    strict_confidence: bool = False,
) -> dict[str, Any]:
    """Trả về dict kết luận; dùng được trực tiếp trong backend (không cần CLI)."""
    schema_issues = validate_schema(output, SCHEMA)
    semantic_issues: list[Issue] = []
    if isinstance(output, dict):
        semantic_issues = check_semantics(output, input_doc, min_confidence, strict_confidence)
    else:
        semantic_issues = [Issue("ERROR", "SEM_NOT_OBJECT", "$", "output phải là JSON object")]

    all_issues = schema_issues + semantic_issues
    errors = [issue for issue in all_issues if issue.level == "ERROR"]
    warnings = [issue for issue in all_issues if issue.level == "WARNING"]
    return {
        "valid": not errors,
        "errors": [issue.as_dict() for issue in errors],
        "warnings": [issue.as_dict() for issue in warnings],
        "checkedAgainstInput": input_doc is not None,
    }


def _read_json(path: str) -> Any:
    # utf-8-sig: chấp nhận cả file có BOM (Windows/PowerShell hay ghi BOM) để không từ chối oan.
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _print_report(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("=" * 78)
    print("KẾT LUẬN:", "HỢP LỆ" if result["valid"] else "KHÔNG HỢP LỆ")
    print("Đối chiếu input:", "CÓ" if result["checkedAgainstInput"] else "KHÔNG (chỉ kiểm schema)")
    print(f"Lỗi: {len(result['errors'])} · Cảnh báo: {len(result['warnings'])}")
    for item in result["errors"]:
        print(f"  [LỖI]       {item['code']} tại {item['path']}: {item['message']}")
    for item in result["warnings"]:
        print(f"  [CẢNH BÁO] {item['code']} tại {item['path']}: {item['message']}")
    if result["valid"] and result["warnings"]:
        print("→ Chấp nhận được nhưng PHẢI hiển thị kèm cảnh báo cho OPERATOR.")
    if not result["valid"]:
        print("→ Backend ẩn khung gợi ý AI, ghi audit AI_OUTPUT_REJECTED; Auto-pause cơ học vẫn chạy.")
    print("=" * 78)


# --------------------------------------------------------------------------------------
# 6. 3 TEST MẪU CỦA VALIDATOR (KHÔNG phải output của AI)
#    Đây là fixture do người viết tự tạo để kiểm tra validator; không dùng làm ví dụ output
#    trên slide và không ghi vào prompt-log như kết quả của model.
# --------------------------------------------------------------------------------------


def _fixture_input() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "request": {
            "analysisId": "anl-20261124-9001",
            "trigger": "CAMPAIGN_PAUSED",
            "requestedAt": "2026-11-24T02:15:00Z",
            "windowStart": "2026-11-24T00:00:00Z",
            "windowEnd": "2026-11-24T02:10:00Z",
            "locale": "vi-VN",
        },
        "campaign": {
            "campaignId": "cmp-2026-1118-h660gm-w2",
            "name": "H660GM 2.4.1 - Wave 2",
            "status": "PAUSED",
            "failureThresholdPercent": 5.0,
            "waveId": "wv-02",
            "waveOrder": 2,
            "rolloutPercentage": 10.0,
            "waveStatus": "PAUSED",
        },
        "firmware": {
            "targetModel": "DASAN-H660GM",
            "toVersion": "2.4.1",
            "fromVersion": "2.3.0",
            "versionCode": 20401,
            "minRequiredVersion": "2.3.0",
        },
        "stats": {
            "tasksTerminal": 100,
            "success": 80,
            "failedFinal": 12,
            "timeoutFinal": 5,
            "rolledBack": 3,
            "failureRatePercent": 20.0,
            "stillActive": 4,
        },
        "errorGroups": [
            {
                "errorCode": "ERR_DOWNLOAD_INTERRUPTED",
                "status": "FAILED",
                "model": "DASAN-H660GM",
                "fromVersion": "2.3.0",
                "toVersion": "2.4.1",
                "taskCount": 12,
                "deviceRefs": ["SN-0001", "SN-0002"],
                "attemptCountMin": 3,
                "attemptCountMax": 3,
            },
            {
                "errorCode": "ERR_WATCHDOG_BOOT_TIMEOUT",
                "status": "ROLLED_BACK",
                "model": "DASAN-H660GM",
                "fromVersion": "2.3.0",
                "toVersion": "2.4.1",
                "taskCount": 3,
                "deviceRefs": ["SN-0101"],
                "attemptCountMin": 1,
                "attemptCountMax": 1,
            },
        ],
    }


def _fixture_valid_output() -> dict[str, Any]:
    """Test 1 — đầu ra đúng: schema đúng + mọi mã/ref có thật trong input."""
    return {
        "schemaVersion": 1,
        "analysisId": "anl-20261124-9001",
        "campaignId": "cmp-2026-1118-h660gm-w2",
        "waveId": "wv-02",
        "summary": {
            "headline": "Hai nhóm lỗi: tải bị ngắt diện rộng và bootloop rải rác trên H660GM",
            "severity": "HIGH",
            "needsHumanAttention": True,
        },
        "groups": [
            {
                "groupId": "G1",
                "rootCauseGroup": "DOWNLOAD_TRANSPORT",
                "confidence": 0.72,
                "errorCodes": ["ERR_DOWNLOAD_INTERRUPTED"],
                "statuses": ["FAILED"],
                "model": "DASAN-H660GM",
                "fromVersion": "2.3.0",
                "toVersion": "2.4.1",
                "deviceCount": 12,
                "deviceRefs": ["SN-0001", "SN-0002"],
                "evidence": ["errorGroups[ERR_DOWNLOAD_INTERRUPTED].taskCount=12",
                             "errorGroups[ERR_DOWNLOAD_INTERRUPTED].attemptCountMax=3"],
                "reasoning": "Toàn bộ 12 task lỗi ở bước tải và đã dùng hết 3 lượt; không có lỗi checksum.",
                "suggestedAction": "escalate_to_network_team",
            },
            {
                "groupId": "G2",
                "rootCauseGroup": "BOOT_VERIFY",
                "confidence": 0.66,
                "errorCodes": ["ERR_WATCHDOG_BOOT_TIMEOUT"],
                "statuses": ["ROLLED_BACK"],
                "model": "DASAN-H660GM",
                "fromVersion": "2.3.0",
                "toVersion": "2.4.1",
                "deviceCount": 3,
                "deviceRefs": ["SN-0101"],
                "evidence": ["errorGroups[ERR_WATCHDOG_BOOT_TIMEOUT].status=ROLLED_BACK"],
                "reasoning": "3 thiết bị quay về bank A sau 3 lần boot lỗi; lỗi nằm ở bước xác minh.",
                "suggestedAction": "recommend_review_firmware",
            },
        ],
        "unclassified": [],
        "inputAnomalies": [],
        "limitations": ["Không có log chi tiết của từng thiết bị trong input"],
    }


def _fixture_invalid_schema() -> dict[str, Any]:
    """Test 2 — sai schema: confidence ngoài 0..1, enum lạ, thêm trường tự chế."""
    doc = _fixture_valid_output()
    doc["groups"][0]["confidence"] = 1.4
    doc["groups"][0]["rootCauseGroup"] = "AUTO_ABORT"
    doc["groups"][0]["deviceRefs"] = ["SN-0001", "SN-0001"]
    doc["autoAbortCampaign"] = True
    return doc


def _fixture_invalid_semantics() -> dict[str, Any]:
    """Test 3 — đúng schema nhưng bịa: mã lỗi/ref không có trong input, model sai."""
    doc = _fixture_valid_output()
    doc["groups"][0]["errorCodes"] = ["ERR_FLASH_WRITE_CORRUPTED"]
    doc["groups"][0]["deviceRefs"] = ["SN-9999"]
    doc["groups"][0]["deviceCount"] = 500
    doc["groups"][0]["model"] = "DASAN-H660GM-V2"
    doc["groups"][0]["confidence"] = 0.2
    return doc


def run_self_test() -> int:
    print("TỰ KIỂM TRA VALIDATOR — 3 fixture do người viết tạo, KHÔNG phải output của AI\n")
    input_doc = _fixture_input()
    cases = [
        ("Test 1 — đầu ra ĐÚNG", _fixture_valid_output(), True),
        ("Test 2 — SAI SCHEMA (confidence 1.4, enum lạ, trùng ref, thừa trường)", _fixture_invalid_schema(), False),
        ("Test 3 — SAI NGỮ NGHĨA (bịa mã lỗi/ref/model, vượt số task)", _fixture_invalid_semantics(), False),
    ]
    failed = 0
    for name, doc, expected_valid in cases:
        result = validate_document(doc, input_doc)
        ok = result["valid"] is expected_valid
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'} · {name}")
        print(f"       kỳ vọng valid={expected_valid}, nhận valid={result['valid']} "
              f"({len(result['errors'])} lỗi, {len(result['warnings'])} cảnh báo)")
        for issue in result["errors"]:
            print(f"         - {issue['code']}: {issue['message']}")
        for issue in result["warnings"]:
            print(f"         ~ {issue['code']}: {issue['message']}")
        print()
    print("KẾT QUẢ:", "TẤT CẢ PASS" if failed == 0 else f"{failed} TEST FAIL")
    return 0 if failed == 0 else 1


# --------------------------------------------------------------------------------------
# 7. CLI
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Validate đầu ra JSON của AI Log Classifier (schema + ngữ nghĩa).",
    )
    parser.add_argument("file", nargs="?", help="file JSON là output của AI")
    parser.add_argument("--input", help="file JSON input đã gửi cho AI (để đối chiếu)")
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE,
                        help=f"ngưỡng confidence tối thiểu (mặc định {DEFAULT_MIN_CONFIDENCE})")
    parser.add_argument("--strict-confidence", action="store_true",
                        help="confidence dưới ngưỡng là LỖI thay vì cảnh báo")
    parser.add_argument("--json", action="store_true", help="in kết luận dạng JSON cho backend")
    parser.add_argument("--self-test", action="store_true", help="chạy 3 test mẫu của validator")
    parser.add_argument("--print-schema", action="store_true", help="in JSON Schema rồi thoát")
    args = parser.parse_args(argv)

    if args.print_schema:
        print(json.dumps(SCHEMA, ensure_ascii=False, indent=2))
        return 0
    if args.self_test:
        return run_self_test()
    if not args.file:
        parser.error("cần đường dẫn file JSON output (hoặc dùng --self-test / --print-schema)")

    try:
        output = _read_json(args.file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"KHÔNG ĐỌC ĐƯỢC OUTPUT: {exc}", file=sys.stderr)
        return 2
    input_doc = None
    if args.input:
        try:
            input_doc = _read_json(args.input)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"KHÔNG ĐỌC ĐƯỢC INPUT: {exc}", file=sys.stderr)
            return 2

    result = validate_document(output, input_doc, args.min_confidence, args.strict_confidence)
    _print_report(result, args.json)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
