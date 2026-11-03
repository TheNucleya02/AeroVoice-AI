import re
import math
from typing import Dict, Tuple, Optional
from app.core.entity_extractor import AviationEntityExtractor, ExtractedAviationEntities


class AviationIntent:
    FLIGHT_STATUS = "FLIGHT_STATUS"
    PNR_LOOKUP = "PNR_LOOKUP"
    BAGGAGE_TRACKING = "BAGGAGE_TRACKING"
    FLIGHT_REBOOKING = "FLIGHT_REBOOKING"
    SEAT_INQUIRY = "SEAT_INQUIRY"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    GREETING = "GREETING"
    UNKNOWN = "UNKNOWN"


class IntentClassifier:
    """
    Classifies aviation customer service intents and estimates probability distribution
    for intent entropy scoring.
    """

    def __init__(self, extractor: Optional[AviationEntityExtractor] = None):
        self.extractor = extractor or AviationEntityExtractor()

    def classify(
        self, text: str, entities: ExtractedAviationEntities
    ) -> Tuple[str, Dict[str, float]]:
        cleaned = text.lower().strip()

        # Score accumulator for intents
        scores: Dict[str, float] = {
            AviationIntent.FLIGHT_STATUS: 0.05,
            AviationIntent.PNR_LOOKUP: 0.05,
            AviationIntent.BAGGAGE_TRACKING: 0.05,
            AviationIntent.FLIGHT_REBOOKING: 0.05,
            AviationIntent.SEAT_INQUIRY: 0.05,
            AviationIntent.HUMAN_ESCALATION: 0.05,
            AviationIntent.GREETING: 0.05,
        }

        # Check for Greeting
        if any(w in cleaned for w in ["hello", "hi", "hey", "good morning", "good afternoon", "greetings"]):
            scores[AviationIntent.GREETING] += 0.70

        # Check for Human Escalation
        if any(w in cleaned for w in ["human", "agent", "supervisor", "representative", "operator", "take over"]):
            scores[AviationIntent.HUMAN_ESCALATION] += 0.85

        # Check for Baggage Tracking
        if any(w in cleaned for w in ["bag", "luggage", "suitcase", "carousel", "baggage"]) or entities.baggage_tags:
            scores[AviationIntent.BAGGAGE_TRACKING] += 0.75
            if entities.baggage_tags:
                scores[AviationIntent.BAGGAGE_TRACKING] += 0.20

        # Check for Rebooking / Change
        if any(w in cleaned for w in ["rebook", "reschedule", "alternative", "change flight", "cancelled flight", "next flight", "new flight"]):
            scores[AviationIntent.FLIGHT_REBOOKING] += 0.80

        # Check for Seat Inquiry
        if any(w in cleaned for w in ["seat", "seat number", "window seat", "aisle"]):
            scores[AviationIntent.SEAT_INQUIRY] += 0.70

        # Check for PNR / Booking Lookup
        if any(w in cleaned for w in ["pnr", "booking", "reservation", "itinerary", "ticket"]) or entities.pnr_codes:
            scores[AviationIntent.PNR_LOOKUP] += 0.70
            if entities.pnr_codes:
                scores[AviationIntent.PNR_LOOKUP] += 0.25

        # Check for Flight Status
        if any(w in cleaned for w in ["status", "delayed", "on time", "gate", "terminal", "boarding", "departure", "arrival", "flying", "schedule"]) or entities.flight_numbers:
            scores[AviationIntent.FLIGHT_STATUS] += 0.65
            if entities.flight_numbers:
                scores[AviationIntent.FLIGHT_STATUS] += 0.25

        # Apply temperature-scaled softmax for realistic intent distribution
        temperature = 0.18
        max_score = max(scores.values())
        exp_scores = {k: math.exp((v - max_score) / temperature) for k, v in scores.items()}
        total_exp = sum(exp_scores.values())
        probabilities = {k: round(v / total_exp, 4) for k, v in exp_scores.items()}

        # Top intent
        top_intent = max(probabilities, key=probabilities.get)

        # Disambiguate if PNR is present and query is about status
        if entities.pnr_codes and top_intent not in [AviationIntent.HUMAN_ESCALATION, AviationIntent.FLIGHT_REBOOKING]:
            if "bag" in cleaned:
                top_intent = AviationIntent.BAGGAGE_TRACKING
            else:
                top_intent = AviationIntent.PNR_LOOKUP

        return top_intent, probabilities


intent_classifier = IntentClassifier()
