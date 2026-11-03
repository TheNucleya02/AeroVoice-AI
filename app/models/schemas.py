from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class FlightStatus(str, Enum):
    ON_TIME = "ON_TIME"
    DELAYED = "DELAYED"
    BOARDING = "BOARDING"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    DIVERTED = "DIVERTED"


class BaggageStatus(str, Enum):
    CHECKED_IN = "CHECKED_IN"
    SCREENED = "SCREENED"
    LOADED = "LOADED"
    IN_TRANSIT = "IN_TRANSIT"
    ON_CAROUSEL = "ON_CAROUSEL"
    DELAYED = "DELAYED"
    CLAIMED = "CLAIMED"


class AgentSessionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    MASKING = "MASKING"
    SPEAKING = "SPEAKING"
    ESCALATED = "ESCALATED"
    SUPERVISOR_ACTIVE = "SUPERVISOR_ACTIVE"
    DISCONNECTED = "DISCONNECTED"


class FlightInfo(BaseModel):
    flight_number: str = Field(..., description="Aviation flight number e.g. AI101, DL402")
    airline: str
    origin: str = Field(..., description="3-letter IATA code of origin airport")
    origin_name: str
    destination: str = Field(..., description="3-letter IATA code of destination airport")
    destination_name: str
    scheduled_departure: str
    estimated_departure: str
    scheduled_arrival: str
    estimated_arrival: str
    terminal: str
    gate: str
    status: FlightStatus
    delay_minutes: int = 0
    aircraft_type: str
    remarks: Optional[str] = None


class BaggageRecord(BaseModel):
    tag_number: str = Field(..., description="Baggage tag identifier e.g. BAG-90812")
    pnr_code: str
    passenger_name: str
    flight_number: str
    status: BaggageStatus
    last_seen_location: str
    carousel: Optional[str] = None
    last_updated: str
    notes: Optional[str] = None


class RebookOption(BaseModel):
    option_id: str
    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    available_seats: int
    fare_difference_usd: float = 0.0
    recommended: bool = False


class PNRRecord(BaseModel):
    pnr_code: str = Field(..., description="6-character alphanumeric Passenger Name Record")
    passenger_name: str
    flight_number: str
    origin: str
    destination: str
    travel_date: str
    seat: str
    cabin_class: str
    status: str = "CONFIRMED"
    baggage_tags: List[str] = Field(default_factory=list)

    @field_validator("pnr_code")
    @classmethod
    def validate_pnr(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not re.match(r"^[A-Z0-9]{6}$", cleaned):
            raise ValueError("PNR must be exactly 6 alphanumeric characters")
        return cleaned


class ConfidenceScore(BaseModel):
    stt_certainty: float = Field(..., ge=0.0, le=1.0, description="Acoustic STT confidence score")
    intent_entropy: float = Field(..., ge=0.0, le=1.0, description="Normalized intent distribution uncertainty")
    sentiment_score: float = Field(..., ge=0.0, le=1.0, description="Sentiment positivity/calmness rating")
    composite_confidence: float = Field(..., ge=0.0, le=1.0, description="Weighted composite confidence score")
    is_distressed: bool = False
    distress_reason: Optional[str] = None
    is_escalation_needed: bool = False


class TranscriptMessage(BaseModel):
    id: str
    speaker: str  # "user", "agent", "filler", "supervisor", "system"
    text: str
    timestamp: str
    confidence: Optional[float] = None
    is_filler: bool = False
    card_data: Optional[Dict[str, Any]] = None


class CallSessionState(BaseModel):
    session_id: str
    status: AgentSessionStatus = AgentSessionStatus.CONNECTED
    passenger_name: Optional[str] = None
    pnr_code: Optional[str] = None
    active_flight_number: Optional[str] = None
    confidence_history: List[ConfidenceScore] = Field(default_factory=list)
    latest_confidence: Optional[ConfidenceScore] = None
    transcript: List[TranscriptMessage] = Field(default_factory=list)
    created_at: str
    updated_at: str
    escalated_to_supervisor: bool = False
    supervisor_notes: Optional[str] = None


class VoiceStreamEvent(BaseModel):
    type: str  # "transcript", "filler", "agent_response", "confidence", "flight_card", "baggage_card", "escalation", "barge_in"
    session_id: str
    payload: Dict[str, Any]
    timestamp: str
