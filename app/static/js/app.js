/**
 * AeroVoice AI — Client-Side Audio Pipeline & WebSocket Controller
 * Implements: Full-duplex WebSocket, Audio Visualizer, Client VAD/Barge-in,
 * Web Speech Recognition/Synthesis, Latency Masking Cues, and Live Supervisor Loop.
 */

// Global State
let sessionId = "AV-" + Math.floor(100000 + Math.random() * 900000);
let voiceSocket = null;
let supervisorSocket = null;
let isRecording = false;
let speechRecognizer = null;
let audioContext = null;
let analyser = null;
let visualizerAnimationId = null;
let currentSupervisorFocusedSession = null;

// Speech Synthesis Queue
const synth = window.speechSynthesis;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("display-session-id").innerText = sessionId;
    initVoiceWebSocket();
    initSupervisorWebSocket();
    initVisualizerCanvas();
    initSpeechRecognition();
    refreshDatabaseView();
});

/* =========================================================================
   1. REAL-TIME VOICE WEBSOCKET GATEWAY (Section 3.1.2)
   ========================================================================= */

function initVoiceWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/voice/${sessionId}`;

    updateConnectionStatus(false, "Connecting to WebSocket Gateway...");

    voiceSocket = new WebSocket(wsUrl);

    voiceSocket.onopen = () => {
        updateConnectionStatus(true, "Sub-800ms Stream Connected");
        // Keep-alive ping
        setInterval(() => {
            if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
                voiceSocket.send(JSON.stringify({ type: "ping" }));
            }
        }, 15000);
    };

    voiceSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleVoiceEvent(data);
        } catch (e) {
            console.error("Malformed voice WS packet:", e);
        }
    };

    voiceSocket.onclose = () => {
        updateConnectionStatus(false, "Disconnected. Reconnecting...");
        setTimeout(initVoiceWebSocket, 3000);
    };

    voiceSocket.onerror = (err) => {
        console.error("Voice WS error:", err);
    };
}

function updateConnectionStatus(connected, text) {
    const indicator = document.getElementById("ws-indicator");
    const statusText = document.getElementById("ws-status-text");
    if (indicator && statusText) {
        indicator.className = `connection-indicator ${connected ? "connected" : "disconnected"}`;
        statusText.innerText = text;
    }
}

function handleVoiceEvent(data) {
    const type = data.type;

    if (type === "connected") {
        appendMessage("agent", data.message, false);
        speakText(data.message);
        setAgentBadge("LISTENING", "badge-idle");
    } 
    else if (type === "filler_cue") {
        // Acoustic Latency Masking Filler (Section 3.1.4)
        appendMessage("filler", data.text, true);
        setAgentBadge("MASKING (SUBAGENT RUNNING)", "badge-masking");
        speakText(data.text);
    } 
    else if (type === "agent_response") {
        // Final Response & Visual Aviation Cards
        setAgentBadge("SPEAKING", "badge-speaking");
        appendMessage("agent", data.text, false);
        speakText(data.text, () => {
            setAgentBadge("LISTENING", "badge-idle");
        });

        if (data.card_type && data.card_data) {
            renderAviationCard(data.card_type, data.card_data);
        }
    } 
    else if (type === "confidence_telemetry") {
        updateConfidenceHUD(data.confidence);
    } 
    else if (type === "escalation_alert") {
        setAgentBadge("ESCALATED TO SUPERVISOR", "badge-escalated");
        appendMessage("agent", `⚠️ ${data.text}`, false);
        speakText(data.text);
        showSupervisorAlertPill();
    } 
    else if (type === "supervisor_takeover") {
        setAgentBadge("SUPERVISOR LIVE", "badge-supervisor");
        appendMessage("supervisor", `👨‍✈️ ${data.message}`, false);
        speakText(data.message);
    } 
    else if (type === "supervisor_message") {
        appendMessage("supervisor", `👨‍✈️ [${data.speaker}]: ${data.message}`, false);
        speakText(data.message);
    } 
    else if (type === "barge_in_flushed") {
        setAgentBadge("LISTENING (BARGED-IN)", "badge-idle");
        stopSpeaking();
    }
}

/* =========================================================================
   2. CLIENT AUDIO CAPTURE & BARGE-IN (Section 3.1.1)
   ========================================================================= */

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        document.getElementById("mic-status-label").innerText = "Web Speech API not supported in this browser. Use text input.";
        return;
    }

    speechRecognizer = new SpeechRecognition();
    speechRecognizer.continuous = true;
    speechRecognizer.interimResults = true;
    speechRecognizer.lang = "en-US";

    speechRecognizer.onstart = () => {
        isRecording = true;
        document.getElementById("mic-toggle-btn").classList.add("recording");
        document.getElementById("mic-status-label").innerText = "Listening... (Speak flight, PNR, or baggage query)";
        startVisualizer();
    };

    speechRecognizer.onresult = (event) => {
        let interimTranscript = "";
        let finalTranscript = "";

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            const transcript = event.results[i][0].transcript;
            const confidence = event.results[i][0].confidence || 0.95;

            if (event.results[i].isFinal) {
                finalTranscript += transcript;
                sendSpeechToServer(finalTranscript, confidence);
            } else {
                interimTranscript += transcript;
                // Client-side VAD Barge-In: If user starts speaking while agent is speaking, flush audio!
                if (synth.speaking) {
                    triggerBargeIn();
                }
            }
        }
    };

    speechRecognizer.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        if (event.error !== "no-speech") {
            stopRecording();
        }
    };

    speechRecognizer.onend = () => {
        if (isRecording) {
            // Restart if continuous mode
            try { speechRecognizer.start(); } catch(e) {}
        } else {
            stopRecording();
        }
    };
}

function toggleMicrophone() {
    if (!speechRecognizer) {
        alert("Speech Recognition is not available in this browser. You can type queries directly in the chat box or use Quick Test Queries!");
        return;
    }

    if (isRecording) {
        stopRecording();
    } else {
        // Stop any current agent speech on mic click
        triggerBargeIn();
        try {
            speechRecognizer.start();
        } catch (e) {
            console.error("Error starting speech recognizer:", e);
        }
    }
}

function stopRecording() {
    isRecording = false;
    document.getElementById("mic-toggle-btn").classList.remove("recording");
    document.getElementById("mic-status-label").innerText = "Click microphone or push to talk";
    if (speechRecognizer) {
        try { speechRecognizer.stop(); } catch(e) {}
    }
    stopVisualizer();
}

function sendSpeechToServer(text, confidence = 0.95) {
    if (!text.trim() || !voiceSocket || voiceSocket.readyState !== WebSocket.OPEN) return;

    appendMessage("user", text, false);

    voiceSocket.send(JSON.stringify({
        type: "user_speech",
        text: text,
        stt_confidence: confidence
    }));
}

function triggerBargeIn() {
    stopSpeaking();
    if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
        voiceSocket.send(JSON.stringify({
            type: "barge_in"
        }));
    }
}

function speakText(text, onEndCallback) {
    if (!synth) return;
    synth.cancel(); // Flush previous speech

    const cleanText = text.replace(/<[^>]*>/g, "").replace(/👨‍✈️|✈️|🎫|🧳|⚠️/g, "");
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    // Pick a natural voice if available
    const voices = synth.getVoices();
    const englishVoice = voices.find(v => v.lang.includes("en") && (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Samantha")));
    if (englishVoice) {
        utterance.voice = englishVoice;
    }

    utterance.onend = () => {
        if (onEndCallback) onEndCallback();
    };

    synth.speak(utterance);
}

function stopSpeaking() {
    if (synth) {
        synth.cancel();
    }
}

/* =========================================================================
   3. AUDIO VISUALIZER (HTML5 Canvas)
   ========================================================================= */

function initVisualizerCanvas() {
    const canvas = document.getElementById("waveform-canvas");
    const ctx = canvas.getContext("2d");
    drawIdleWaveform(ctx, canvas.width, canvas.height);
}

function drawIdleWaveform(ctx, width, height) {
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = "rgba(6, 182, 212, 0.3)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
}

function startVisualizer() {
    const canvas = document.getElementById("waveform-canvas");
    const ctx = canvas.getContext("2d");

    let step = 0;
    function animate() {
        step += 0.08;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const bars = 36;
        const barWidth = canvas.width / bars - 3;
        const centerY = canvas.height / 2;

        for (let i = 0; i < bars; i++) {
            const freq = Math.sin(step + i * 0.4) * 0.5 + 0.5;
            const barHeight = Math.max(4, freq * (canvas.height * 0.7));

            const gradient = ctx.createLinearGradient(0, centerY - barHeight/2, 0, centerY + barHeight/2);
            gradient.addColorStop(0, "#06b6d4");
            gradient.addColorStop(0.5, "#3b82f6");
            gradient.addColorStop(1, "#10b981");

            ctx.fillStyle = gradient;
            ctx.fillRect(i * (barWidth + 3), centerY - barHeight / 2, barWidth, barHeight);
        }

        visualizerAnimationId = requestAnimationFrame(animate);
    }
    animate();
}

function stopVisualizer() {
    if (visualizerAnimationId) {
        cancelAnimationFrame(visualizerAnimationId);
    }
    const canvas = document.getElementById("waveform-canvas");
    const ctx = canvas.getContext("2d");
    drawIdleWaveform(ctx, canvas.width, canvas.height);
}

/* =========================================================================
   4. UI TRANSCRIPT & HUD RENDERING
   ========================================================================= */

function appendMessage(speaker, text, isFiller = false) {
    const container = document.getElementById("transcript-feed-container");
    if (!container) return;

    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-msg ${speaker}`;

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    let speakerLabel = speaker.toUpperCase();
    if (speaker === "filler") speakerLabel = "LATENCY MASKING CUE";
    if (speaker === "supervisor") speakerLabel = "AIRLINE SUPERVISOR";

    let fillerTagHtml = isFiller ? '<span class="filler-badge-tag">LATENCY MASK</span>' : '';

    msgDiv.innerHTML = `
        <div class="msg-meta">
            <span>${speakerLabel}</span>
            ${fillerTagHtml}
            <span>• ${now}</span>
        </div>
        <div class="msg-bubble">${text}</div>
    `;

    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

