import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any
from fastapi import WebSocket
from app.models.schemas import (
    CallSessionState,
    AgentSessionStatus,
    ConfidenceScore,
    TranscriptMessage,
)


class SupervisorManager:
    """
    Manages live passenger call sessions, supervisor WebSocket connections,
    real-time event broadcasting, and zero-context-loss human takeover.
    """

    def __init__(self):
        self.active_sessions: Dict[str, CallSessionState] = {}
        self.passenger_sockets: Dict[str, WebSocket] = {}
        self.supervisor_sockets: Set[WebSocket] = set()

    def register_session(
        self, session_id: str, websocket: Optional[WebSocket] = None
    ) -> CallSessionState:
        now_str = datetime.now(timezone.utc).isoformat()
        session = CallSessionState(
            session_id=session_id,
            status=AgentSessionStatus.CONNECTED,
            created_at=now_str,
            updated_at=now_str,
        )
        self.active_sessions[session_id] = session
        if websocket:
            self.passenger_sockets[session_id] = websocket
        return session

    def register_passenger_socket(self, session_id: str, websocket: WebSocket):
        self.passenger_sockets[session_id] = websocket

    def unregister_passenger(self, session_id: str):
        if session_id in self.passenger_sockets:
            del self.passenger_sockets[session_id]
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = AgentSessionStatus.DISCONNECTED

    def register_supervisor_socket(self, websocket: WebSocket):
        self.supervisor_sockets.add(websocket)

    def unregister_supervisor_socket(self, websocket: WebSocket):
        self.supervisor_sockets.discard(websocket)

    def get_session(self, session_id: str) -> Optional[CallSessionState]:
        return self.active_sessions.get(session_id)

    def list_sessions(self) -> List[CallSessionState]:
        return list(self.active_sessions.values())

    def add_transcript(
        self,
        session_id: str,
        speaker: str,
        text: str,
        confidence: Optional[float] = None,
        is_filler: bool = False,
        card_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[TranscriptMessage]:
        session = self.get_session(session_id)
        if not session:
            return None

        msg = TranscriptMessage(
            id=str(uuid.uuid4())[:8],
            speaker=speaker,
            text=text,
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            confidence=confidence,
            is_filler=is_filler,
            card_data=card_data,
        )
        session.transcript.append(msg)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return msg

    def record_confidence(
        self, session_id: str, confidence: ConfidenceScore
    ) -> Optional[CallSessionState]:
        session = self.get_session(session_id)
        if not session:
            return None

        session.latest_confidence = confidence
        session.confidence_history.append(confidence)
        session.updated_at = datetime.now(timezone.utc).isoformat()

        if confidence.is_escalation_needed and not session.escalated_to_supervisor:
            session.escalated_to_supervisor = True
            session.status = AgentSessionStatus.ESCALATED

        return session

    def takeover_call(self, session_id: str, supervisor_name: str = "Lead Supervisor") -> bool:
        session = self.get_session(session_id)
        if not session:
            return False

        session.status = AgentSessionStatus.SUPERVISOR_ACTIVE
        session.supervisor_notes = f"Taken over by {supervisor_name}."
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    async def broadcast_to_supervisors(self, event_type: str, data: Dict[str, Any]):
        """
        Broadcasts live operational updates to all connected supervisor dashboards.
        """
        payload = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        dead_sockets = set()
        for ws in self.supervisor_sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead_sockets.add(ws)

        for ws in dead_sockets:
            self.supervisor_sockets.discard(ws)

    async def send_to_passenger(self, session_id: str, payload: Dict[str, Any]):
        ws = self.passenger_sockets.get(session_id)
        if ws:
            try:
                await ws.send_json(payload)
            except Exception:
                pass


supervisor_manager = SupervisorManager()
