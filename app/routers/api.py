from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.database.mock_aviation_db import aviation_db
from app.models.schemas import FlightInfo, PNRRecord, BaggageRecord, RebookOption, CallSessionState
from app.core.entity_extractor import extracted_entities
from app.core.intent_classifier import intent_classifier
from app.core.confidence_engine import confidence_engine
from app.core.supervisor_manager import supervisor_manager

api_router = APIRouter(prefix="/api", tags=["AeroVoice REST API"])


class RebookRequest(BaseModel):
    pnr_code: str
    new_flight_number: str


class SupervisorMessageRequest(BaseModel):
    message: str
    supervisor_name: str = "Lead Supervisor"


class AnalyzeSpeechRequest(BaseModel):
    text: str
    stt_certainty: float = 0.95
    session_pnr: Optional[str] = None
    session_flight: Optional[str] = None


@api_router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "system": "AeroVoice AI Platform",
        "architecture": "Event-Driven Fast-API Web Audio Gateway",
        "active_sessions": len(supervisor_manager.active_sessions),
    }


# Flight Endpoints
@api_router.get("/flights", response_model=List[FlightInfo])
def get_all_flights():
    return list(aviation_db.flights.values())


@api_router.get("/flights/{flight_number}", response_model=FlightInfo)
def get_flight(flight_number: str):
    flight = aviation_db.get_flight(flight_number)
    if not flight:
        raise HTTPException(status_code=404, detail=f"Flight {flight_number} not found")
    return flight


# PNR Endpoints
@api_router.get("/pnr/{pnr_code}", response_model=PNRRecord)
def get_pnr(pnr_code: str):
    pnr = aviation_db.get_pnr(pnr_code)
    if not pnr:
        raise HTTPException(status_code=404, detail=f"PNR record {pnr_code} not found")
    return pnr


# Baggage Endpoints
@api_router.get("/baggage/{tag_number}", response_model=BaggageRecord)
def get_baggage(tag_number: str):
    bag = aviation_db.get_baggage(tag_number)
    if not bag:
        raise HTTPException(status_code=404, detail=f"Baggage tag {tag_number} not found")
    return bag


@api_router.get("/baggage/by-pnr/{pnr_code}", response_model=List[BaggageRecord])
def get_baggage_by_pnr(pnr_code: str):
    return aviation_db.get_baggage_by_pnr(pnr_code)


# Rebooking Endpoints
@api_router.get("/rebook/options/{flight_number}", response_model=List[RebookOption])
def get_rebooking_options(flight_number: str):
    options = aviation_db.get_rebook_options(flight_number)
    return options


@api_router.post("/rebook")
def execute_rebooking(req: RebookRequest):
    updated_pnr = aviation_db.rebook_pnr(req.pnr_code, req.new_flight_number)
    if not updated_pnr:
        raise HTTPException(status_code=400, detail="Rebooking failed: invalid PNR or Flight number")
    return {
        "status": "success",
        "message": f"PNR {req.pnr_code} successfully rebooked to flight {req.new_flight_number}",
        "pnr": updated_pnr,
    }


# Supervisor Endpoints
@api_router.get("/supervisor/sessions", response_model=List[CallSessionState])
def list_call_sessions():
    return supervisor_manager.list_sessions()


@api_router.get("/supervisor/session/{session_id}", response_model=CallSessionState)
def get_call_session(session_id: str):
    session = supervisor_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Call session not found")
    return session


@api_router.post("/supervisor/takeover/{session_id}")
async def supervisor_takeover(session_id: str, supervisor_name: str = Query("Lead Supervisor")):
    success = supervisor_manager.takeover_call(session_id, supervisor_name)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found for takeover")

    # Notify passenger
    takeover_event = {
        "type": "supervisor_takeover",
        "session_id": session_id,
        "message": f"Supervisor {supervisor_name} has connected to your call. How may I help you?",
        "timestamp": "now",
    }
    await supervisor_manager.send_to_passenger(session_id, takeover_event)

    # Broadcast to other supervisors
    await supervisor_manager.broadcast_to_supervisors(
        "session_taken_over",
        {"session_id": session_id, "supervisor": supervisor_name},
    )

    return {"status": "success", "message": f"Session {session_id} taken over by {supervisor_name}"}


@api_router.post("/supervisor/message/{session_id}")
async def supervisor_send_message(session_id: str, req: SupervisorMessageRequest):
    session = supervisor_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Add message to transcript
    msg = supervisor_manager.add_transcript(
        session_id=session_id,
        speaker="supervisor",
        text=req.message,
    )

    # Deliver to passenger
    payload = {
        "type": "supervisor_message",
        "session_id": session_id,
        "speaker": req.supervisor_name,
        "message": req.message,
    }
    await supervisor_manager.send_to_passenger(session_id, payload)

    # Broadcast update to supervisor dashboard
    await supervisor_manager.broadcast_to_supervisors(
        "transcript_added",
        {"session_id": session_id, "transcript_item": msg.model_dump() if msg else {}},
    )

    return {"status": "success", "message": "Dispatched to passenger"}


# Direct Diagnostic & Testing Endpoint
@api_router.post("/test/analyze")
def test_analyze(req: AnalyzeSpeechRequest):
    """
    Diagnostic tool to test entity extraction, intent classification, and confidence scoring
    without needing a WebSocket client.
    """
    entities = extracted_entities.extract(req.text)
    intent, intent_probs = intent_classifier.classify(req.text, entities)
    confidence = confidence_engine.compute_confidence(
        transcript_text=req.text,
        stt_certainty=req.stt_certainty,
        intent_probabilities=intent_probs,
    )

    return {
        "input_text": req.text,
        "extracted_entities": entities.model_dump(),
        "primary_intent": intent,
        "intent_distribution": intent_probs,
        "confidence_evaluation": confidence.model_dump(),
        "escalation_triggered": confidence.is_escalation_needed,
    }
