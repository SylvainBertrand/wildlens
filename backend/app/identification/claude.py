"""Claude CLI vision provider (opt-in).

Uses a local `claude` CLI (Claude Code subscription) to identify the most
prominent landmark, animal, and plant in a photo — no separate API key needed.

Runs ONLY at ingest time (never in the request path), so it never affects the
idle server's footprint. Fails soft: if the CLI is missing, errors, or returns
unparseable output, it yields no subjects and ingest continues.

Select with: WILDLENS_ID_PROVIDER=claude  (override binary via WILDLENS_CLAUDE_BIN)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from ..models import Identification, IdentifiedSubject

_PROMPT = (
    "Look at the image file at {path}. Identify up to one landmark/scene, one "
    "animal, and one plant that are clearly visible. Respond with ONLY a JSON "
    'object, no prose: {{"subjects": [{{"kind": "landmark|fauna|flora", '
    '"label": "common name", "confidence": 0.0-1.0}}]}}. Omit anything not '
    "clearly present. If nothing is identifiable, return {{\"subjects\": []}}."
)

_VALID_KINDS = {"landmark", "fauna", "flora", "scene"}


class ClaudeCLIProvider:
    name = "claude"

    def __init__(self) -> None:
        self.bin = os.environ.get("WILDLENS_CLAUDE_BIN", "claude")
        self.timeout = float(os.environ.get("WILDLENS_CLAUDE_TIMEOUT", "120"))

    def _run(self, image_path: str) -> str | None:
        if not shutil.which(self.bin):
            return None
        prompt = _PROMPT.format(path=image_path)
        try:
            proc = subprocess.run(
                [self.bin, "-p", prompt, "--output-format", "json"],
                capture_output=True, text=True, timeout=self.timeout,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout

    @staticmethod
    def _extract_subjects(raw: str) -> list[IdentifiedSubject]:
        # The CLI may wrap the answer (e.g. {"result": "...json..."}); search the
        # whole payload for the first object containing a "subjects" array.
        candidates: list[str] = [raw]
        try:
            outer = json.loads(raw)
            if isinstance(outer, dict) and isinstance(outer.get("result"), str):
                candidates.append(outer["result"])
        except (json.JSONDecodeError, TypeError):
            pass

        for text in candidates:
            for match in re.finditer(r"\{.*?\"subjects\".*?\}", text, re.DOTALL):
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue
                subs = data.get("subjects")
                if not isinstance(subs, list):
                    continue
                out: list[IdentifiedSubject] = []
                for s in subs:
                    if not isinstance(s, dict):
                        continue
                    label = str(s.get("label", "")).strip()
                    kind = str(s.get("kind", "unknown")).strip().lower()
                    if not label:
                        continue
                    if kind not in _VALID_KINDS:
                        kind = "unknown"
                    try:
                        conf = float(s.get("confidence", 0.5))
                    except (TypeError, ValueError):
                        conf = 0.5
                    out.append(IdentifiedSubject(
                        kind=kind, label=label,
                        confidence=max(0.0, min(1.0, conf)), source="claude"))
                if out:
                    return out
        return []

    def identify(self, image_path: str, context: dict | None = None) -> Identification:
        raw = self._run(image_path)
        subjects = self._extract_subjects(raw) if raw else []
        return Identification(provider=self.name, subjects=subjects)
