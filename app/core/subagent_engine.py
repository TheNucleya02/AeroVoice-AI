import asyncio
import random
from typing import Dict, Any, Optional, Tuple, List
from app.models.schemas import FlightInfo, BaggageRecord, PNRRecord, RebookOption
from app.core.entity_extractor import ExtractedAviationEntities
from app.core.intent_classifier import AviationIntent
from app.database.mock_aviation_db import aviation_db


class SubagentEngine:
    """
    Asynchronous Subagent and Latency Masking Engine (Section 3.1.4).
    Prevents conversational dead air by generating immediate contextual acoustic filler cues
    while heavy airline backend database queries and rebooking calculations execute in
    background worker coroutines.
    """

    FILLER_TEMPLATES = {
        AviationIntent.FLIGHT_STATUS: [
            "Checking live operational radar and departure gate status for flight {flight} right now...",
            "Pulling up real-time telemetry and schedule details for flight {flight}...",
            "Accessing current airport departure and arrival boards for flight {flight}...",
        ],
        AviationIntent.PNR_LOOKUP: [
            "Accessing the passenger reservation system for PNR {pnr}...",
            "Retrieving your booking confirmation and itinerary for reference {pnr}...",
            "Looking up your passenger record and assigned seat for PNR {pnr}...",
        ],
        AviationIntent.BAGGAGE_TRACKING: [
            "Connecting to the baggage sorting telemetry system for tag {bag}...",
            "Tracking the latest RFID cargo scan and carousel location for tag {bag}...",
            "Querying ground handling baggage operations for tag {bag}...",
        ],
        AviationIntent.FLIGHT_REBOOKING: [
            "Checking alternative flights, available seats, and fare recalculation options...",
            "Querying real-time airline inventory to find the fastest rebooking options for you...",
            "Scanning available flights to your destination to arrange immediate rebooking...",
        ],
        AviationIntent.SEAT_INQUIRY: [
            "Opening your aircraft cabin layout and seat assignment...",
            "Checking current seat availability and cabin configuration...",
        ],
        AviationIntent.HUMAN_ESCALATION: [
            "Initiating priority supervisor handoff and preserving your conversation context...",
            "Paging an airline operations supervisor with your itinerary details...",
        ],
        AviationIntent.GREETING: [
            "AeroVoice AI operational system online. How may I assist your travel today?",
        ],
    }

    def generate_filler_cue(
        self,
        intent: str,
        entities: ExtractedAviationEntities,
        session_pnr: Optional[str] = None,
        session_flight: Optional[str] = None,
    ) -> str:
        """
        Synthesizes an immediate contextual acoustic filler cue to eliminate dead air.
        """
        templates = self.FILLER_TEMPLATES.get(intent, [
            "Processing your request with airline operations right now..."
        ])
        template = random.choice(templates)

        flight = (
            entities.flight_numbers[0]
            if entities.flight_numbers
            else (session_flight or "your flight")
        )
        pnr = (
            entities.pnr_codes[0]
            if entities.pnr_codes
            else (session_pnr or "your booking")
        )
        bag = (
            entities.baggage_tags[0]
            if entities.baggage_tags
            else "your checked luggage"
        )

        return template.format(flight=flight, pnr=pnr, bag=bag)

    async def run_async_subagent_task(
        self,
        intent: str,
        entities: ExtractedAviationEntities,
        session_pnr: Optional[str] = None,
        session_flight: Optional[str] = None,
        simulate_computation_delay: float = 1.2,
    ) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Executes background asynchronous aviation lookup subagent.
        Returns:
            - final_speech_text: Response to be synthesized into TTS
            - card_type: 'flight', 'baggage', 'rebook', 'pnr', or None
            - card_data: Serialized card payload for visual rendering
        """
        # Simulate realistic multi-step airline GDS/database retrieval delay
        if simulate_computation_delay > 0:
            await asyncio.sleep(simulate_computation_delay)

        # 1. PNR LOOKUP INTENT
        if intent == AviationIntent.PNR_LOOKUP or (entities.pnr_codes and intent != AviationIntent.FLIGHT_REBOOKING):
            pnr_code = entities.pnr_codes[0] if entities.pnr_codes else session_pnr
            if pnr_code:
                pnr_data = aviation_db.get_pnr(pnr_code)
                if pnr_data:
                    flight_data = aviation_db.get_flight(pnr_data.flight_number)
                    status_desc = flight_data.status.value if flight_data else pnr_data.status
                    speech = (
                        f"Passenger {pnr_data.passenger_name}, booking reference {pnr_data.pnr_code} is confirmed "
                        f"for flight {pnr_data.flight_number} from {pnr_data.origin} to {pnr_data.destination}. "
                        f"Your seat is {pnr_data.seat} in {pnr_data.cabin_class}. Flight status is {status_desc}."
                    )
                    if flight_data and flight_data.status == "DELAYED":
                        speech += f" Please note there is an estimated delay of {flight_data.delay_minutes} minutes."
                    elif flight_data and flight_data.status == "CANCELLED":
                        speech += " This flight has unfortunately been cancelled. I can assist you with immediate rebooking."

                    card_payload = {
                        "pnr": pnr_data.model_dump(),
                        "flight": flight_data.model_dump() if flight_data else None,
                    }
                    return speech, "pnr_card", card_payload
                else:
                    return (
                        f"I could not locate a reservation matching PNR code {pnr_code}. "
                        "Please verify the 6-character reference or speak with an agent.",
                        None,
                        None,
                    )

        # 2. FLIGHT STATUS INTENT
        if intent == AviationIntent.FLIGHT_STATUS or entities.flight_numbers:
            flight_no = entities.flight_numbers[0] if entities.flight_numbers else session_flight
            if flight_no:
                flight = aviation_db.get_flight(flight_no)
                if flight:
                    if flight.status == "ON_TIME":
                        speech = (
                            f"Flight {flight.flight_number} operated by {flight.airline} from {flight.origin} to {flight.destination} "
                            f"is on time. Scheduled departure is {flight.scheduled_departure} from Terminal {flight.terminal}, {flight.gate}."
                        )
                    elif flight.status == "DELAYED":
                        speech = (
                            f"Flight {flight.flight_number} from {flight.origin} to {flight.destination} is currently delayed by "
                            f"{flight.delay_minutes} minutes. New estimated departure is {flight.estimated_departure} at {flight.gate}."
                        )
                    elif flight.status == "CANCELLED":
                        speech = (
                            f"Flight {flight.flight_number} to {flight.destination} has been cancelled due to {flight.remarks} "
                            "We have rebooking options ready for you."
                        )
                    elif flight.status == "BOARDING":
                        speech = (
                            f"Flight {flight.flight_number} to {flight.destination} is currently boarding at {flight.gate}. "
                            "Please proceed to the gate immediately."
                        )
                    else:
                        speech = (
                            f"Flight {flight.flight_number} is currently {flight.status}. "
                            f"Departure scheduled for {flight.scheduled_departure} at {flight.gate}."
                        )
                    return speech, "flight_card", flight.model_dump()
                else:
                    return (
                        f"I checked the radar schedules, but flight {flight_no} is not listed in today's active roster. "
                        "Would you like me to check connecting routes?",
                        None,
                        None,
                    )

        # 3. BAGGAGE TRACKING INTENT
        if intent == AviationIntent.BAGGAGE_TRACKING:
            tag_no = None
            if entities.baggage_tags:
                tag_no = entities.baggage_tags[0]
            elif session_pnr:
                bags = aviation_db.get_baggage_by_pnr(session_pnr)
                if bags:
                    tag_no = bags[0].tag_number

            if tag_no:
                bag = aviation_db.get_baggage(tag_no)
                if bag:
                    speech = (
                        f"Luggage tag {bag.tag_number} for passenger {bag.passenger_name} on flight {bag.flight_number} "
                        f"is currently {bag.status.value}. Last recorded scan: {bag.last_seen_location} at {bag.last_updated}."
                    )
                    if bag.carousel:
                        speech += f" You can collect your bag at Carousel {bag.carousel}."
                    return speech, "baggage_card", bag.model_dump()

            return (
                "To track your baggage, please provide your baggage tag number or your 6-character PNR code.",
                None,
                None,
            )

        # 4. FLIGHT REBOOKING INTENT
        if intent == AviationIntent.FLIGHT_REBOOKING:
            flight_no = entities.flight_numbers[0] if entities.flight_numbers else (session_flight or "BA178")
            options = aviation_db.get_rebook_options(flight_no)
            if options:
                top = options[0]
                speech = (
                    f"I found {len(options)} available alternative options for your disrupted flight. "
                    f"The recommended option is {top.airline} flight {top.flight_number}, departing at {top.departure_time} "
                    f"with {top.available_seats} seats remaining at zero fare difference. Would you like me to confirm this rebooking?"
                )
                return speech, "rebook_card", {"options": [o.model_dump() for o in options]}
            else:
                return (
                    f"There are no direct automated rebooking slots found for flight {flight_no}. "
                    "Let me escalate this to our airline rebooking supervisor for priority handling.",
                    None,
                    None,
                )

        # 5. SEAT INQUIRY
        if intent == AviationIntent.SEAT_INQUIRY:
            pnr_code = entities.pnr_codes[0] if entities.pnr_codes else session_pnr
            if pnr_code:
                pnr_data = aviation_db.get_pnr(pnr_code)
                if pnr_data:
                    return (
                        f"For booking {pnr_data.pnr_code}, your reserved seat is {pnr_data.seat} in {pnr_data.cabin_class} "
                        f"on flight {pnr_data.flight_number}.",
                        "pnr_card",
                        {"pnr": pnr_data.model_dump()},
                    )
            return (
                "Please state your 6-character booking code (PNR) so I can verify your seat assignment.",
                None,
                None,
            )

        # 6. GREETING
        if intent == AviationIntent.GREETING:
            return (
                "Hello! Welcome to AeroVoice AI customer support. I can assist you with real-time flight status, "
                "PNR booking details, baggage tracking, or automated flight rebooking. How can I help you today?",
                None,
                None,
            )

        # Default fallback
        return (
            "I'm listening. You can state your 6-character PNR, flight number (e.g. AI101 or DL402), or baggage tag "
            "and I will pull up the details immediately.",
            None,
            None,
        )


subagent_engine = SubagentEngine()
