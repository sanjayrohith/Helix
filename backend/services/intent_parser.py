"""Intent parsing facade.

HELIX has two parsers with the same contract: a Groq-backed LLM parser with
broad natural-language coverage, and a deterministic rule-based parser that
works offline. This module picks between them and, crucially, degrades to the
rule-based parser instead of failing a provisioning request when the LLM is
unavailable or returns something unusable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from core.config import settings
from core.logging_config import get_logger
from models.slice_models import SliceConfig
from services.llm_parser import llm_parser
from services.rule_parser import rule_based_parser

logger = get_logger("parser")


@dataclass
class ParseOutcome:
    """A parsed slice plus provenance about how it was produced."""

    config: SliceConfig
    parser_used: str
    duration_ms: float
    fallback_reason: str | None = None
    trace: dict | None = None

    @property
    def used_fallback(self) -> bool:
        return self.fallback_reason is not None


class IntentParser:
    """Selects a parsing strategy and normalises its output into a SliceConfig."""

    def __init__(self) -> None:
        self._llm = llm_parser
        self._rules = rule_based_parser

    @property
    def active_parser(self) -> str:
        return "llm" if settings.llm_available else "rule-based"

    def describe(self) -> dict:
        """Report parser availability, for the system-status endpoint."""
        return {
            "active_parser": self.active_parser,
            "llm_configured": bool(settings.groq_api_key),
            "llm_model": settings.groq_model,
            "force_rule_based": settings.force_rule_based_parser,
            "fallback_parser": "rule-based",
        }

    def parse(self, intent: str) -> ParseOutcome:
        """Parse ``intent``, preferring the LLM and falling back to the rules."""
        text = (intent or "").strip()
        if not text:
            raise ValueError("Intent must not be empty")

        started = time.perf_counter()

        if settings.llm_available:
            try:
                config_dict = self._llm.parse(text)
                outcome = self._finalise(config_dict, "llm", started)
                logger.info("Intent parsed by LLM in %.0f ms", outcome.duration_ms)
                return outcome
            except Exception as exc:
                # Any LLM problem (auth, network, malformed JSON) degrades to the
                # deterministic parser rather than failing the provisioning request.
                reason = f"{type(exc).__name__}: {exc}"
                logger.warning("LLM parsing failed, falling back to rules: %s", reason)
                return self._parse_with_rules(text, started, fallback_reason=reason)

        return self._parse_with_rules(text, started)

    def parse_with(self, intent: str, parser: str) -> ParseOutcome:
        """Parse using an explicitly requested parser ('llm' or 'rule-based')."""
        text = (intent or "").strip()
        if not text:
            raise ValueError("Intent must not be empty")
        started = time.perf_counter()
        if parser == "rule-based":
            return self._parse_with_rules(text, started)
        if parser == "llm":
            return self._finalise(self._llm.parse(text), "llm", started)
        raise ValueError(f"Unknown parser '{parser}'. Use 'llm' or 'rule-based'.")

    # --- internals -----------------------------------------------------------

    def _parse_with_rules(
        self, intent: str, started: float, fallback_reason: str | None = None
    ) -> ParseOutcome:
        config_dict, trace = self._rules.parse(intent)
        outcome = self._finalise(config_dict, "rule-based", started, fallback_reason)
        outcome.trace = trace.as_dict()
        return outcome

    def _finalise(
        self,
        config_dict: dict,
        parser_used: str,
        started: float,
        fallback_reason: str | None = None,
    ) -> ParseOutcome:
        config = SliceConfig(**config_dict)
        return ParseOutcome(
            config=config,
            parser_used=parser_used,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            fallback_reason=fallback_reason,
        )


intent_parser = IntentParser()
