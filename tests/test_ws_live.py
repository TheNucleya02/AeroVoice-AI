import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
import websockets


async def run_live_pipeline():
    uri = "ws://127.0.0.1:8000/ws/voice/TEST-LIVE-01"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as ws:
        # Step 1: Connect
        init = json.loads(await ws.recv())
        print("1. [WS CONNECTED]:", init["type"], "->", init["message"])

        # Step 2: Inquire Flight Status
        print("\nSending query: 'What is the status of flight DL402?'")
        await ws.send(
            json.dumps(
                {
                    "type": "user_speech",
                    "text": "What is the status of flight DL402?",
                    "stt_confidence": 0.98,
                }
            )
        )

        telemetry = json.loads(await ws.recv())
        print(
            "2. [TELEMETRY]:",
            "Intent:",
            telemetry["intent"],
            "| Composite Confidence:",
            telemetry["confidence"]["composite_confidence"],
            flush=True,
        )

        filler = json.loads(await ws.recv())
        print("3. [LATENCY MASKING FILLER]:", filler["text"], flush=True)

        agent_res = json.loads(await ws.recv())
        print("4. [SUBAGENT COMPLETED]: Card Type:", agent_res.get("card_type"), flush=True)
        print("   Speech Response:", agent_res["text"], flush=True)

        # Step 3: Trigger Distress & Escalation
        print("\nSending distress query: 'This is terrible! I need a supervisor immediately!'", flush=True)
        await ws.send(
            json.dumps(
                {
                    "type": "user_speech",
                    "text": "This is terrible! I need a supervisor immediately!",
                    "stt_confidence": 0.92,
                }
            )
        )

        distress_telemetry = json.loads(await ws.recv())
        print(
            "5. [DISTRESS TELEMETRY]: Escalation Needed:",
            distress_telemetry["confidence"]["is_escalation_needed"],
            "| Reason:",
            distress_telemetry["confidence"]["distress_reason"],
            flush=True,
        )

        escalation_alert = json.loads(await ws.recv())
        print("6. [ESCALATION PROTOCOL TRIGGERED]:", escalation_alert["type"], flush=True)
        print("   Alert message to passenger:", escalation_alert["text"], flush=True)

    print("\n>>> ALL TEST PIPELINE CHECKS COMPLETED SUCCESSFULLY! <<<", flush=True)


if __name__ == "__main__":
    asyncio.run(run_live_pipeline())
