"""Semantic risk classification for artifact content.

Complements the hidden-Unicode scan (`content_guard`) by judging *what an artifact
instructs*. Two tiers cover two distinct threats:

- a cheap, always-on local encoder for injection/jailbreak payloads embedded in the
  text (default `protectai/deberta-v3-base-prompt-injection-v2`), and
- an optional judge that evaluates the artifact against the policy's explicit rule
  set (malicious-execution intent), driven through DSPy for structured output.

Everything heavy is imported lazily, so importing this module pulls no ML deps. The
whole subsystem is OFF unless the governing policy's `[risk]` enables it — so by
default this is a no-op. It is advisory-first: blocking requires `mode = "block"`
in the policy (intended only once a model is measured against a labeled corpus).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Protocol

from aim.core import paths, policy

_SEVERITY_TO_LEVEL: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


class RiskBlockedError(ValueError):
    """An artifact's risk verdict meets the policy's block threshold."""


class RiskDependencyError(RuntimeError):
    """A risk backend needs an optional dependency that is not installed."""


class RiskLevel(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @classmethod
    def from_severity(cls, severity: str) -> RiskLevel:
        return cls(_SEVERITY_TO_LEVEL.get(severity, 2))


@dataclass(frozen=True)
class RiskVerdict:
    level: RiskLevel
    reasons: list[str] = field(default_factory=list)
    source: str = ""


@dataclass(frozen=True)
class RiskConfig:
    enabled: bool
    mode: str  # warn | block
    backend: str  # null | local | judge | tiered
    model_id: str
    block_threshold: RiskLevel
    escalate_threshold: RiskLevel
    judge: str | None
    allow_override: bool
    rules: list[policy.RiskRule]


def config_from_policy(pol: policy.Policy) -> RiskConfig:
    r = pol.risk
    return RiskConfig(
        enabled=r.enabled,
        mode=r.mode,
        backend=r.backend,
        model_id=r.model_id,
        block_threshold=RiskLevel.from_severity(r.block_threshold),
        escalate_threshold=RiskLevel.from_severity(r.escalate_threshold),
        judge=r.judge,
        allow_override=r.allow_override,
        rules=policy.active_rules(pol),
    )


# ---------- classifier protocol + backends (all heavy imports are lazy) ----------


class RiskClassifier(Protocol):
    def classify(self, text: str, *, source: str | None = None) -> RiskVerdict: ...


class NullClassifier:
    def classify(self, text: str, *, source: str | None = None) -> RiskVerdict:
        return RiskVerdict(RiskLevel.LOW, [], "null")


def risk_model_dir() -> Path:
    """Cache location for local risk models — under platformdirs' user cache, so
    aim never downloads into the cwd or a stray HF default."""
    return paths.user_cache_dir() / "risk-model"


def _injection_label_index(config_path: Path) -> int:
    """Which output index means 'injection/unsafe', read from the model config.
    Defaults to 1 (ProtectAI convention: 0=SAFE, 1=INJECTION)."""
    try:
        id2label = json.loads(config_path.read_text(encoding="utf-8")).get("id2label", {})
    except (OSError, json.JSONDecodeError):
        return 1
    for idx, label in id2label.items():
        if any(k in str(label).lower() for k in ("inject", "unsafe", "jailbreak", "malicious")):
            return int(idx)
    return 1


def _injection_score_to_level(score: float) -> RiskLevel:
    if score >= 0.9:
        return RiskLevel.HIGH
    if score >= 0.5:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


@functools.lru_cache(maxsize=4)
def _load_onnx_model(model_id: str) -> tuple[Any, Any, int, tuple[str, ...]]:
    """Download (to platformdirs) and load an ONNX text-classification model once.
    Returns (session, tokenizer, injection_index, input_names). Cached per model_id."""
    try:
        import onnxruntime as ort
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise RiskDependencyError(
            "local risk model needs the 'risk' extra: pip install 'agent-init[risk]'"
        ) from exc
    local_dir = Path(
        snapshot_download(
            model_id,
            cache_dir=str(risk_model_dir()),
            # Pull only what inference needs — never the torch/tf weights.
            allow_patterns=["*.onnx", "*.json", "tokenizer*", "spm.model", "*.txt"],
        )
    )
    onnx_files = sorted(local_dir.rglob("*.onnx"))
    if not onnx_files:
        raise RiskDependencyError(f"no .onnx file found in {model_id}")
    # Prefer the full-precision model.onnx over quantized variants for accuracy.
    model_path = next((p for p in onnx_files if p.name == "model.onnx"), onnx_files[0])
    tok_path = local_dir / "tokenizer.json"
    if not tok_path.exists():
        raise RiskDependencyError(
            f"{model_id} has no tokenizer.json (a fast tokenizer is required)"
        )
    tokenizer = Tokenizer.from_file(str(tok_path))
    tokenizer.enable_truncation(max_length=512)
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_names = tuple(i.name for i in session.get_inputs())
    return session, tokenizer, _injection_label_index(local_dir / "config.json"), input_names


@dataclass
class LocalOnnxClassifier:
    """Cheap injection/jailbreak screen backed by a local ONNX text-classification
    model (default deberta-v3-base-prompt-injection-v2). On-device, no egress.
    Raises RiskDependencyError if the `risk` extra is not installed."""

    model_id: str

    def classify(self, text: str, *, source: str | None = None) -> RiskVerdict:
        import numpy as np

        session, tokenizer, injection_index, input_names = _load_onnx_model(self.model_id)
        enc = tokenizer.encode(text)
        ids = list(enc.ids)
        feed: dict[str, Any] = {}
        if "input_ids" in input_names:
            feed["input_ids"] = np.array([ids], dtype=np.int64)
        if "attention_mask" in input_names:
            feed["attention_mask"] = np.array([list(enc.attention_mask)], dtype=np.int64)
        if "token_type_ids" in input_names:
            feed["token_type_ids"] = np.zeros((1, len(ids)), dtype=np.int64)
        logits = np.asarray(session.run(None, feed)[0])[0]
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()
        score = float(probs[injection_index])
        return RiskVerdict(
            _injection_score_to_level(score),
            [f"prompt-injection/jailbreak likelihood {score:.2f}"],
            "local:onnx",
        )


def _parse_findings(raw: str) -> list[dict]:
    """Tolerantly parse the judge's findings JSON (strip code fences / surrounding prose)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1 :] if "\n" in text else text
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [f for f in data if isinstance(f, dict)] if isinstance(data, list) else []


