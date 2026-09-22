"""Small atomic-write primitives for generated backend artifacts."""

from collections.abc import Mapping
import gzip
import json
from pathlib import Path
from typing import Any


class ArtifactWriteError(RuntimeError):
    """Raised when generated artifact content cannot be validated or committed."""


def validated_json_text(payload: Mapping[str, Any]) -> str:
    """Serialize a finite JSON object and verify it decodes before disk mutation."""

    try:
        encoded = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
        decoded = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ArtifactWriteError("Artifact payload is not valid finite JSON") from exc
    if not isinstance(decoded, dict):
        raise ArtifactWriteError("Artifact payload must be a JSON object")
    return encoded


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Validate and atomically replace one JSON artifact."""

    destination = Path(path)
    encoded = validated_json_text(payload)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(encoded, encoding="utf-8")
        with temporary.open("r", encoding="utf-8") as source:
            decoded = json.load(source)
        if not isinstance(decoded, dict):
            raise ArtifactWriteError("Written artifact must decode to a JSON object")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json_gzip(path: Path, payload: Mapping[str, Any]) -> None:
    """Validate and atomically replace one deterministically encoded gzip JSON artifact."""

    destination = Path(path)
    encoded = validated_json_text(payload).encode("utf-8")
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with temporary.open("wb") as raw_output:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_output,
                mtime=0,
            ) as compressed_output:
                compressed_output.write(encoded)
        with gzip.open(temporary, "rt", encoding="utf-8") as source:
            decoded = json.load(source)
        if not isinstance(decoded, dict):
            raise ArtifactWriteError("Written artifact must decode to a JSON object")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