function setAgentBadge(text, className) {
    const badge = document.getElementById("agent-state-badge");
    if (badge) {
        badge.innerText = text;
        badge.className = `agent-badge ${className}`;
    }
}

function updateConfidenceHUD(confidence) {
    if (!confidence) return;

    document.getElementById("composite-score-text").innerText = confidence.composite_confidence.toFixed(2);
    document.getElementById("composite-progress-bar").style.width = `${confidence.composite_confidence * 100}%`;

    document.getElementById("metric-stt-val").innerText = confidence.stt_certainty.toFixed(2);
    document.getElementById("metric-intent-val").innerText = (1.0 - confidence.intent_entropy).toFixed(2);
    document.getElementById("metric-sentiment-val").innerText = confidence.sentiment_score.toFixed(2);

    const escEl = document.getElementById("metric-escalation-val");
    if (confidence.is_escalation_needed) {
        escEl.innerText = "ESCALATION TRIGGERED";
        escEl.className = "metric-val status-alert";
    } else {
        escEl.innerText = "NOMINAL (PASS)";
        escEl.className = "metric-val status-normal";
    }
}

/* =========================================================================
   5. INTERACTIVE AVIATION CARDS (Flight, Baggage, Rebooking)
   ========================================================================= */

function renderAviationCard(cardType, data) {
    const slot = document.getElementById("aviation-card-slot");
    slot.innerHTML = "";
    slot.style.display = "block";

    if (cardType === "flight_card") {
        slot.innerHTML = `
            <div class="flight-preview-card">
                <div class="card-top">
                    <div class="card-title-group">
                        <span class="airline-tag">${data.airline} ${data.flight_number}</span>
                    </div>
                    <span class="status-badge ${data.status}">${data.status}</span>
                </div>
                <div class="route-display">
                    <div class="airport-block">
                        <span class="airport-code">${data.origin}</span>
                        <span class="airport-name">${data.origin_name}</span>
                    </div>
                    <div class="route-arrow">
                        <span>✈️</span>
                        <small>${data.aircraft_type}</small>
                    </div>
                    <div class="airport-block" style="text-align: right;">
                        <span class="airport-code">${data.destination}</span>
                        <span class="airport-name">${data.destination_name}</span>
                    </div>
                </div>
                <div class="card-details-grid">
                    <div class="detail-item">
                        <span class="detail-lbl">Scheduled Dep</span>
                        <span class="detail-val">${data.scheduled_departure.split(" ")[1]}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-lbl">Estimated Dep</span>
                        <span class="detail-val" style="color: ${data.status === 'DELAYED' ? '#f59e0b' : '#fff'}">${data.estimated_departure.split(" ")[1] || data.estimated_departure}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-lbl">Terminal</span>
                        <span class="detail-val">${data.terminal}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-lbl">Gate</span>
                        <span class="detail-val" style="color: #06b6d4;">${data.gate}</span>
                    </div>
                </div>
            </div>
        `;
    } 
    else if (cardType === "pnr_card") {
        const pnr = data.pnr;
        const fl = data.flight;
        slot.innerHTML = `
            <div class="flight-preview-card">
                <div class="card-top">
                    <div class="card-title-group">
                        <span class="airline-tag">PNR: ${pnr.pnr_code} • ${pnr.passenger_name}</span>
                    </div>
                    <span class="status-badge ON_TIME">${pnr.status}</span>
                </div>
                <div class="route-display">
                    <div class="airport-block">
                        <span class="airport-code">${pnr.origin}</span>
                        <span class="airport-name">Date: ${pnr.travel_date}</span>
                    </div>
                    <div class="route-arrow">
                        <span>✈️ ${pnr.flight_number}</span>
                    </div>
                    <div class="airport-block" style="text-align: right;">
                        <span class="airport-code">${pnr.destination}</span>
                        <span class="airport-name">${pnr.cabin_class}</span>
                    </div>
                </div>
                <div class="card-details-grid">
                    <div class="detail-item">
                        <span class="detail-lbl">Assigned Seat</span>
                        <span class="detail-val" style="color: #06b6d4; font-size: 1.1rem;">${pnr.seat}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-lbl">Cabin</span>
                        <span class="detail-val">${pnr.cabin_class}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-lbl">Flight Status</span>
                        <span class="detail-val">${fl ? fl.status : 'CONFIRMED'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-lbl">Baggage Tags</span>
                        <span class="detail-val">${pnr.baggage_tags.join(", ") || 'None'}</span>
                    </div>
                </div>
            </div>
        `;
    }
    else if (cardType === "baggage_card") {
        slot.innerHTML = `
            <div class="baggage-preview-card">
                <div class="card-top">
                    <div class="card-title-group">
                        <span class="airline-tag">🧳 Tag: ${data.tag_number} • ${data.passenger_name}</span>
                    </div>
                    <span class="status-badge ON_TIME">${data.status}</span>
                </div>
                <div style="margin: 0.75rem 0;">
                    <div style="font-size: 0.82rem; color: #94a3b8;">Flight: <strong>${data.flight_number}</strong> | PNR: <code>${data.pnr_code}</code></div>
                    <div style="font-size: 0.9rem; color: #fff; margin-top: 4px;">Last Location: <strong style="color: #06b6d4;">${data.last_seen_location}</strong></div>
                    <div style="font-size: 0.78rem; color: #64748b; margin-top: 2px;">Updated: ${data.last_updated}</div>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; font-size: 0.8rem; color: #cbd5e1;">
                    ℹ️ ${data.notes || 'Telemetry normal. Baggage in transit.'}
                </div>
            </div>
        `;
    }
    else if (cardType === "rebook_card") {
        const options = data.options || [];
        let optionsHtml = options.map((opt, idx) => `
            <div style="background: rgba(0,0,0,0.3); border: 1px solid ${opt.recommended ? '#10b981' : 'rgba(255,255,255,0.1)'}; padding: 10px; border-radius: 8px; margin-top: 8px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong style="color: #fff;">${opt.airline} ${opt.flight_number}</strong>
                    <div style="font-size: 0.75rem; color: #94a3b8;">${opt.origin} → ${opt.destination} • Departs: ${opt.departure_time}</div>
                    <div style="font-size: 0.72rem; color: #10b981;">${opt.available_seats} seats remaining • Zero Fare Difference</div>
                </div>
                <button onclick="confirmRebooking('${opt.flight_number}')" style="background: #10b981; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer;">
                    Confirm Rebooking
                </button>
            </div>
        `).join("");

        slot.innerHTML = `
            <div class="rebook-preview-card">
                <div class="card-top">
                    <span class="airline-tag">🔄 Available Flight Rebooking Options</span>
                    <span class="status-badge ON_TIME">INSTANT REBOOK</span>
                </div>
                <p style="font-size: 0.82rem; color: #94a3b8;">Selected partner flight inventory with zero change penalty fee:</p>
                ${optionsHtml}
            </div>
        `;
    }
}

