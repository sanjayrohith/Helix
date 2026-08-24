"""3GPP domain knowledge used across HELIX.

Keeping the standards tables in one place means the intent parser, the
conflict detector and the exporters all reason about the same numbers instead
of each carrying their own copy of the 5QI characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- S-NSSAI Slice/Service Types (3GPP TS 23.501 §5.15.2.2) ------------------

SST_EMBB = 1
SST_URLLC = 2
SST_MMTC = 3

SST_NAMES: dict[int, str] = {
    SST_EMBB: "eMBB",
    SST_URLLC: "URLLC",
    SST_MMTC: "mMTC",
}

SST_DESCRIPTIONS: dict[int, str] = {
    SST_EMBB: "Enhanced Mobile Broadband",
    SST_URLLC: "Ultra-Reliable Low-Latency Communications",
    SST_MMTC: "Massive Machine Type Communications",
}


@dataclass(frozen=True)
class QosCharacteristics:
    """Standardised 5QI characteristics (3GPP TS 23.501 Table 5.7.4-1)."""

    qi: int
    resource_type: str  # "GBR" | "Non-GBR" | "Delay-critical GBR"
    priority_level: int
    packet_delay_budget_ms: int
    packet_error_rate: float
    example_services: str

    @property
    def is_gbr(self) -> bool:
        return self.resource_type in ("GBR", "Delay-critical GBR")


# Subset of the standard table covering the 5QIs HELIX provisions.
QOS_TABLE: dict[int, QosCharacteristics] = {
    1: QosCharacteristics(1, "GBR", 20, 100, 1e-2, "Conversational voice"),
    2: QosCharacteristics(2, "GBR", 40, 150, 1e-3, "Conversational video (live)"),
    3: QosCharacteristics(3, "GBR", 30, 50, 1e-3, "Real-time gaming, V2X messages"),
    4: QosCharacteristics(4, "GBR", 50, 300, 1e-6, "Non-conversational video"),
    5: QosCharacteristics(5, "Non-GBR", 10, 100, 1e-6, "IMS signalling"),
    6: QosCharacteristics(6, "Non-GBR", 60, 300, 1e-6, "Video buffered streaming"),
    7: QosCharacteristics(7, "Non-GBR", 70, 100, 1e-3, "Voice, live video, gaming"),
    8: QosCharacteristics(8, "Non-GBR", 80, 300, 1e-6, "Buffered video, web, email"),
    9: QosCharacteristics(9, "Non-GBR", 90, 300, 1e-6, "Default bearer, web browsing"),
    65: QosCharacteristics(65, "GBR", 7, 75, 1e-2, "Mission-critical push-to-talk voice"),
    66: QosCharacteristics(66, "GBR", 20, 100, 1e-2, "Non-mission-critical PTT voice"),
    69: QosCharacteristics(69, "Non-GBR", 5, 60, 1e-6, "Mission-critical delay-sensitive signalling"),
    70: QosCharacteristics(70, "Non-GBR", 55, 200, 1e-6, "Mission-critical data"),
    79: QosCharacteristics(79, "Non-GBR", 65, 50, 1e-2, "V2X messages"),
    80: QosCharacteristics(80, "Non-GBR", 68, 10, 1e-6, "Low-latency eMBB, AR"),
    82: QosCharacteristics(82, "Delay-critical GBR", 19, 10, 1e-4, "Discrete automation"),
    83: QosCharacteristics(83, "Delay-critical GBR", 22, 10, 1e-4, "Discrete automation, V2X"),
    84: QosCharacteristics(84, "Delay-critical GBR", 24, 30, 1e-5, "Intelligent transport systems"),
    85: QosCharacteristics(85, "Delay-critical GBR", 21, 5, 1e-5, "Electricity distribution, remote driving"),
}

DEFAULT_QOS = QOS_TABLE[9]


def get_qos(qi: int) -> QosCharacteristics | None:
    """Look up 5QI characteristics, or None when the value is non-standard."""
    return QOS_TABLE.get(qi)


def packet_delay_budget(qi: int) -> int:
    """Packet delay budget in ms for a 5QI, falling back to the default bearer."""
    qos = QOS_TABLE.get(qi)
    return qos.packet_delay_budget_ms if qos else DEFAULT_QOS.packet_delay_budget_ms


# --- ARP bands ---------------------------------------------------------------

ARP_BANDS: list[tuple[range, str]] = [
    (range(1, 2), "Mission-critical (emergency, healthcare)"),
    (range(2, 6), "High-priority business services"),
    (range(6, 11), "Standard enterprise services"),
    (range(11, 16), "Best effort / consumer"),
]


def arp_band(priority: int) -> str:
    """Human-readable band for an ARP priority level."""
    for band, label in ARP_BANDS:
        if priority in band:
            return label
    return "Unknown"


# --- Use-case profiles -------------------------------------------------------


@dataclass(frozen=True)
class UseCaseProfile:
    """A canonical slice template for a class of service."""

    key: str
    label: str
    sst: int
    qos_5qi: int
    arp_priority: int
    guaranteed_bitrate_mbps: float
    max_bitrate_mbps: float
    latency_ms: int
    security_level: str
    isolation: str
    device_count: int
    keywords: tuple[str, ...] = field(default_factory=tuple)


USE_CASE_PROFILES: tuple[UseCaseProfile, ...] = (
    UseCaseProfile(
        key="healthcare",
        label="Healthcare / Remote Surgery",
        sst=SST_URLLC,
        qos_5qi=69,
        arp_priority=1,
        guaranteed_bitrate_mbps=50.0,
        max_bitrate_mbps=120.0,
        latency_ms=5,
        security_level="critical",
        isolation="strict",
        device_count=500,
        keywords=(
            "hospital", "healthcare", "health care", "medical", "surgery", "surgical",
            "patient", "clinic", "telemedicine", "ambulance", "icu", "diagnostic",
        ),
    ),
    UseCaseProfile(
        key="emergency",
        label="Emergency Services / Public Safety",
        sst=SST_URLLC,
        qos_5qi=65,
        arp_priority=1,
        guaranteed_bitrate_mbps=40.0,
        max_bitrate_mbps=100.0,
        latency_ms=10,
        security_level="critical",
        isolation="strict",
        device_count=800,
        keywords=(
            "emergency", "public safety", "first responder", "disaster", "police",
            "fire brigade", "rescue", "civil defence", "civil defense",
        ),
    ),
    UseCaseProfile(
        key="autonomous-vehicles",
        label="Autonomous Vehicles / V2X",
        sst=SST_URLLC,
        qos_5qi=79,
        arp_priority=2,
        guaranteed_bitrate_mbps=60.0,
        max_bitrate_mbps=150.0,
        latency_ms=10,
        security_level="high",
        isolation="dedicated",
        device_count=2000,
        keywords=(
            "autonomous", "self-driving", "self driving", "v2x", "v2v", "vehicle",
            "connected car", "car", "fleet", "platooning", "drone", "uav",
        ),
    ),
    UseCaseProfile(
        key="industrial-automation",
        label="Industrial Automation / Smart Factory",
        sst=SST_URLLC,
        qos_5qi=82,
        arp_priority=3,
        guaranteed_bitrate_mbps=80.0,
        max_bitrate_mbps=200.0,
        latency_ms=5,
        security_level="high",
        isolation="dedicated",
        device_count=1500,
        keywords=(
            "factory", "industrial", "automation", "manufacturing", "robot", "plc",
            "assembly line", "warehouse", "agv", "predictive maintenance", "plant",
        ),
    ),
    UseCaseProfile(
        key="iot",
        label="IoT / Smart City Sensors",
        sst=SST_MMTC,
        qos_5qi=80,
        arp_priority=8,
        guaranteed_bitrate_mbps=30.0,
        max_bitrate_mbps=60.0,
        latency_ms=100,
        security_level="standard",
        isolation="shared",
        device_count=10000,
        keywords=(
            "iot", "sensor", "smart city", "smart meter", "meter", "telemetry",
            "asset tracking", "agriculture", "environmental", "parking", "streetlight",
            "utility", "water", "smart grid",
        ),
    ),
    UseCaseProfile(
        key="gaming-xr",
        label="Cloud Gaming / AR / VR",
        sst=SST_EMBB,
        qos_5qi=80,
        arp_priority=6,
        guaranteed_bitrate_mbps=120.0,
        max_bitrate_mbps=300.0,
        latency_ms=15,
        security_level="standard",
        isolation="dedicated",
        device_count=3000,
        keywords=(
            "gaming", "game", "esports", "ar", "vr", "xr", "augmented reality",
            "virtual reality", "metaverse", "cloud gaming", "immersive",
        ),
    ),
    UseCaseProfile(
        key="broadcast",
        label="Live Broadcast / Media Production",
        sst=SST_EMBB,
        qos_5qi=2,
        arp_priority=4,
        guaranteed_bitrate_mbps=150.0,
        max_bitrate_mbps=400.0,
        latency_ms=20,
        security_level="high",
        isolation="dedicated",
        device_count=200,
        keywords=(
            "broadcast", "live stream", "stadium", "concert", "media", "camera",
            "production", "event", "sports coverage", "news",
        ),
    ),
    UseCaseProfile(
        key="broadband",
        label="Enterprise Broadband / Fixed Wireless",
        sst=SST_EMBB,
        qos_5qi=9,
        arp_priority=5,
        guaranteed_bitrate_mbps=200.0,
        max_bitrate_mbps=500.0,
        latency_ms=20,
        security_level="standard",
        isolation="shared",
        device_count=1000,
        keywords=(
            "broadband", "internet", "office", "enterprise", "campus", "residential",
            "fixed wireless", "browsing", "video streaming", "streaming", "wifi",
            "corporate", "employees", "branch",
        ),
    ),
)

DEFAULT_PROFILE = USE_CASE_PROFILES[-1]  # Enterprise broadband

PROFILES_BY_KEY: dict[str, UseCaseProfile] = {p.key: p for p in USE_CASE_PROFILES}
