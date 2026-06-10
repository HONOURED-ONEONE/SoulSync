from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CandidateModelSpec:
    provider: str
    model_id: str
    modality: Literal["text", "voice", "multimodal"] = "text"
    capability_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class NIMSControlVector:
    literalness: str = "high"
    topic_adherence: str = "medium"
    response_length: str = "short"
    repair_mode: str = "clarify_first"
    turn_latency_ms: int = 700
    cognitive_load: str = "low"


@dataclass
class NIMSTurnInput:
    user_id: int | None
    user_text: str
    voice_mode: str
    context: str | None = None


@dataclass
class NIMSTurnOutput:
    final_text: str
    raw_model_response: str
    control_vector: dict[str, Any]
    arbitration: dict[str, Any]
    topic_ledger: dict[str, Any]
    guardrail: dict[str, Any]
