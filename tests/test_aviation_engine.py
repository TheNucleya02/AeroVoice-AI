import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import asyncio
from app.core.entity_extractor import AviationEntityExtractor
from app.core.intent_classifier import IntentClassifier, AviationIntent
from app.core.confidence_engine import ConfidenceEngine
from app.core.subagent_engine import SubagentEngine
from app.database.mock_aviation_db import AviationDatabase
from app.models.schemas import FlightStatus, BaggageStatus


@pytest.fixture
def extractor():
    return AviationEntityExtractor()


@pytest.fixture
def classifier():
    return IntentClassifier()


@pytest.fixture
def confidence_engine():
    return ConfidenceEngine()


@pytest.fixture
def subagent_engine():
    return SubagentEngine()


@pytest.fixture
def db():
    return AviationDatabase()


def test_entity_extraction_pnr_and_flight(extractor):
    # Test typical spaced speech input from STT model
    spoken_text = "Hello I want to check my reservation PNR W 7 X 9 K 2 for flight A I 1 0 1"
    entities = extractor.extract(spoken_text)

    assert "W7X9K2" in entities.pnr_codes
    assert "AI101" in entities.flight_numbers


def test_entity_extraction_baggage_and_iata(extractor):
    spoken_text = "Where is my luggage BAG-90812 flying from DEL to JFK?"
    entities = extractor.extract(spoken_text)

    assert "BAG-90812" in entities.baggage_tags
    assert "DEL" in entities.iata_airports
    assert "JFK" in entities.iata_airports


def test_intent_classification(extractor, classifier):
    # Flight status query
    text = "What is the status of flight DL402?"
    entities = extractor.extract(text)
    intent, probs = classifier.classify(text, entities)
    assert intent == AviationIntent.FLIGHT_STATUS
    assert probs[AviationIntent.FLIGHT_STATUS] > 0.3

    # Baggage tracking query
    text = "Where is my baggage BAG-90812?"
    entities = extractor.extract(text)
    intent, probs = classifier.classify(text, entities)
    assert intent == AviationIntent.BAGGAGE_TRACKING

    # Escalation query
    text = "I am tired of this, let me talk to a human agent right now"
    entities = extractor.extract(text)
    intent, probs = classifier.classify(text, entities)
    assert intent == AviationIntent.HUMAN_ESCALATION


def test_confidence_scoring_pass(confidence_engine):
    # High certainty clear input
    res = confidence_engine.compute_confidence(
        transcript_text="Please check the gate for flight AI101, thank you.",
        stt_certainty=0.98,
        intent_probabilities={"FLIGHT_STATUS": 0.95, "GREETING": 0.05},
    )
    assert res.composite_confidence >= 0.85
    assert res.is_escalation_needed is False
    assert res.is_distressed is False


def test_confidence_scoring_escalation_on_distress(confidence_engine):
    # Distress keywords trigger escalation
    res = confidence_engine.compute_confidence(
        transcript_text="This is terrible service! I am stranded at the airport and need a supervisor immediately!",
        stt_certainty=0.92,
        intent_probabilities={"HUMAN_ESCALATION": 0.90, "OTHER": 0.10},
    )
    assert res.is_distressed is True
    assert res.is_escalation_needed is True
    assert "supervisor" in (res.distress_reason or "").lower()


def test_confidence_scoring_escalation_on_low_certainty(confidence_engine):
    # Ambiguous speech with low STT certainty drops composite confidence below 0.85
    res = confidence_engine.compute_confidence(
        transcript_text="uh maybe flight somewhere... or booking maybe...",
        stt_certainty=0.55,
        intent_probabilities={"FLIGHT_STATUS": 0.33, "PNR_LOOKUP": 0.33, "GREETING": 0.34},
    )
    assert res.composite_confidence < 0.85
    assert res.is_escalation_needed is True


def test_subagent_latency_masking_and_lookup(extractor, subagent_engine):
    query = "Check status of flight AI101"
    entities = extractor.extract(query)

    # 1. Latency Masking Filler Cue is generated synchronously without dead air
    filler = subagent_engine.generate_filler_cue(
        intent=AviationIntent.FLIGHT_STATUS,
        entities=entities,
    )
    assert len(filler) > 10
    assert "AI101" in filler

    # 2. Asynchronous subagent task executes and returns structured card data
    speech, card_type, card_data = asyncio.run(
        subagent_engine.run_async_subagent_task(
            intent=AviationIntent.FLIGHT_STATUS,
            entities=entities,
            simulate_computation_delay=0.01,
        )
    )
    assert card_type == "flight_card"
    assert card_data["flight_number"] == "AI101"
    assert "Air India" in speech
    assert "on time" in speech.lower()


def test_database_rebooking(db):
    cancelled_flight = "BA178"
    options = db.get_rebook_options(cancelled_flight)
    assert len(options) >= 1

    # Rebook PNR BA9921 to BA182
    updated = db.rebook_pnr("BA9921", "BA182")
    assert updated is not None
    assert updated.flight_number == "BA182"
    assert updated.status == "REBOOKED_CONFIRMED"