async function confirmRebooking(newFlightNumber) {
    try {
        const res = await fetch("/api/rebook", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                pnr_code: "BA9921",
                new_flight_number: newFlightNumber
            })
        });
        const result = await res.json();
        alert(`Flight rebooked successfully! New flight: ${newFlightNumber}`);
        appendMessage("agent", `Your rebooking to flight ${newFlightNumber} has been confirmed. Updated boarding documents have been generated.`);
        speakText(`Your rebooking to flight ${newFlightNumber} has been confirmed.`);
        refreshDatabaseView();
    } catch(e) {
        console.error("Rebook error:", e);
    }
}

/* =========================================================================
   6. USER INPUT HANDLERS (Text & Scenarios)
   ========================================================================= */

function handleInputKey(event) {
    if (event.key === "Enter") {
        sendTextMessage();
    }
}

function sendTextMessage() {
    const input = document.getElementById("text-speech-input");
    const text = input.value.trim();
    if (!text) return;

    // Interrupt current playback if user submits new query
    triggerBargeIn();

    input.value = "";
    sendSpeechToServer(text, 0.98);
}

function sendSampleQuery(text) {
    triggerBargeIn();
    sendSpeechToServer(text, 0.99);
}

/* =========================================================================
   7. SUPERVISOR COMMAND CENTER (Section 3.1.5)
   ========================================================================= */

function initSupervisorWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/supervisor`;

    supervisorSocket = new WebSocket(wsUrl);

    supervisorSocket.onmessage = (event) => {
        try {
            const packet = JSON.parse(event.data);
            handleSupervisorEvent(packet);
        } catch(e) {
            console.error("Supervisor WS packet error:", e);
        }
    };

    supervisorSocket.onclose = () => {
        setTimeout(initSupervisorWebSocket, 4000);
    };
}

function handleSupervisorEvent(packet) {
    const type = packet.type;
    const data = packet.data || packet;

    if (type === "initial_state") {
        renderSupervisorCallsList(data.sessions || []);
    }
    else if (type === "session_created" || type === "session_disconnected") {
        fetchActiveSessions();
    }
    else if (type === "escalation_triggered") {
        showSupervisorAlertPill();
        fetchActiveSessions();
    }
    else if (type === "transcript_added") {
        if (currentSupervisorFocusedSession === data.session_id) {
            appendSupervisorTranscript(data.transcript_item);
        }
    }
    else if (type === "session_taken_over") {
        fetchActiveSessions();
    }
}

function showSupervisorAlertPill() {
    const pill = document.getElementById("supervisor-alert-badge");
    if (pill) pill.style.display = "inline-block";
}

async function fetchActiveSessions() {
    try {
        const res = await fetch("/api/supervisor/sessions");
        const sessions = await res.json();
        renderSupervisorCallsList(sessions);
    } catch(e) {
        console.error("Error fetching sessions:", e);
    }
}

function renderSupervisorCallsList(sessions) {
    const list = document.getElementById("supervisor-calls-list");
    const countBadge = document.getElementById("active-calls-count");
    if (countBadge) countBadge.innerText = sessions.length;

    if (!sessions || sessions.length === 0) {
        list.innerHTML = `<div class="empty-state">No passenger calls currently active. Initiate a call from Passenger Terminal.</div>`;
        return;
    }

    list.innerHTML = "";
    sessions.forEach(s => {
        const item = document.createElement("div");
        const isEscalated = s.escalated_to_supervisor;
        item.className = `call-item ${isEscalated ? 'escalated' : ''} ${s.session_id === currentSupervisorFocusedSession ? 'active' : ''}`;
        item.onclick = () => selectSupervisorSession(s.session_id);

        const confVal = s.latest_confidence ? s.latest_confidence.composite_confidence.toFixed(2) : '—';

        item.innerHTML = `
            <div class="call-item-top">
                <span>Session: <code>${s.session_id}</code></span>
                <span style="color: ${isEscalated ? '#f43f5e' : '#10b981'}">${s.status}</span>
            </div>
            <div class="call-item-meta">
                <span>Passenger: ${s.passenger_name || 'Anonymous'}</span>
                <span>Conf: <strong>${confVal}</strong></span>
            </div>
        `;
        list.appendChild(item);
    });

    // Auto-focus current active passenger session
    if (!currentSupervisorFocusedSession && sessions.length > 0) {
        selectSupervisorSession(sessions[sessions.length - 1].session_id);
    }
}

async function selectSupervisorSession(id) {
    currentSupervisorFocusedSession = id;
    try {
        const res = await fetch(`/api/supervisor/session/${id}`);
        const session = await res.json();

        document.getElementById("sup-passenger").innerText = session.passenger_name || "Anonymous Passenger";
        document.getElementById("sup-pnr").innerText = session.pnr_code || "—";
        document.getElementById("sup-flight").innerText = session.active_flight_number || "—";

        const conf = session.latest_confidence ? session.latest_confidence.composite_confidence.toFixed(2) : "—";
        document.getElementById("sup-conf").innerText = conf;

        const container = document.getElementById("supervisor-transcript-container");
        container.innerHTML = "";
        (session.transcript || []).forEach(t => appendSupervisorTranscript(t));

        // Enable takeover button
        const takeoverBtn = document.getElementById("takeover-btn");
        const inputMsg = document.getElementById("supervisor-input-msg");
        const sendBtn = document.getElementById("supervisor-send-btn");

        takeoverBtn.disabled = false;
        inputMsg.disabled = false;
        sendBtn.disabled = false;

        if (session.status === "SUPERVISOR_ACTIVE") {
            takeoverBtn.innerText = "✅ Supervisor Active (Connected)";
            takeoverBtn.style.background = "#10b981";
        } else {
            takeoverBtn.innerText = "🎙️ One-Click Takeover";
            takeoverBtn.style.background = "";
        }
    } catch(e) {
        console.error("Error loading session:", e);
    }
}

function appendSupervisorTranscript(item) {
    const container = document.getElementById("supervisor-transcript-container");
    if (!container || !item.text) return;

    const div = document.createElement("div");
    div.className = `chat-msg ${item.speaker}`;
    div.innerHTML = `
        <div class="msg-meta">
            <span>${item.speaker.toUpperCase()}</span>
            <span>• ${item.timestamp || 'now'}</span>
        </div>
        <div class="msg-bubble">${item.text}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

