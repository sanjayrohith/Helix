"""Deterministic, offline intent parser.

The LLM parser gives HELIX its natural-language range, but it needs an API key,
costs a network round trip and can occasionally return something unusable. This
module implements the same contract with pure pattern matching so the system
stays usable during demos, in CI, and whenever the LLM is unavailable.

The parser is intentionally explainable: every field it derives is recorded in
``ParseTrace`` so the UI can show *why* a slice ended up with a given 5QI.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.telecom import (
    DEFAULT_PROFILE,
    SST_NAMES,
    USE_CASE_PROFILES,
    UseCaseProfile,
)

# --- Unit-aware quantity extraction -----------------------------------------

_BITRATE_UNITS = {
    "kbps": 1e-3,
    "kb/s": 1e-3,
    "mbps": 1.0,
    "mb/s": 1.0,
    "mbit": 1.0,
    "gbps": 1000.0,
    "gb/s": 1000.0,
    "gbit": 1000.0,
    "tbps": 1_000_000.0,
}

_LATENCY_UNITS = {
    "ms": 1.0,
    "millisecond": 1.0,
    "milliseconds": 1.0,
    "us": 0.001,
    "microsecond": 0.001,
    "microseconds": 0.001,
    "s": 1000.0,
    "sec": 1000.0,
    "second": 1000.0,
    "seconds": 1000.0,
}

_MULTIPLIERS = {"k": 1_000, "m": 1_000_000, "thousand": 1_000, "million": 1_000_000}

_NUMBER = r"(\d+(?:[.,]\d+)?)"

_BITRATE_RE = re.compile(
    rf"{_NUMBER}\s*(kbps|kb/s|mbps|mb/s|mbit|gbps|gb/s|gbit|tbps)\b", re.IGNORECASE
)
_LATENCY_RE = re.compile(
    rf"{_NUMBER}\s*(ms|milliseconds?|us|microseconds?|seconds?|sec|s)\b(?!\w)", re.IGNORECASE
)
_DEVICE_RE = re.compile(
    rf"{_NUMBER}\s*(k|m|thousand|million)?\s*"
    r"(devices?|sensors?|users?|endpoints?|terminals?|meters?|cameras?|nodes?|ues?|"
    r"subscribers?|vehicles?|cars?|robots?|drones?|handsets?|clients?)",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(?:in|at|for|across|near|around|covering)\s+"
    r"((?:the\s+)?[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,2})"
)

# Bare numbers with a scale suffix, e.g. "50k IoT" where the noun follows later.
_SCALED_NUMBER_RE = re.compile(rf"{_NUMBER}\s*(k|m)\b", re.IGNORECASE)

_LOW_LATENCY_HINTS = (
    "ultra low latency", "ultra-low latency", "real time", "real-time",
    "sub-millisecond", "instant", "immediate", "deterministic",
)

_SECURITY_HINTS = {
    "critical": (
        "life critical", "life-critical", "mission critical", "mission-critical",
        "hipaa", "regulated", "classified", "confidential patient", "highest security",
    ),
    "high": (
        "secure", "security", "encrypted", "encryption", "isolated tenant",
        "private", "compliance", "gdpr", "pci",
    ),
}

_ISOLATION_HINTS = {
    "strict": ("strict isolation", "fully isolated", "physically isolated", "air gapped", "air-gapped"),
    "dedicated": ("dedicated", "reserved", "exclusive", "guaranteed resources", "private slice"),
    "shared": ("shared", "best effort", "best-effort", "cost optimised", "cost optimized"),
}


@dataclass
class ParseTrace:
    """Explains how each field of a configuration was derived."""

    matched_profile: str = ""
    profile_score: int = 0
    matched_keywords: list[str] = field(default_factory=list)
    derived: dict[str, str] = field(default_factory=dict)

    def note(self, field_name: str, reason: str) -> None:
        self.derived[field_name] = reason

    def as_dict(self) -> dict:
        return {
            "matched_profile": self.matched_profile,
            "profile_score": self.profile_score,
            "matched_keywords": self.matched_keywords,
            "derived": self.derived,
        }


def _to_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def extract_bitrate_mbps(text: str) -> float | None:
    """Return the largest explicit bitrate mentioned, normalised to Mbps."""
    values = [
        _to_number(match.group(1)) * _BITRATE_UNITS[match.group(2).lower()]
        for match in _BITRATE_RE.finditer(text)
    ]
    return max(values) if values else None


def extract_latency_ms(text: str) -> float | None:
    """Return the tightest explicit latency requirement, normalised to ms."""
    values = [
        _to_number(match.group(1)) * _LATENCY_UNITS[match.group(2).lower()]
        for match in _LATENCY_RE.finditer(text)
    ]
    values = [value for value in values if value > 0]
    return min(values) if values else None


def extract_device_count(text: str) -> int | None:
    """Return the device population referenced in the intent."""
    match = _DEVICE_RE.search(text)
    if match:
        count = _to_number(match.group(1))
        suffix = (match.group(2) or "").lower()
        return int(count * _MULTIPLIERS.get(suffix, 1))

    scaled = _SCALED_NUMBER_RE.search(text)
    if scaled:
        return int(_to_number(scaled.group(1)) * _MULTIPLIERS[scaled.group(2).lower()])
    return None


def extract_location(text: str) -> str | None:
    """Pull a plausible place name out of the intent."""
    for match in _LOCATION_RE.finditer(text):
        candidate = match.group(1).strip()
        # Skip prepositional phrases that captured a capitalised common noun.
        if candidate.lower().startswith("the "):
            candidate = candidate[4:]
        if len(candidate) > 2:
            return candidate
    return None


def _score_profile(text: str, profile: UseCaseProfile) -> tuple[int, list[str]]:
    hits = [keyword for keyword in profile.keywords if keyword in text]
    # Longer keyword matches are more specific, so weight them.
    score = sum(2 if " " in keyword else 1 for keyword in hits)
    return score, hits


def select_profile(text: str) -> tuple[UseCaseProfile, int, list[str]]:
    """Pick the best matching use-case profile for a lowercased intent."""
    best = (DEFAULT_PROFILE, 0, [])
    for profile in USE_CASE_PROFILES:
        score, hits = _score_profile(text, profile)
        if score > best[1]:
            best = (profile, score, hits)
    return best


class RuleBasedIntentParser:
    """Pattern-matching parser that never leaves the process."""

    name = "rule-based"

    def __init__(self) -> None:
        self._sd_counter = 0x000100

    def parse(self, intent: str) -> tuple[dict, ParseTrace]:
        """Turn an intent string into a slice-config dict plus its derivation trace."""
        text = intent.lower().strip()
        trace = ParseTrace()

        profile, score, hits = select_profile(text)
        trace.matched_profile = profile.key
        trace.profile_score = score
        trace.matched_keywords = hits
        trace.note(
            "use_case",
            f"matched profile '{profile.label}' on {len(hits)} keyword(s)"
            if hits
            else "no keyword matched; fell back to the enterprise broadband profile",
        )

        config: dict = {
            "name": self._build_name(intent, profile),
            "sst": profile.sst,
            "sd": self._next_sd(),
            "qos_5qi": profile.qos_5qi,
            "arp_priority": profile.arp_priority,
            "guaranteed_bitrate_mbps": profile.guaranteed_bitrate_mbps,
            "max_bitrate_mbps": profile.max_bitrate_mbps,
            "latency_ms": profile.latency_ms,
            "security_level": profile.security_level,
            "isolation": profile.isolation,
            "device_count": profile.device_count,
            "use_case": profile.key,
            "location": "Unspecified",
        }
        trace.note("sst", f"{SST_NAMES[profile.sst]} implied by the '{profile.key}' profile")

        self._apply_bitrate(intent, config, trace)
        self._apply_latency(intent, text, config, trace)
        self._apply_devices(intent, config, trace)
        self._apply_location(intent, config, trace)
        self._apply_security(text, config, trace)
        self._apply_isolation(text, config, trace)

        config["slice_id"] = str(uuid.uuid4())
        config["status"] = "pending"
        config["created_at"] = datetime.now(UTC)
        return config, trace

    # --- field extraction helpers -------------------------------------------

    def _apply_bitrate(self, intent: str, config: dict, trace: ParseTrace) -> None:
        bitrate = extract_bitrate_mbps(intent)
        if bitrate is None:
            trace.note(
                "guaranteed_bitrate_mbps",
                f"profile default ({config['guaranteed_bitrate_mbps']} Mbps)",
            )
            return
        config["guaranteed_bitrate_mbps"] = round(bitrate, 2)
        config["max_bitrate_mbps"] = round(max(bitrate * 2.0, bitrate), 2)
        trace.note("guaranteed_bitrate_mbps", f"explicit bitrate of {bitrate:g} Mbps in the intent")
        trace.note("max_bitrate_mbps", "set to 2x the guaranteed rate to allow bursting")

    def _apply_latency(self, intent: str, text: str, config: dict, trace: ParseTrace) -> None:
        latency = extract_latency_ms(intent)
        if latency is not None:
            config["latency_ms"] = max(1, int(round(latency)))
            trace.note("latency_ms", f"explicit latency budget of {latency:g} ms")
            return
        if any(hint in text for hint in _LOW_LATENCY_HINTS):
            config["latency_ms"] = min(config["latency_ms"], 5)
            trace.note("latency_ms", "tightened to 5 ms by an ultra-low-latency phrase")
            return
        trace.note("latency_ms", f"profile default ({config['latency_ms']} ms)")

    def _apply_devices(self, intent: str, config: dict, trace: ParseTrace) -> None:
        devices = extract_device_count(intent)
        if devices is None:
            trace.note("device_count", f"profile default ({config['device_count']:,})")
            return
        config["device_count"] = max(1, devices)
        trace.note("device_count", f"explicit population of {devices:,} devices")

    def _apply_location(self, intent: str, config: dict, trace: ParseTrace) -> None:
        location = extract_location(intent)
        if location is None:
            trace.note("location", "no location mentioned in the intent")
            return
        config["location"] = location
        trace.note("location", f"place name '{location}' found after a locative preposition")

    def _apply_security(self, text: str, config: dict, trace: ParseTrace) -> None:
        for level in ("critical", "high"):
            if any(hint in text for hint in _SECURITY_HINTS[level]):
                config["security_level"] = level
                trace.note("security_level", f"raised to '{level}' by a security phrase")
                return
        trace.note("security_level", f"profile default ('{config['security_level']}')")

    def _apply_isolation(self, text: str, config: dict, trace: ParseTrace) -> None:
        for level in ("strict", "dedicated", "shared"):
            if any(hint in text for hint in _ISOLATION_HINTS[level]):
                config["isolation"] = level
                trace.note("isolation", f"set to '{level}' by an isolation phrase")
                return
        trace.note("isolation", f"profile default ('{config['isolation']}')")

    # --- naming and identifiers ----------------------------------------------

    def _build_name(self, intent: str, profile: UseCaseProfile) -> str:
        """Derive a readable slice name from the intent, falling back to the profile."""
        cleaned = re.sub(r"[^A-Za-z0-9 \-]", " ", intent).strip()
        words = [word for word in cleaned.split() if len(word) > 2][:6]
        if not words:
            return profile.label
        title = " ".join(word.capitalize() if word.islower() else word for word in words)
        return f"{title[:48].strip()} ({SST_NAMES[profile.sst]})"

    def _next_sd(self) -> str:
        """Allocate the next Slice Differentiator in 3GPP hex notation."""
        self._sd_counter = (self._sd_counter + 1) & 0xFFFFFF
        return f"0x{self._sd_counter:06x}"


rule_based_parser = RuleBasedIntentParser()
