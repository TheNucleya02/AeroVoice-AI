import math
from typing import Dict, List, Optional, Tuple
from app.models.schemas import ConfidenceScore


class ConfidenceEngine:
    """
    Automated Multi-Factor Confidence Engine (Section 3.1.5).
    Computes a composite score based on:
      1. STT Certainty (acoustic model word confidence)
      2. Intent Clarity (1 - Intent Entropy)
      3. Sentiment & Distress Rating (emotional valence & distress markers)

    Escalates to Human Supervisor if Composite Confidence < 0.85 or distress detected.
    """

    ESCALATION_THRESHOLD = 0.85

    DISTRESS_KEYWORDS = [
        "human", "agent", "supervisor", "representative", "person",
        "operator", "manager", "furious", "terrible", "worst",
        "unacceptable", "stranded", "emergency", "lawyer", "ridiculous",
        "horrible", "frustrated", "help me now", "disaster", "stolen",
        "missed my flight", "stuck at airport"
    ]

    NEGATIVE_SENTIMENT_WORDS = [
        "angry", "annoyed", "bad", "broken", "delayed", "lost",
        "ruined", "hate", "upset", "wrong", "mess", "problem",
        "fail", "refuse", "cheat", "scam"
    ]

    POSITIVE_SENTIMENT_WORDS = [
        "thank", "thanks", "great", "good", "perfect", "appreciate",
        "helpful", "excellent", "wonderful", "awesome", "clear"
    ]

    def __init__(
        self,
        weight_stt: float = 0.40,
        weight_intent: float = 0.35,
        weight_sentiment: float = 0.25,
    ):
        self.w_stt = weight_stt
        self.w_intent = weight_intent
        self.w_sentiment = weight_sentiment

    def calculate_intent_entropy(self, intent_probabilities: Dict[str, float]) -> float:
        """
        Calculates normalized Shannon entropy of the intent distribution.
        Normalized to [0.0, 1.0], where 0 means 100% confidence in one intent,
        and 1.0 means complete ambiguity/uniform distribution.
        """
        if not intent_probabilities:
            return 0.5

        probs = [p for p in intent_probabilities.values() if p > 0.0]
        if len(probs) <= 1:
            return 0.0

        n = len(probs)
        entropy = -sum(p * math.log(p) for p in probs)
        max_entropy = math.log(n)
        return min(1.0, max(0.0, entropy / max_entropy if max_entropy > 0 else 0.0))

    def evaluate_sentiment(self, text: str) -> Tuple[float, bool, Optional[str]]:
        """
        Evaluates sentiment score in range [0.0, 1.0].
        0.0 = severe negative / distress
        0.5 = neutral
        1.0 = highly positive / cooperative
        Also detects explicit distress triggers and requests for a human supervisor.
        """
        lower = text.lower()
        distress_found: List[str] = []

        for kw in self.DISTRESS_KEYWORDS:
            if kw in lower:
                distress_found.append(kw)

        neg_count = sum(1 for w in self.NEGATIVE_SENTIMENT_WORDS if w in lower)
        pos_count = sum(1 for w in self.POSITIVE_SENTIMENT_WORDS if w in lower)

        # Baseline neutral score
        sentiment = 0.88

        if distress_found:
            sentiment -= 0.50 + (0.1 * min(3, len(distress_found)))
        sentiment -= neg_count * 0.12
        sentiment += pos_count * 0.10

        sentiment = max(0.05, min(1.0, sentiment))

        is_distressed = len(distress_found) > 0 or sentiment < 0.40
        reason = None
        if distress_found:
            reason = f"Distress / Supervisor request keywords detected: {', '.join(distress_found[:3])}"
        elif sentiment < 0.40:
            reason = "High negative sentiment and conversational distress detected."

        return sentiment, is_distressed, reason

    def compute_confidence(
        self,
        transcript_text: str,
        stt_certainty: float = 0.95,
        intent_probabilities: Optional[Dict[str, float]] = None,
    ) -> ConfidenceScore:
        """
        Computes composite confidence score for the current conversational turn.
        """
        if intent_probabilities is None:
            intent_probabilities = {"PRIMARY": 0.95, "SECONDARY": 0.05}

        entropy = self.calculate_intent_entropy(intent_probabilities)
        sentiment, is_distressed, distress_reason = self.evaluate_sentiment(transcript_text)

        # Weighted calculation
        composite = (
            (self.w_stt * stt_certainty)
            + (self.w_intent * (1.0 - entropy))
            + (self.w_sentiment * sentiment)
        )

        # Cap between 0 and 1
        composite = round(max(0.0, min(1.0, composite)), 3)

        # If explicit distress or composite < 0.85, flag escalation
        needs_escalation = (composite < self.ESCALATION_THRESHOLD) or is_distressed

        return ConfidenceScore(
            stt_certainty=round(stt_certainty, 3),
            intent_entropy=round(entropy, 3),
            sentiment_score=round(sentiment, 3),
            composite_confidence=composite,
            is_distressed=is_distressed,
            distress_reason=distress_reason,
            is_escalation_needed=needs_escalation,
        )


confidence_engine = ConfidenceEngine()
