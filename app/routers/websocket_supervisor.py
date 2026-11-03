import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.supervisor_manager import supervisor_manager

supervisor_router = APIRouter(tags=["AeroVoice Supervisor WebSocket"])


@supervisor_router.websocket("/ws/supervisor")
async def websocket_supervisor_endpoint(websocket: WebSocket):
    await websocket.accept()
    supervisor_manager.register_supervisor_socket(websocket)

    try:
        # Send initial snapshot of all active sessions
        sessions = supervisor_manager.list_sessions()
        await websocket.send_json({
            "type": "initial_state",
            "sessions": [s.model_dump() for s in sessions],
        })

        while True:
            # Listen for supervisory control events (takeover, message, etc.)
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                action = msg.get("action")

                if action == "ping":
                    await websocket.send_json({"type": "pong"})

                elif action == "takeover":
                    session_id = msg.get("session_id")
                    supervisor_name = msg.get("supervisor_name", "Lead Supervisor")
                    if session_id:
                        supervisor_manager.takeover_call(session_id, supervisor_name)
                        await supervisor_manager.send_to_passenger(session_id, {
                            "type": "supervisor_takeover",
                            "session_id": session_id,
                            "message": f"Supervisor {supervisor_name} has connected to your call.",
                        })
                        await supervisor_manager.broadcast_to_supervisors(
                            "session_taken_over",
                            {"session_id": session_id, "supervisor": supervisor_name},
                        )

                elif action == "send_message":
                    session_id = msg.get("session_id")
                    text = msg.get("text")
                    supervisor_name = msg.get("supervisor_name", "Lead Supervisor")
                    if session_id and text:
                        t_msg = supervisor_manager.add_transcript(
                            session_id=session_id,
                            speaker="supervisor",
                            text=text,
                        )
                        await supervisor_manager.send_to_passenger(session_id, {
                            "type": "supervisor_message",
                            "session_id": session_id,
                            "speaker": supervisor_name,
                            "message": text,
                        })
                        await supervisor_manager.broadcast_to_supervisors(
                            "transcript_added",
                            {
                                "session_id": session_id,
                                "transcript_item": t_msg.model_dump() if t_msg else {},
                            },
                        )

            except Exception:
                continue

    except WebSocketDisconnect:
        supervisor_manager.unregister_supervisor_socket(websocket)
    except Exception:
        supervisor_manager.unregister_supervisor_socket(websocket)