async function executeSupervisorTakeover() {
    if (!currentSupervisorFocusedSession) return;

    try {
        const res = await fetch(`/api/supervisor/takeover/${currentSupervisorFocusedSession}?supervisor_name=Lead%20Supervisor`, {
            method: "POST"
        });
        const data = await res.json();
        alert(data.message);
        selectSupervisorSession(currentSupervisorFocusedSession);
    } catch(e) {
        console.error("Takeover error:", e);
    }
}

function handleSupervisorKey(event) {
    if (event.key === "Enter") {
        sendSupervisorMessage();
    }
}

async function sendSupervisorMessage() {
    const input = document.getElementById("supervisor-input-msg");
    const msg = input.value.trim();
    if (!msg || !currentSupervisorFocusedSession) return;

    input.value = "";
    try {
        await fetch(`/api/supervisor/message/${currentSupervisorFocusedSession}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: msg,
                supervisor_name: "Lead Supervisor"
            })
        });
    } catch(e) {
        console.error("Error dispatching supervisor message:", e);
    }
}

/* =========================================================================
   8. AVIATION DATABASE VIEWER
   ========================================================================= */

async function refreshDatabaseView() {
    try {
        const [flightsRes, pnrRes, baggageRes] = await Promise.all([
            fetch("/api/flights"),
            fetch("/api/pnr/W7X9K2"),
            fetch("/api/baggage/BAG-90812")
        ]);

        const flights = await flightsRes.json();
        renderFlightsTable(flights);

        // Fetch additional PNRs and baggage
        renderPnrTable();
        renderBaggageTable();
    } catch(e) {
        console.error("DB refresh error:", e);
    }
}

function renderFlightsTable(flights) {
    const slot = document.getElementById("db-flights-table-slot");
    if (!slot) return;

    let rows = flights.map(f => `
        <tr>
            <td><strong>${f.flight_number}</strong></td>
            <td>${f.airline}</td>
            <td><code>${f.origin} → ${f.destination}</code></td>
            <td>${f.scheduled_departure}</td>
            <td><span class="status-badge ${f.status}">${f.status}</span></td>
            <td>${f.terminal} / ${f.gate}</td>
            <td>${f.remarks || '—'}</td>
        </tr>
    `).join("");

    slot.innerHTML = `
        <table class="db-table">
            <thead>
                <tr>
                    <th>Flight No</th>
                    <th>Airline</th>
                    <th>Route</th>
                    <th>Scheduled</th>
                    <th>Status</th>
                    <th>Gate</th>
                    <th>Remarks</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

async function renderPnrTable() {
    const slot = document.getElementById("db-pnr-table-slot");
    const pnrs = ["W7X9K2", "DL8401", "BA9921", "EK4032"];

    const pnrData = await Promise.all(pnrs.map(async p => {
        const res = await fetch(`/api/pnr/${p}`);
        return res.json();
    }));

    let rows = pnrData.map(p => `
        <tr>
            <td><code>${p.pnr_code}</code></td>
            <td><strong>${p.passenger_name}</strong></td>
            <td>${p.flight_number} (${p.origin} → ${p.destination})</td>
            <td>${p.travel_date}</td>
            <td><strong>${p.seat}</strong> (${p.cabin_class})</td>
            <td><span class="status-badge ON_TIME">${p.status}</span></td>
            <td>${p.baggage_tags.join(", ") || 'None'}</td>
        </tr>
    `).join("");

    slot.innerHTML = `
        <table class="db-table">
            <thead>
                <tr>
                    <th>PNR</th>
                    <th>Passenger Name</th>
                    <th>Flight</th>
                    <th>Date</th>
                    <th>Seat</th>
                    <th>Status</th>
                    <th>Baggage Tag</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

async function renderBaggageTable() {
    const slot = document.getElementById("db-baggage-table-slot");
    const tags = ["BAG-90812", "BAG-55421", "BAG-10294", "BAG-77319"];

    const bagData = await Promise.all(tags.map(async t => {
        const res = await fetch(`/api/baggage/${t}`);
        return res.json();
    }));

    let rows = bagData.map(b => `
        <tr>
            <td><code>${b.tag_number}</code></td>
            <td>${b.passenger_name}</td>
            <td>${b.flight_number} (PNR: <code>${b.pnr_code}</code>)</td>
            <td><span class="status-badge ON_TIME">${b.status}</span></td>
            <td><strong>${b.last_seen_location}</strong></td>
            <td>${b.last_updated}</td>
            <td>${b.notes || '—'}</td>
        </tr>
    `).join("");

    slot.innerHTML = `
        <table class="db-table">
            <thead>
                <tr>
                    <th>Tag Number</th>
                    <th>Passenger</th>
                    <th>Flight / PNR</th>
                    <th>Status</th>
                    <th>Last Location Scan</th>
                    <th>Updated</th>
                    <th>Handling Notes</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

/* =========================================================================
   9. TAB SWITCHER
   ========================================================================= */

function switchTab(tabId) {
    document.querySelectorAll(".nav-tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-view").forEach(view => view.classList.remove("active"));

    if (tabId === "passenger") {
        document.getElementById("tab-passenger-btn").classList.add("active");
        document.getElementById("view-passenger").classList.add("active");
    } else if (tabId === "supervisor") {
        document.getElementById("tab-supervisor-btn").classList.add("active");
        document.getElementById("view-supervisor").classList.add("active");
        document.getElementById("supervisor-alert-badge").style.display = "none";
        fetchActiveSessions();
    } else if (tabId === "database") {
        document.getElementById("tab-database-btn").classList.add("active");
        document.getElementById("view-database").classList.add("active");
        refreshDatabaseView();
    }
}
