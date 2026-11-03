# AeroVoice AI ✈️🎙️
### Web-Based Conversational Voice Agent for the Aviation Industry
**CSL 801 Project Phase III — Review II**  
*School of Computing, Indian Institute of Information Technology Una*  
**Prepared by:** Shriyansh Kushwaha (23155), Aman Jha (23305), Sajal Kumar Barnwal (23151)  
**Supervisor:** Ms. Nisha

---

## 🌟 Overview & Implemented Core Modules

AeroVoice AI is a real-time, low-latency conversational voice agent and human escalation platform engineered specifically for commercial airline passenger operations. It eliminates legacy telephony (SIP/PSTN) bottlenecks and conversational dead air by implementing direct browser Web Audio streaming, asynchronous subagent query processing, and an automated multi-factor confidence scoring loop.

### Key Implemented Systems

1. **Real-Time Streaming Gateway & Full-Duplex WebSockets (Section 3.1.2)**
   - Fast, bidirectional streaming over `/ws/voice/{session_id}`.
   - Client barge-in (interruption) detection with instant audio buffer flushing.
   - Synchronized broadcast to the Supervisor Command Center over `/ws/supervisor`.

2. **Aviation Domain Entity Extraction & Strict Parsing (Section 3.1.3)**
   - **6-character alphanumeric PNRs** (e.g., `W7X9K2`, `DL8401`, `BA9921`, `EK4032`).
   - **Flight identifiers** (e.g., `AI101`, `DL402`, `BA178`, `EK505`, `UA890`).
   - **3-letter IATA airport codes** (`DEL`, `JFK`, `LHR`, `BOM`, `DXB`, `LAX`, `SFO`, `ORD`).
   - **Baggage RFID tags** (`BAG-90812`, `BAG-55421`, `BAG-10294`, `BAG-77319`).
   - Speech spacing normalizer to handle STT artifacts (e.g., `"W 7 X 9 K 2"` &rarr; `"W7X9K2"`).

3. **Asynchronous Subagent & Acoustic Latency Masking Engine (Section 3.1.4)**
   - Solves conversational dead air during multi-second database lookups and rebooking calculations.
   - Generates immediate contextual acoustic filler cues (e.g., *"Checking live flight availability between Delhi and New York..."*) within milliseconds.
   - Runs background retrieval coroutines and streams final voice responses with interactive visual cards.

4. **Multi-Factor Confidence Scoring Loop ($C \ge 0.85$) & Distress Detection (Section 3.1.5)**
   - Computes: $$C = 0.40 \cdot \text{STT\_Certainty} + 0.35 \cdot (1 - \text{Intent\_Entropy}) + 0.25 \cdot \text{Sentiment}$$
   - Detects negative emotional valence and distress triggers (*"human"*, *"agent"*, *"stranded"*, *"emergency"*, *"terrible"*).
   - If $C < 0.85$ or distress is detected, immediately triggers the **Human Escalation Protocol**.

5. **Live Supervisor Command Center & One-Click Takeover (Section 3.1.5)**
   - Real-time active calls list with live confidence gauges.
   - Zero-loss context handoff (passenger name, PNR, flight status, live transcript history).
   - One-click supervisor takeover button and direct bidirectional messaging.

6. **Interactive Cockpit Web Interface**
   - Editorial light UI: porcelain ground, a single oxblood accent, Newsreader serif headlines, Inter UI and Space Mono labels.
   - HTML5 Canvas real-time waveform visualizer.
   - Web Speech API microphone input & neural voice playback.
   - Flight status preview cards, Baggage tracking timeline cards, and Rebooking cards.
   - Quick Test Scenario chips for 1-click live testing.

---

## 🚀 How to Run AeroVoice AI

### 1. Prerequisites
- Python 3.10+ (Python 3.12 verified)
- Modern web browser (Chrome, Edge, Firefox, or Safari)

### 2. Install Dependencies
Open your terminal or PowerShell in the project directory:
```bash
pip install -r requirements.txt
```

### 3. Launch the AeroVoice AI Server
Run the application launcher:
```bash
python run.py
```
*Or using uvicorn directly:*
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

You will see:
```text
============================================================
[INFO] AeroVoice AI v1.0.0 starting up...
[GATEWAY] Real-time Voice WebSocket: ws://127.0.0.1:8000/ws/voice/{session_id}
[SUPERVISOR] Supervisor Portal WebSocket: ws://127.0.0.1:8000/ws/supervisor
[UI] Web UI & Dashboard: http://127.0.0.1:8000/
[DOCS] API Documentation: http://127.0.0.1:8000/docs
============================================================
```

### 4. Access the Web Dashboard
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

- **Tab 1: Passenger Terminal**
  - Click the microphone button to speak, or type into the query box.
  - Test quick queries using the clickable chips (e.g. Flight Status, PNR lookup, Baggage track).
  - Test the **Interrupt Agent (Barge-In)** button while speech is playing.
- **Tab 2: Supervisor Command Center**
  - Open in a second browser window or tab.
  - Watch live calls stream in real time.
  - Click **One-Click Takeover** to intervene in any active or escalated session!
- **Tab 3: Aviation Data**
  - Live inspection of flights, PNRs, and baggage telemetry.

---

## 🧪 Running Automated Tests

Run the full pytest suite for unit tests (Entity extraction, confidence engine, subagents, and rebooking):
```bash
python -m pytest -v
```

Run the live WebSocket pipeline integration test (while the server is running):
```bash
python tests/test_ws_live.py
```

---

## 📂 Project Structure

```
AeroVoice AI/
├── app/
│   ├── config.py                 # Configuration settings
│   ├── main.py                   # FastAPI app, static files, and router mounting
│   ├── core/
│   │   ├── entity_extractor.py   # 6-char PNR, flight, IATA, baggage parser
│   │   ├── intent_classifier.py  # Intent distribution & Shannon entropy calculation
│   │   ├── confidence_engine.py  # Multi-factor score (C >= 0.85) & distress detection
│   │   ├── subagent_engine.py    # Async subagent background worker & latency masking
│   │   └── supervisor_manager.py # Live call registry & supervisor takeover manager
│   ├── database/
│   │   └── mock_aviation_db.py   # Flights, PNRs, baggage, and rebooking inventory
│   ├── models/
│   │   └── schemas.py            # Pydantic schemas and event definitions
│   ├── routers/
│   │   ├── api.py                # REST endpoints (/api/flights, /api/pnr, /api/rebook)
│   │   ├── websocket_voice.py    # Full-duplex voice WebSocket (/ws/voice/{session_id})
│   │   └── websocket_supervisor.py # Supervisor portal WebSocket (/ws/supervisor)
│   └── static/
│       ├── index.html            # Web cockpit terminal & supervisor UI
│       ├── css/styles.css        # Editorial light theme (porcelain + oxblood)
│       └── js/app.js             # Web Audio visualizer, Web Speech, & WS logic
├── tests/
│   ├── test_aviation_engine.py   # Pytest suite for core engine logic
│   └── test_ws_live.py           # Live end-to-end WebSocket pipeline test
├── requirements.txt              # Python dependencies
├── run.py                        # Server execution entrypoint
└── README.md                     # Documentation & usage manual
```