def _judge_verdict(findings: list[dict], rules: list[policy.RiskRule]) -> RiskVerdict:
    """Fold per-rule findings into one verdict: level = max severity among violated
    rules; reasons name the rule that fired and its evidence."""
    severity_by_id = {r.id: r.severity for r in rules}
    violated = [f for f in findings if f.get("violated") in (True, "true", "True", 1)]
    if not violated:
        return RiskVerdict(RiskLevel.LOW, [], "judge")
    level = max(
        (
            RiskLevel.from_severity(severity_by_id.get(str(f.get("rule_id")), "high"))
            for f in violated
        ),
        default=RiskLevel.LOW,
    )
    reasons = [f"{f.get('rule_id')}: {f.get('evidence', '')}".strip().rstrip(":") for f in violated]
    return RiskVerdict(level, reasons, "judge")


@dataclass
class JudgeClassifier:
    """Evaluates the artifact against the policy's explicit rule set via DSPy,
    returning per-rule findings. Lazily loads DSPy; raises RiskDependencyError if
    the `risk-judge` extra is not installed.

    aim only needs DSPy here — DSPy accesses the configured language model on its
    own via the model string in `[risk].judge` (e.g. "ollama_chat/llama3" or
    "openai/gpt-4o"). How that model is hosted and authenticated (local server,
    remote endpoint, env credentials) is the user's concern, not aim's."""

    config: RiskConfig
    lm: Any = None  # pre-built DSPy LM; tests/advanced users inject one here

    def classify(self, text: str, *, source: str | None = None) -> RiskVerdict:
        try:
            import dspy
        except ImportError as exc:
            raise RiskDependencyError(
                "risk judge needs the 'risk-judge' extra: pip install 'agent-init[risk-judge]'"
            ) from exc
        lm = self.lm if self.lm is not None else dspy.settings.lm
        if lm is None:
            if not self.config.judge:
                raise RiskDependencyError(
                    "no judge model configured; set [risk].judge in the policy"
                )
            lm = dspy.LM(self.config.judge)
        rules = self.config.rules
        if not rules:
            return RiskVerdict(RiskLevel.LOW, [], "judge")

        class _RuleJudge(dspy.Signature):
            """Assess an AI agent artifact (skill/rule/subagent instructions) against
            each risk rule. Judge execution-time intent — data exfiltration, destructive
            operations, remote code execution, privilege escalation, obfuscation — not
            mere mention. Mark `violated` true only with concrete evidence in the text."""

            artifact: str = dspy.InputField(desc="the artifact text to assess")
            rules: str = dspy.InputField(desc="JSON list of rules [{id, severity, guidance}]")
            findings: str = dspy.OutputField(
                desc='JSON list [{"rule_id": str, "violated": bool, "evidence": str}]'
            )

        payload = json.dumps(
            [{"id": r.id, "severity": r.severity, "guidance": r.prompt} for r in rules]
        )
        with dspy.context(lm=lm):
            out = dspy.Predict(_RuleJudge)(artifact=text, rules=payload)
        return _judge_verdict(_parse_findings(out.findings), rules)


