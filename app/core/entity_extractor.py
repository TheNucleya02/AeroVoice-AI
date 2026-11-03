import re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ExtractedAviationEntities(BaseModel):
    pnr_codes: List[str] = Field(default_factory=list)
    flight_numbers: List[str] = Field(default_factory=list)
    iata_airports: List[str] = Field(default_factory=list)
    baggage_tags: List[str] = Field(default_factory=list)
    raw_entities: Dict[str, Any] = Field(default_factory=dict)


class AviationEntityExtractor:
    """
    Domain Entity Extraction for Aviation Speech.
    Handles strict 6-character PNR extraction, flight identifiers,
    IATA airport codes, and phonetic spacing artifacts from STT models.
    """

    IATA_CODES = {
        "DEL": "Indira Gandhi International, Delhi",
        "BOM": "Chhatrapati Shivaji Maharaj International, Mumbai",
        "JFK": "John F. Kennedy International, New York",
        "LHR": "Heathrow Airport, London",
        "DXB": "Dubai International Airport",
        "LAX": "Los Angeles International",
        "SFO": "San Francisco International",
        "ORD": "O'Hare International, Chicago",
        "CDG": "Charles de Gaulle, Paris",
        "SIN": "Singapore Changi Airport",
        "FRA": "Frankfurt Airport",
        "HND": "Tokyo Haneda Airport",
    }

    AIRLINE_PREFIXES = ["AI", "DL", "BA", "EK", "UA", "AA", "QF", "LH", "AF", "SQ", "VS", "6E", "SG"]

    # Common English words that happen to be 6 letters and should not be falsely tagged as PNRs
    COMMON_6_LETTER_WORDS = {
        "FLIGHT", "PLEASE", "TRAVEL", "TICKET", "STATUS", "PERSON", "AIRWAY",
        "ARRIVE", "DEPART", "CANCEL", "UPDATE", "NUMBER", "CHANGE", "ROUTER",
        "SYSTEM", "RECORD", "ONLINE", "AGENTS", "DIRECT", "REPORT", "TERMIN"
    }

    def _normalize_speech_spacing(self, text: str) -> str:
        """
        Normalizes single letter/digit spaced strings often produced by STT engines.
        e.g., 'W 7 X 9 K 2' -> 'W7X9K2', 'A I 1 0 1' -> 'AI101'
        """
        # Collapse single characters separated by spaces when 3 or more appear sequentially
        def collapse_match(match):
            return match.group(0).replace(" ", "")

        pattern = r"\b(?:[A-Za-z0-9]\s+){2,}[A-Za-z0-9]\b"
        return re.sub(pattern, collapse_match, text)

    def extract(self, text: str) -> ExtractedAviationEntities:
        cleaned_text = self._normalize_speech_spacing(text.upper())

        pnr_matches: List[str] = []
        flight_matches: List[str] = []
        iata_matches: List[str] = []
        baggage_matches: List[str] = []

        # 1. Extract Flight Numbers (e.g. AI101, DL 402, BA178, EK505)
        # Prefix based
        prefix_pattern = r"\b(" + "|".join(self.AIRLINE_PREFIXES) + r")\s?(\d{1,4})\b"
        for match in re.finditer(prefix_pattern, cleaned_text):
            flight_code = f"{match.group(1)}{match.group(2)}"
            if flight_code not in flight_matches:
                flight_matches.append(flight_code)

        # Generic flight regex fallback: 2-3 letters followed by 2-4 digits (e.g., FLIGHT 302 or XY99)
        generic_flight_pattern = r"\b([A-Z]{2,3})\s?(\d{2,4})\b"
        for match in re.finditer(generic_flight_pattern, cleaned_text):
            code = f"{match.group(1)}{match.group(2)}"
            if code not in flight_matches and match.group(1) not in ["THE", "FOR", "AND"]:
                flight_matches.append(code)

        # 2. Extract 6-character PNRs
        # PNR rule: 6 alphanumeric characters containing at least one digit or one letter,
        # but not a generic 6-letter English word.
        # Often preceded by 'PNR', 'BOOKING', 'CODE', 'REFERENCE'
        pnr_pattern = r"\b([A-Z0-9]{6})\b"
        for candidate in re.findall(pnr_pattern, cleaned_text):
            if candidate in self.COMMON_6_LETTER_WORDS:
                continue
            # If candidate matches an extracted flight, skip
            if candidate in flight_matches:
                continue
            # Needs to have at least one letter and at least one digit, or be in known formats
            has_letter = any(c.isalpha() for c in candidate)
            has_digit = any(c.isdigit() for c in candidate)
            if has_letter and (has_digit or "PNR" in cleaned_text or "BOOKING" in cleaned_text):
                if candidate not in pnr_matches:
                    pnr_matches.append(candidate)

        # 3. Extract Baggage Tags (e.g., BAG-90812, BAG90812)
        baggage_pattern = r"\b(?:BAG[- ]?)?(\d{5,8})\b"
        for match in re.finditer(baggage_pattern, cleaned_text):
            tag = f"BAG-{match.group(1)}"
            # Don't confuse with flight numbers
            if not any(f.endswith(match.group(1)) for f in flight_matches):
                if tag not in baggage_matches and ("BAG" in cleaned_text or "LUGGAGE" in cleaned_text):
                    baggage_matches.append(tag)

        # Explicit BAG-XXXXX format
        explicit_bag_pattern = r"\bBAG-([A-Z0-9]{5,8})\b"
        for match in re.finditer(explicit_bag_pattern, cleaned_text):
            tag = f"BAG-{match.group(1)}"
            if tag not in baggage_matches:
                baggage_matches.append(tag)

        # 4. Extract IATA Airport Codes
        words = re.findall(r"\b[A-Z]{3}\b", cleaned_text)
        for w in words:
            if w in self.IATA_CODES and w not in ["FOR", "THE", "AND", "NOT", "YES", "NOW"]:
                if w not in iata_matches:
                    iata_matches.append(w)

        return ExtractedAviationEntities(
            pnr_codes=pnr_matches,
            flight_numbers=flight_matches,
            iata_airports=iata_matches,
            baggage_tags=baggage_matches,
            raw_entities={
                "normalized_text": cleaned_text,
                "detected_airports": [self.IATA_CODES[code] for code in iata_matches],
            },
        )


extracted_entities = AviationEntityExtractor()
