"""Groq-backed natural-language intent parser.

The Groq SDK and the API key are both resolved lazily: importing this module
must never fail, because HELIX is expected to boot and serve the deterministic
parser when no LLM is configured.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime

from core.config import settings
from core.logging_config import get_logger

logger = get_logger("parser.llm")

SYSTEM_PROMPT = """You are an expert 5G network slice configuration assistant with deep knowledge of 3GPP specifications and telecom standards.

Your task is to parse natural language network slice requirements and output ONLY a valid JSON object with the slice configuration. Never include any explanation, markdown formatting, or text before/after the JSON.

## 5G Network Slicing Knowledge:

### S-NSSAI (Single Network Slice Selection Assistance Information):
- SST (Slice/Service Type):
  - SST=1: eMBB (enhanced Mobile Broadband) - high throughput, video streaming, general internet
  - SST=2: URLLC (Ultra-Reliable Low-Latency Communications) - mission-critical, healthcare, autonomous vehicles, industrial automation
  - SST=3: mMTC (massive Machine Type Communications) - IoT sensors, smart city, smart meters

### 5QI (5G QoS Identifier) Values:
- 5QI=1: Conversational voice
- 5QI=2: Conversational video (live streaming)
- 5QI=5: IMS signaling
- 5QI=9: Video streaming, TCP-based (e.g., buffered streaming, web browsing)
- 5QI=65: Mission-critical push-to-talk voice
- 5QI=69: Mission-critical delay-sensitive signaling (healthcare, emergency services)
- 5QI=70: Mission-critical data
- 5QI=79: V2X messages
- 5QI=80: Low-latency eMBB, IoT with moderate latency requirements
- 5QI=82-85: Discrete automation, ultra-low latency

### ARP (Allocation and Retention Priority):
- Range: 1 (highest priority) to 15 (lowest priority)
- ARP=1: Reserved for mission-critical services (healthcare, emergency)
- ARP=2-5: High priority business services
- ARP=6-10: Standard enterprise services
- ARP=11-15: Best effort, consumer services

### Use Case Mapping:
Healthcare/Hospital/Medical: SST=2, 5QI=69, ARP=1, security="critical", isolation="strict"
Emergency Services/Public Safety: SST=2, 5QI=65, ARP=1, security="critical", isolation="strict"
Autonomous Vehicles/V2X: SST=2, 5QI=79, ARP=2, security="high", isolation="dedicated"
Industrial Automation/Factory: SST=2, 5QI=82, ARP=3, security="high", isolation="dedicated"
IoT/Smart City/Sensors: SST=3, 5QI=80, ARP=8, security="standard", isolation="shared"
Gaming/AR/VR: SST=1, 5QI=80, ARP=6, security="standard", isolation="dedicated"
Live Broadcast/Media: SST=1, 5QI=2, ARP=4, security="high", isolation="dedicated"
Video Streaming/Broadband/Enterprise: SST=1, 5QI=9, ARP=5, security="standard", isolation="shared"

## Output JSON Schema (required fields):
{
  "name": "string - descriptive name for the slice",
  "sst": "integer 1-3",
  "sd": "string hex format like '0x000100'",
  "qos_5qi": "integer 1-255",
  "arp_priority": "integer 1-15",
  "guaranteed_bitrate_mbps": "float",
  "max_bitrate_mbps": "float - must be >= guaranteed_bitrate",
  "latency_ms": "integer in milliseconds",
  "security_level": "standard|high|critical",
  "isolation": "shared|dedicated|strict",
  "device_count": "integer",
  "use_case": "string category",
  "location": "string location/zone"
}

Generate a unique SD value in hex format (0x followed by 6 hex digits). Infer reasonable defaults for any values not explicitly specified in the intent.

CRITICAL: Output ONLY the JSON object. No markdown code blocks, no explanation, no text before or after."""


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM parser cannot be used at all."""


class LLMParseError(ValueError):
    """Raised when the LLM responded but the response was not usable."""


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences that models sometimes wrap JSON in."""
    for pattern in (r"```json\s*\n?(.*?)\n?```", r"```\s*\n?(.*?)\n?```"):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text


def _extract_json_object(text: str) -> str:
    """Return the outermost JSON object in ``text``.

    Models occasionally prepend a sentence despite the instructions; slicing to
    the outermost braces recovers the payload instead of failing the request.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMParseError(f"No JSON object found in LLM response: {text[:200]}")
    return text[start : end + 1]


class LLMIntentParser:
    """Parses intents with Groq, constructing its client on first use."""

    name = "llm"

    def __init__(self) -> None:
        self._client = None
        self._client_error: str | None = None

    @property
    def available(self) -> bool:
        """True when a client can plausibly be built (key present, SDK installed)."""
        if not settings.llm_available:
            return False
        try:
            self._ensure_client()
        except LLMUnavailableError:
            return False
        return True

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if self._client_error:
            raise LLMUnavailableError(self._client_error)

        if not settings.groq_api_key:
            self._client_error = "GROQ_API_KEY is not set"
            raise LLMUnavailableError(self._client_error)
        try:
            from groq import Groq  # imported lazily: optional dependency
        except ImportError as exc:  # pragma: no cover - depends on environment
            self._client_error = f"groq package is not installed ({exc})"
            raise LLMUnavailableError(self._client_error) from exc

        self._client = Groq(api_key=settings.groq_api_key, timeout=settings.llm_timeout_seconds)
        logger.info("Groq client initialised (model=%s)", settings.groq_model)
        return self._client

    def parse(self, intent: str) -> dict:
        """Parse an intent into a slice-config dict.

        Raises:
            LLMUnavailableError: no usable client.
            LLMParseError: the model replied with something unparseable.
        """
        client = self._ensure_client()

        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Parse this network slice requirement and output only JSON:\n\n" + intent
                    ),
                },
            ],
            model=settings.groq_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        raw = (completion.choices[0].message.content or "").strip()
        payload = _extract_json_object(_strip_json_fences(raw))

        try:
            config = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise LLMParseError(f"LLM returned invalid JSON: {exc}") from exc
        if not isinstance(config, dict):
            raise LLMParseError("LLM returned JSON that is not an object")

        config["slice_id"] = str(uuid.uuid4())
        config["status"] = "pending"
        config["created_at"] = datetime.now(UTC)
        return config


llm_parser = LLMIntentParser()