@dataclass
class TieredClassifier:
    local: RiskClassifier | None
    judge: RiskClassifier | None
    escalate_threshold: RiskLevel

    def classify(self, text: str, *, source: str | None = None) -> RiskVerdict:
        base = (
            self.local.classify(text, source=source)
            if self.local is not None
            else RiskVerdict(RiskLevel.LOW, [], "none")
        )
        if self.judge is None or base.level < self.escalate_threshold:
            return base
        judged = self.judge.classify(text, source=source)
        if judged.level >= base.level:
            return RiskVerdict(judged.level, [*base.reasons, *judged.reasons], "tiered")
        return RiskVerdict(base.level, [*base.reasons, *judged.reasons], "tiered")


_override: RiskClassifier | None = None


def set_classifier(classifier: RiskClassifier | None) -> None:
    """Override the active classifier (tests inject a fake here)."""
    global _override
    _override = classifier


def reset_classifier() -> None:
    global _override
    _override = None


def get_classifier(config: RiskConfig) -> RiskClassifier:
    if _override is not None:
        return _override
    if not config.enabled or config.backend == "null":
        return NullClassifier()
    local = LocalOnnxClassifier(config.model_id) if config.backend in ("local", "tiered") else None
    judge = (
        JudgeClassifier(config)
        if (config.backend in ("judge", "tiered") and config.judge)
        else None
    )
    if config.backend == "local":
        return local or NullClassifier()
    if config.backend == "judge":
        return judge or NullClassifier()
    return TieredClassifier(local, judge, config.escalate_threshold)


# ---------- verdict store: per-artifact history (last 3), keyed by content hash ----------

_HISTORY = 3


