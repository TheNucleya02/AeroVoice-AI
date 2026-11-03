import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.schemas import AgentSessionStatus
from app.core.entity_extractor import extracted_entities
from app.core.intent_classifier import intent_classifier, AviationIntent
from app.core.confidence_engine import confidence_engine
from app.core.subagent_engine import subagent_engine
from app.core.supervisor_manager import supervisor_manager
from app.database.mock_aviation_db import aviation_db

voice_router = APIRouter(tags=["AeroVoice Voice WebSocket"])


@voice_router.websocket("/ws/voice/{session_id}")
async def websocket_voice_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = supervisor_manager.register_session(session_id, websocket)

    # Broadcast session creation to supervisors
    await supervisor_manager.broadcast_to_supervisors(
        "session_created",
        {"session_id": session_id, "status": session.status.value},
    )

    # Send initial welcome message
    welcome_text = (
        "Welcome to AeroVoice AI. How can I assist you with your flight, "
        "booking reference (PNR), or baggage tracking today?"
    )
    supervisor_manager.add_transcript(session_id, "agent", welcome_text)

    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "message": welcome_text,
        "status": session.status.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    current_subagent_task: Optional[asyncio.Task] = None

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except Exception:
                continue

            msg_type = data.get("type", "")

            # 1. BARGE-IN INTERRUPTION HANDLER
            if msg_type == "barge_in":
                if current_subagent_task and not current_subagent_task.done():
                    current_subagent_task.cancel()
                session.status = AgentSessionStatus.LISTENING
                await websocket.send_json({
                    "type": "barge_in_flushed",
                    "session_id": session_id,
                    "message": "Audio output buffer flushed. Listening to passenger...",
                })
                continue

            # 2. PING / KEEP-ALIVE
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # 3. USER SPEECH / TEXT INPUT
            if msg_type in ["user_speech", "text_input"]:
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue

                stt_certainty = float(data.get("stt_confidence", 0.95))

                # If Human Supervisor has already taken over call, route directly to supervisor
                if session.status == AgentSessionStatus.SUPERVISOR_ACTIVE:
                    user_msg = supervisor_manager.add_transcript(
                        session_id=session_id,
                        speaker="user",
                        text=user_text,
                        confidence=stt_certainty,
                    )
                    await supervisor_manager.broadcast_to_supervisors(
                        "transcript_added",
                        {"session_id": session_id, "transcript_item": user_msg.model_dump() if user_msg else {}},
                    )
                    continue

                # Step A: Domain Entity Extraction
                entities = extracted_entities.extract(user_text)

                # Persist extracted entities to session
                if entities.pnr_codes:
                    session.pnr_code = entities.pnr_codes[0]
                    # Attempt to resolve passenger name
                    pnr_rec = aviation_db.get_pnr(entities.pnr_codes[0])
                    if pnr_rec:
                        session.passenger_name = pnr_rec.passenger_name
                        session.active_flight_number = pnr_rec.flight_number

                if entities.flight_numbers:
                    session.active_flight_number = entities.flight_numbers[0]

                # Step B: Intent Classification & Entropy Distribution
                intent, intent_probs = intent_classifier.classify(user_text, entities)

                # Step C: Multi-Factor Confidence Scoring Loop
                confidence = confidence_engine.compute_confidence(
                    transcript_text=user_text,
                    stt_certainty=stt_certainty,
                    intent_probabilities=intent_probs,
                )
                supervisor_manager.record_confidence(session_id, confidence)

                # Record user message in transcript
                user_msg = supervisor_manager.add_transcript(
                    session_id=session_id,
                    speaker="user",
                    text=user_text,
                    confidence=confidence.composite_confidence,
                )

                # Broadcast transcript & confidence to supervisors
                await supervisor_manager.broadcast_to_supervisors(
                    "transcript_added",
                    {
                        "session_id": session_id,
                        "transcript_item": user_msg.model_dump() if user_msg else {},
                        "confidence": confidence.model_dump(),
                    },
                )

                # Send confidence telemetry to client
                await websocket.send_json({
                    "type": "confidence_telemetry",
                    "session_id": session_id,
                    "confidence": confidence.model_dump(),
                    "entities": entities.model_dump(),
                    "intent": intent,
                })

                # Step D: Human Escalation Check (Threshold C < 0.85 or distress)
                if confidence.is_escalation_needed:
                    session.status = AgentSessionStatus.ESCALATED
                    escalation_filler = (
                        "I understand your concern. I am immediately connecting you with an airline operations "
                        "supervisor while preserving your entire booking and ticket context."
                    )
                    esc_msg = supervisor_manager.add_transcript(
                        session_id=session_id,
                        speaker="agent",
                        text=escalation_filler,
                    )

                    await websocket.send_json({
                        "type": "escalation_alert",
                        "session_id": session_id,
                        "text": escalation_filler,
                        "reason": confidence.distress_reason or "Confidence score fell below 0.85 threshold.",
                        "confidence": confidence.model_dump(),
                    })

                    # High priority supervisor notification
                    await supervisor_manager.broadcast_to_supervisors(
                        "escalation_triggered",
                        {
                            "session_id": session_id,
                            "reason": confidence.distress_reason,
                            "confidence": confidence.model_dump(),
                            "passenger_name": session.passenger_name,
                            "pnr": session.pnr_code,
                            "flight": session.active_flight_number,
                            "transcript": [t.model_dump() for t in session.transcript],
                        },
                    )
                    continue

                # Step E: Acoustic Latency Masking Cue (Section 3.1.4)
                # Eliminate dead air during background database query
                session.status = AgentSessionStatus.MASKING
                filler_cue = subagent_engine.generate_filler_cue(
                    intent=intent,
                    entities=entities,
                    session_pnr=session.pnr_code,
                    session_flight=session.active_flight_number,
                )

                filler_msg = supervisor_manager.add_transcript(
                    session_id=session_id,
                    speaker="filler",
                    text=filler_cue,
                    is_filler=True,
                )

                # Send filler immediately to client to play
                await websocket.send_json({
                    "type": "filler_cue",
                    "session_id": session_id,
                    "text": filler_cue,
                    "is_filler": True,
                })

                await supervisor_manager.broadcast_to_supervisors(
                    "transcript_added",
                    {"session_id": session_id, "transcript_item": filler_msg.model_dump() if filler_msg else {}},
                )

                # Step F: Run Asynchronous Subagent Worker
                session.status = AgentSessionStatus.PROCESSING
                final_speech, card_type, card_data = await subagent_engine.run_async_subagent_task(
                    intent=intent,
                    entities=entities,
                    session_pnr=session.pnr_code,
                    session_flight=session.active_flight_number,
                    simulate_computation_delay=1.2,
                )

                # Step G: Deliver Final Agent Response & Visual Aviation Cards
                session.status = AgentSessionStatus.SPEAKING
                agent_msg = supervisor_manager.add_transcript(
                    session_id=session_id,
                    speaker="agent",
                    text=final_speech,
                    card_data=card_data,
                )

                await websocket.send_json({
                    "type": "agent_response",
                    "session_id": session_id,
                    "text": final_speech,
                    "card_type": card_type,
                    "card_data": card_data,
                })

                await supervisor_manager.broadcast_to_supervisors(
                    "transcript_added",
                    {
                        "session_id": session_id,
                        "transcript_item": agent_msg.model_dump() if agent_msg else {},
                        "card_data": card_data,
                    },
                )

                session.status = AgentSessionStatus.LISTENING

    except WebSocketDisconnect:
        supervisor_manager.unregister_passenger(session_id)
        await supervisor_manager.broadcast_to_supervisors(
            "session_disconnected",
            {"session_id": session_id},
        )
    except Exception as e:
        supervisor_manager.unregister_passenger(session_id)
        await supervisor_manager.broadcast_to_supervisors(
            "session_error",
            {"session_id": session_id, "error": str(e)},
        )
