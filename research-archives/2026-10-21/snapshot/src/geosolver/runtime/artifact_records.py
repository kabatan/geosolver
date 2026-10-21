"""v4 wire normalization with lossless v3-shaped in-memory/read compatibility.

Content addresses also distinguish revisions whose coordinates or evidence
differ. Reuse never substitutes the latest candidate for the one that justified
a descriptor. Public diagnostics retain their existing expanded shape.
"""

import hashlib
import json

REFERENCE = "$solver_record"


def normalize_artifact(payload):
    tables = {"candidates": {}, "verifications": {}, "descriptors": {}}

    def visit(value):
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        table = None
        if "x_hp" in value or "x_float" in value:
            table = "candidates"
        elif "verified" in value and "normalized_residual" in value:
            table = "verifications"
        elif value.get("kind") in ("algebraic", "affine_pi"):
            table = "descriptors"
        result = {key: visit(item) for key, item in value.items()}
        if table is None:
            return result
        # Acceptance belongs to this reference, not the underlying revision.
        overlay = {key: result.pop(key) for key in ("accepted",) if key in result}
        encoded = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        key = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        tables[table].setdefault(key, result)
        return {REFERENCE: [table, key], **overlay}

    result = visit(payload)
    result["record_tables"] = tables
    return result


def expand_artifact(payload):
    """Read v3 unchanged; resolve and validate v4 references without cycles."""
    if not isinstance(payload, dict) or "record_tables" not in payload:
        return payload
    if payload.get("protocol_version") != 4:
        raise ValueError("record tables require artifact protocol v4")
    tables = payload["record_tables"]
    visiting = set()

    def visit(value):
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        if REFERENCE in value:
            table, key = value[REFERENCE]
            identity = table, key
            if identity in visiting:
                raise ValueError("cyclic artifact record reference")
            try:
                body = tables[table][key]
            except (KeyError, TypeError) as error:
                raise ValueError("missing artifact record reference") from error
            visiting.add(identity)
            result = visit(body)
            visiting.remove(identity)
            result.update({k: visit(v) for k, v in value.items() if k != REFERENCE})
            return result
        return {key: visit(item) for key, item in value.items()}

    return visit({key: value for key, value in payload.items() if key != "record_tables"})