def _verdict_store_path(qualified_name: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", qualified_name)
    return paths.user_cache_dir() / "risk-verdicts" / f"{safe}.json"


def _load_history(qualified_name: str) -> list[dict]:
    path = _verdict_store_path(qualified_name)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def config_fingerprint(config: RiskConfig) -> str:
    """Identity of the classifier configuration: a cached verdict is only valid for
    the same fingerprint, so changing the rules/backend/judge/thresholds correctly
    invalidates stale verdicts instead of reusing a level computed under old rules."""
    payload = json.dumps(
        {
            "backend": config.backend,
            "model_id": config.model_id,
            "judge": config.judge,
            "escalate": int(config.escalate_threshold),
            "rules": sorted((r.id, r.severity, r.prompt) for r in config.rules),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def verdict_cache_get(
    qualified_name: str, content_hash: str, fingerprint: str
) -> RiskVerdict | None:
    for entry in _load_history(qualified_name):
        if entry.get("content_hash") == content_hash and entry.get("fingerprint") == fingerprint:
            return RiskVerdict(RiskLevel(entry["level"]), list(entry.get("reasons", [])), "cache")
    return None


_store_lock = threading.Lock()


def verdict_cache_put(
    qualified_name: str, content_hash: str, fingerprint: str, verdict: RiskVerdict
) -> None:
    path = _verdict_store_path(qualified_name)
    key = (content_hash, fingerprint)
    with _store_lock:  # sync fans gates out across threads; serialize the RMW + write
        history = [
            e
            for e in _load_history(qualified_name)
            if (e.get("content_hash"), e.get("fingerprint")) != key
        ]
        history.append(
            {
                "content_hash": content_hash,
                "fingerprint": fingerprint,
                "level": int(verdict.level),
                "reasons": verdict.reasons,
                "source": verdict.source,
            }
        )
        history = history[-_HISTORY:]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(history), encoding="utf-8")
        os.replace(tmp, path)  # atomic publish (intra-process lock only)


# ---------- advisory warnings buffer (drained by the CLI/TUI) ----------

_risk_warnings: list[str] = []
_warnings_lock = threading.Lock()


def _warn(message: str) -> None:
    with _warnings_lock:
        _risk_warnings.append(message)


def take_risk_warnings() -> list[str]:
    with _warnings_lock:
        out = list(_risk_warnings)
        _risk_warnings.clear()
    return out


# ---------- enforcement entry ----------


def assert_acceptable_risk(
    text: str, *, source: str, config: RiskConfig, allow_risky: bool = False
) -> RiskVerdict:
    """Classify `text` and enforce the policy's risk mode.

    Returns a LOW verdict immediately when risk is disabled (the default). Caches
    verdicts by content hash so re-scans are deterministic and cheap. Raises
    RiskBlockedError only when the policy sets `mode = "block"` and the verdict
    meets the block threshold (unless `allow_risky`). Sub-block findings are pushed
    to the advisory warnings buffer; the reasons are always populated.
    """
    if not config.enabled:
        return RiskVerdict(RiskLevel.LOW, [], "disabled")

    # The override is honored only when the policy permits it (allow_override).
    override = allow_risky and config.allow_override

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    fingerprint = config_fingerprint(config)
    verdict = verdict_cache_get(source, content_hash, fingerprint)
    if verdict is None:
        try:
            verdict = get_classifier(config).classify(text, source=source)
        except RiskDependencyError as exc:
            # In block mode the policy demands enforcement, so an unavailable
            # classifier must fail CLOSED — otherwise block mode is silently vacuous.
            if config.mode == "block" and not override:
                raise RiskBlockedError(
                    f"{source}: policy requires risk blocking but the classifier is "
                    f"unavailable ({exc}); install the risk extra or pass --allow-risky"
                ) from exc
            _warn(f"{source}: risk scan skipped ({exc})")
            return RiskVerdict(RiskLevel.LOW, [], "unavailable")
        verdict_cache_put(source, content_hash, fingerprint, verdict)

    if verdict.level >= config.block_threshold:
        detail = "; ".join(verdict.reasons) or "no detail"
        if config.mode == "block" and not override:
            hint = "" if config.allow_override else " (override disabled by policy)"
            raise RiskBlockedError(
                f"{source}: risk {verdict.level.name} >= {config.block_threshold.name}: {detail}"
                f"{hint or ' (pass --allow-risky to override)'}"
            )
        _warn(f"{source}: risk {verdict.level.name}: {detail}")
    elif verdict.level >= RiskLevel.MEDIUM:
        _warn(f"{source}: risk {verdict.level.name}: {'; '.join(verdict.reasons) or 'no detail'}")
    return verdict


def gate(
    content: str, *, qualified_name: str, pol: policy.Policy, allow_risky: bool = False
) -> None:
    """Convenience wrapper for the deploy chokepoints: classify+enforce using the
    governing policy's risk settings. No-op when risk is disabled."""
    assert_acceptable_risk(
        content,
        source=qualified_name,
        config=config_from_policy(pol),
        allow_risky=allow_risky,
    )
