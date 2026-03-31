"""Groq LLM integration for parsing natural language intents into slice configurations."""

import json
import os
import re
import uuid
from datetime import datetime

from groq import Groq
from dotenv import load_dotenv

from models.slice_models import SliceConfig


load_dotenv()

# Telecom-specific system prompt for intent parsing
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

### Security Levels:
- "standard": Basic security, suitable for general consumer services
- "high": Enhanced encryption and authentication, enterprise use
- "critical": Maximum security with strict access controls, healthcare/government

### Isolation Types:
- "shared": Resources shared with other slices, cost-effective
- "dedicated": Dedicated resources but same physical infrastructure
- "strict": Complete isolation, separate infrastructure, highest security

## Intent Mapping Rules:

Healthcare/Hospital/Medical:
- SST=2 (URLLC), 5QI=69, ARP=1, security_level="critical", isolation="strict"

Autonomous Vehicles/V2X/Connected Cars:
- SST=2 (URLLC), 5QI=79, ARP=2, security_level="high", isolation="dedicated"

IoT/Smart City/Sensors/Smart Meters:
- SST=3 (mMTC), 5QI=80, ARP=8, security_level="standard", isolation="shared"

Video Streaming/Broadband/Enterprise Internet:
- SST=1 (eMBB), 5QI=9, ARP=5, security_level="standard", isolation="shared"

Industrial Automation/Factory:
- SST=2 (URLLC), 5QI=82, ARP=3, security_level="high", isolation="dedicated"

Gaming/AR/VR:
- SST=1 (eMBB), 5QI=80, ARP=6, security_level="standard", isolation="dedicated"

Emergency Services/Public Safety:
- SST=2 (URLLC), 5QI=69, ARP=1, security_level="critical", isolation="strict"

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


class IntentParser:
    """Parses natural language intents into 5G slice configurations using Groq LLM."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

    def parse_intent(self, intent: str) -> SliceConfig:
        """
        Parse a natural language intent into a SliceConfig.

        Args:
            intent: Plain English description of network slice requirement

        Returns:
            SliceConfig with generated parameters
        """
        # Call Groq LLM
        chat_completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Parse this network slice requirement and output only JSON:\n\n{intent}",
                },
            ],
            model=self.model,
            temperature=0.2,  # Low temperature for consistent parsing
            max_tokens=1024,
        )

        response_text = chat_completion.choices[0].message.content.strip()

        # Strip markdown code fences if present
        response_text = self._strip_json_fences(response_text)

        # Parse JSON response
        try:
            config_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON: {e}\nResponse: {response_text}"
            )

        # Generate UUID and timestamp on backend
        config_dict["slice_id"] = str(uuid.uuid4())
        config_dict["status"] = "pending"
        config_dict["created_at"] = datetime.utcnow()

        # Validate and create SliceConfig
        slice_config = SliceConfig(**config_dict)

        return slice_config

    def _strip_json_fences(self, text: str) -> str:
        """Remove markdown code fences from JSON response."""
        # Pattern to match ```json ... ``` or ``` ... ```
        patterns = [
            r"```json\s*\n?(.*?)\n?```",
            r"```\s*\n?(.*?)\n?```",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()

        return text


# Global singleton instance
intent_parser = IntentParser()
