from typing import Dict, List, Optional
from datetime import datetime, timezone
from app.models.schemas import FlightInfo, FlightStatus, BaggageRecord, BaggageStatus, PNRRecord, RebookOption


class AviationDatabase:
    def __init__(self):
        self.flights: Dict[str, FlightInfo] = {}
        self.pnrs: Dict[str, PNRRecord] = {}
        self.baggage: Dict[str, BaggageRecord] = {}
        self.rebook_inventory: Dict[str, List[RebookOption]] = {}
        self._seed_database()

    def _seed_database(self):
        # Seed Flights
        self.flights = {
            "AI101": FlightInfo(
                flight_number="AI101",
                airline="Air India",
                origin="DEL",
                origin_name="Indira Gandhi International Airport, New Delhi",
                destination="JFK",
                destination_name="John F. Kennedy International Airport, New York",
                scheduled_departure="2026-11-04 02:15",
                estimated_departure="2026-11-04 02:15",
                scheduled_arrival="2026-11-04 07:45",
                estimated_arrival="2026-11-04 07:45",
                terminal="T3",
                gate="Gate 32A",
                status=FlightStatus.ON_TIME,
                delay_minutes=0,
                aircraft_type="Boeing 777-300ER",
                remarks="Flight operating on schedule. Boarding begins 45 minutes prior to departure.",
            ),
            "DL402": FlightInfo(
                flight_number="DL402",
                airline="Delta Air Lines",
                origin="JFK",
                origin_name="John F. Kennedy International Airport, New York",
                destination="LAX",
                destination_name="Los Angeles International Airport",
                scheduled_departure="2026-11-04 14:00",
                estimated_departure="2026-11-04 16:15",
                scheduled_arrival="2026-11-04 17:30",
                estimated_arrival="2026-11-04 19:45",
                terminal="T4",
                gate="Gate B24",
                status=FlightStatus.DELAYED,
                delay_minutes=135,
                aircraft_type="Airbus A350-900",
                remarks="Delayed due to adverse crosswinds and air traffic ground stop at JFK.",
            ),
            "BA178": FlightInfo(
                flight_number="BA178",
                airline="British Airways",
                origin="JFK",
                origin_name="John F. Kennedy International Airport, New York",
                destination="LHR",
                destination_name="London Heathrow Airport",
                scheduled_departure="2026-11-04 08:30",
                estimated_departure="CANCELLED",
                scheduled_arrival="2026-11-04 20:30",
                estimated_arrival="CANCELLED",
                terminal="T7",
                gate="Gate 12",
                status=FlightStatus.CANCELLED,
                delay_minutes=0,
                aircraft_type="Boeing 787-9 Dreamliner",
                remarks="Flight cancelled due to unscheduled aircraft maintenance. Rebooking available.",
            ),
            "BA182": FlightInfo(
                flight_number="BA182",
                airline="British Airways",
                origin="JFK",
                origin_name="John F. Kennedy International Airport, New York",
                destination="LHR",
                destination_name="London Heathrow Airport",
                scheduled_departure="2026-11-04 12:15",
                estimated_departure="2026-11-04 12:15",
                scheduled_arrival="2026-11-05 00:15",
                estimated_arrival="2026-11-05 00:15",
                terminal="T7",
                gate="Gate 18",
                status=FlightStatus.ON_TIME,
                delay_minutes=0,
                aircraft_type="Boeing 777-200ER",
                remarks="Replacement direct service to London Heathrow.",
            ),
            "DL416": FlightInfo(
                flight_number="DL416",
                airline="Delta Air Lines",
                origin="JFK",
                origin_name="John F. Kennedy International Airport, New York",
                destination="LAX",
                destination_name="Los Angeles International Airport",
                scheduled_departure="2026-11-04 18:00",
                estimated_departure="2026-11-04 18:00",
                scheduled_arrival="2026-11-04 21:15",
                estimated_arrival="2026-11-04 21:15",
                terminal="T4",
                gate="Gate B30",
                status=FlightStatus.ON_TIME,
                delay_minutes=0,
                aircraft_type="Boeing 767-400ER",
                remarks="Alternative non-stop evening service to LAX.",
            ),
            "EK505": FlightInfo(
                flight_number="EK505",
                airline="Emirates",
                origin="BOM",
                origin_name="Chhatrapati Shivaji Maharaj International Airport, Mumbai",
                destination="DXB",
                destination_name="Dubai International Airport",
                scheduled_departure="2026-11-04 10:10",
                estimated_departure="2026-11-04 10:10",
                scheduled_arrival="2026-11-04 12:25",
                estimated_arrival="2026-11-04 12:25",
                terminal="T2",
                gate="Gate 48B",
                status=FlightStatus.BOARDING,
                delay_minutes=0,
                aircraft_type="Airbus A380-800",
                remarks="Boarding currently in progress. Final call for Zones A and B.",
            ),
            "UA890": FlightInfo(
                flight_number="UA890",
                airline="United Airlines",
                origin="SFO",
                origin_name="San Francisco International Airport",
                destination="ORD",
                destination_name="Chicago O'Hare International Airport",
                scheduled_departure="2026-11-04 15:45",
                estimated_departure="2026-11-04 15:45",
                scheduled_arrival="2026-11-04 21:55",
                estimated_arrival="2026-11-04 21:55",
                terminal="T3",
                gate="Gate 77",
                status=FlightStatus.ON_TIME,
                delay_minutes=0,
                aircraft_type="Boeing 737 MAX 9",
                remarks="On schedule. In-flight Wi-Fi and power outlets available.",
            ),
        }

        # Seed PNRs (6-character alphanumeric)
        self.pnrs = {
            "W7X9K2": PNRRecord(
                pnr_code="W7X9K2",
                passenger_name="Shriyansh Kushwaha",
                flight_number="AI101",
                origin="DEL",
                destination="JFK",
                travel_date="2026-11-04",
                seat="14B",
                cabin_class="Economy Premium",
                status="CONFIRMED",
                baggage_tags=["BAG-90812"],
            ),
            "DL8401": PNRRecord(
                pnr_code="DL8401",
                passenger_name="Sarah Connor",
                flight_number="DL402",
                origin="JFK",
                destination="LAX",
                travel_date="2026-11-04",
                seat="22A",
                cabin_class="Economy",
                status="DELAYED",
                baggage_tags=["BAG-55421"],
            ),
            "BA9921": PNRRecord(
                pnr_code="BA9921",
                passenger_name="David Smith",
                flight_number="BA178",
                origin="JFK",
                destination="LHR",
                travel_date="2026-11-04",
                seat="10C",
                cabin_class="Club World (Business)",
                status="CANCELLED_REQUIRES_REBOOKING",
                baggage_tags=["BAG-10294"],
            ),
            "EK4032": PNRRecord(
                pnr_code="EK4032",
                passenger_name="Priya Sharma",
                flight_number="EK505",
                origin="BOM",
                destination="DXB",
                travel_date="2026-11-04",
                seat="05K",
                cabin_class="First Class",
                status="BOARDING",
                baggage_tags=["BAG-77319"],
            ),
        }

        # Seed Baggage Records
        self.baggage = {
            "BAG-90812": BaggageRecord(
                tag_number="BAG-90812",
                pnr_code="W7X9K2",
                passenger_name="Shriyansh Kushwaha",
                flight_number="AI101",
                status=BaggageStatus.LOADED,
                last_seen_location="DEL Cargo Ramp Hold 3",
                carousel=None,
                last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                notes="Bag scanned onto container AKE-44910. Destination JFK Terminal 4.",
            ),
            "BAG-55421": BaggageRecord(
                tag_number="BAG-55421",
                pnr_code="DL8401",
                passenger_name="Sarah Connor",
                flight_number="DL402",
                status=BaggageStatus.IN_TRANSIT,
                last_seen_location="JFK Terminal 4 Staging Bay",
                carousel=None,
                last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                notes="Holding securely in tarmac buffer zone awaiting aircraft repositioning.",
            ),
            "BAG-10294": BaggageRecord(
                tag_number="BAG-10294",
                pnr_code="BA9921",
                passenger_name="David Smith",
                flight_number="BA178",
                status=BaggageStatus.DELAYED,
                last_seen_location="JFK Terminal 7 Baggage Sorting Hub",
                carousel=None,
                last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                notes="Holding in central sorting bay. Will be rerouted automatically upon flight rebooking.",
            ),
            "BAG-77319": BaggageRecord(
                tag_number="BAG-77319",
                pnr_code="EK4032",
                passenger_name="Priya Sharma",
                flight_number="EK505",
                status=BaggageStatus.LOADED,
                last_seen_location="BOM Terminal 2 ULD Bay 7",
                carousel=None,
                last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                notes="Priority baggage tag attached. Stowed in forward belly hold.",
            ),
        }

        # Seed Rebooking Options for Cancelled/Delayed Flights
        self.rebook_inventory = {
            "BA178": [
                RebookOption(
                    option_id="RB-BA-112",
                    flight_number="BA182",
                    airline="British Airways",
                    origin="JFK",
                    destination="LHR",
                    departure_time="2026-11-04 12:15",
                    arrival_time="2026-11-05 00:15",
                    available_seats=8,
                    fare_difference_usd=0.0,
                    recommended=True,
                ),
                RebookOption(
                    option_id="RB-VS-450",
                    flight_number="VS004",
                    airline="Virgin Atlantic",
                    origin="JFK",
                    destination="LHR",
                    departure_time="2026-11-04 18:30",
                    arrival_time="2026-11-05 06:45",
                    available_seats=14,
                    fare_difference_usd=0.0,
                    recommended=False,
                ),
            ],
            "DL402": [
                RebookOption(
                    option_id="RB-DL-509",
                    flight_number="DL416",
                    airline="Delta Air Lines",
                    origin="JFK",
                    destination="LAX",
                    departure_time="2026-11-04 18:00",
                    arrival_time="2026-11-04 21:15",
                    available_seats=5,
                    fare_difference_usd=0.0,
                    recommended=True,
                )
            ],
        }

    def get_flight(self, flight_number: str) -> Optional[FlightInfo]:
        key = flight_number.upper().replace(" ", "")
        return self.flights.get(key)

    def get_pnr(self, pnr_code: str) -> Optional[PNRRecord]:
        key = pnr_code.upper().strip()
        return self.pnrs.get(key)

    def get_baggage(self, tag_number: str) -> Optional[BaggageRecord]:
        key = tag_number.upper().strip()
        return self.baggage.get(key)

    def get_baggage_by_pnr(self, pnr_code: str) -> List[BaggageRecord]:
        pnr = self.get_pnr(pnr_code)
        if not pnr:
            return []
        return [self.baggage[tag] for tag in pnr.baggage_tags if tag in self.baggage]

    def get_rebook_options(self, flight_number: str) -> List[RebookOption]:
        key = flight_number.upper().replace(" ", "")
        return self.rebook_inventory.get(key, [])

    def rebook_pnr(self, pnr_code: str, new_flight_number: str) -> Optional[PNRRecord]:
        pnr = self.get_pnr(pnr_code)
        new_flight = self.get_flight(new_flight_number)
        if pnr and new_flight:
            pnr.flight_number = new_flight.flight_number
            pnr.status = "REBOOKED_CONFIRMED"
            # Update baggage note
            for tag in pnr.baggage_tags:
                if tag in self.baggage:
                    self.baggage[tag].flight_number = new_flight.flight_number
                    self.baggage[tag].notes = f"Rerouted to flight {new_flight.flight_number}."
            return pnr
        return None

    def search_flights_by_route(self, origin: str, destination: str) -> List[FlightInfo]:
        orig = origin.upper().strip()
        dest = destination.upper().strip()
        return [f for f in self.flights.values() if f.origin == orig and f.destination == dest]


# Singleton instance
aviation_db = AviationDatabase()
