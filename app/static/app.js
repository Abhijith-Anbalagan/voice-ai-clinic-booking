/* ─────────────────────────────────────────
   MediBook — Voice Booking Frontend Logic
   v2: Start screen gate + Review/Confirm modal
───────────────────────────────────────── */

// ── DOM refs ──────────────────────────────
const startScreen   = document.getElementById("startScreen");
const startBtn      = document.getElementById("startBtn");

const talkBtn       = document.getElementById("talkBtn");
const stopBtn       = document.getElementById("stopBtn");
const sendBtn       = document.getElementById("sendBtn");
const manualInput   = document.getElementById("manualInput");
const statusBadge   = document.getElementById("statusBadge");
const ringContainer = document.getElementById("ringContainer");
const voiceLabel    = document.getElementById("voiceLabel");
const voiceHint     = document.getElementById("voiceHint");
const convoBody     = document.getElementById("convoBody");
const confirmedCard = document.getElementById("confirmedCard");
const confirmedMsg  = document.getElementById("confirmedMsg");
const bookAnotherBtn= document.getElementById("bookAnotherBtn");

// Review modal refs
const reviewModal      = document.getElementById("reviewModal");
const rvDoctor         = document.getElementById("rv-doctor");
const rvDatetime       = document.getElementById("rv-datetime");
const rvName           = document.getElementById("rv-name");
const rvEmail          = document.getElementById("rv-email");
const reviewCancelBtn  = document.getElementById("reviewCancelBtn");
const reviewConfirmBtn = document.getElementById("reviewConfirmBtn");

// Progress step elements
const stepDoctor  = document.getElementById("step-doctor");
const stepDate    = document.getElementById("step-date");
const stepPatient = document.getElementById("step-patient");
const stepEmail   = document.getElementById("step-email");
const valDoctor   = document.getElementById("val-doctor");
const valDate     = document.getElementById("val-date");
const valPatient  = document.getElementById("val-patient");
const valEmail    = document.getElementById("val-email");

// ── State ─────────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition    = null;
let sessionId      = null;
let isListening    = false;
let isSpeaking     = false;
let autoContinue   = true;
let silenceTimer   = null;
let introPlayed    = false;   // true once the greeting has been spoken

// Tracks current booking state from server
let currentState   = {};

// Tracks the "pending confirm" info when we've gathered everything
// but are showing the review modal before actually sending to server.
let pendingReviewText = null;  // the user's final "yes/confirm" utterance held

// ── UI helpers ────────────────────────────
function setMicMode(mode, hint = "") {
  talkBtn.className = `mic-btn ${mode}`;
  ringContainer.className = `ring-container ${mode}`;

  const labels = {
    waiting:    ["Ready to listen",     hint || "Tap the mic or press Space to begin"],
    listening:  ["Listening\u2026",     hint || "Speak now \u2014 I'm hearing you"],
    speaking:   ["Assistant speaking",  hint || "Tap mic to interrupt anytime"],
    processing: ["Processing\u2026",    hint || "Checking availability\u2026"],
    error:      ["Voice issue",         hint || "Try typing in the box below"],
  };

  const [label, h] = labels[mode] || labels.waiting;
  voiceLabel.textContent = label;
  voiceHint.textContent  = h;

  const badgeMap = {
    waiting: "", listening: "listening", speaking: "speaking",
    processing: "processing", error: "error", done: "done",
  };
  statusBadge.className = "convo-badge " + (badgeMap[mode] || "");
  statusBadge.textContent = {
    waiting: "Idle", listening: "Listening", speaking: "Speaking",
    processing: "Processing", error: "Error", done: "Done",
  }[mode] || mode;
}

function addBubble(role, text) {
  const typing = convoBody.querySelector(".bubble.typing");
  if (typing) typing.remove();

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "bubble-avatar";
  avatar.textContent = role === "assistant" ? "\u2726" : "U";

  const body = document.createElement("div");
  body.className = "bubble-text";
  body.textContent = text;

  bubble.appendChild(avatar);
  bubble.appendChild(body);
  convoBody.appendChild(bubble);
  convoBody.scrollTop = convoBody.scrollHeight;
}

function showTyping() {
  const bubble = document.createElement("div");
  bubble.className = "bubble assistant typing";
  bubble.innerHTML = `
    <div class="bubble-avatar">\u2726</div>
    <div class="bubble-text">
      <div class="dot"></div>
      <div class="dot"></div>
      <div class="dot"></div>
    </div>`;
  convoBody.appendChild(bubble);
  convoBody.scrollTop = convoBody.scrollHeight;
}

function updateProgress(state) {
  if (!state) return;
  currentState = { ...currentState, ...state };

  const connectors = document.querySelectorAll(".step-connector");

  if (state.doctor_name || state.specialty) {
    stepDoctor.classList.add("done");
    valDoctor.textContent = state.doctor_name || state.specialty || "\u2014";
    if (connectors[0]) connectors[0].classList.add("done");
  }
  if (state.requested_date) {
    stepDate.classList.add("done");
    valDate.textContent =
      state.requested_date + (state.requested_time ? " \u00b7 " + formatTime(state.requested_time) : "");
    if (connectors[1]) connectors[1].classList.add("done");
  }
  if (state.patient_name) {
    stepPatient.classList.add("done");
    valPatient.textContent = state.patient_name;
    if (connectors[2]) connectors[2].classList.add("done");
  }
  if (state.patient_email) {
    stepEmail.classList.add("done");
    valEmail.textContent = state.patient_email;
  }
}

function formatTime(t) {
  if (!t) return "";
  const [h, m] = t.split(":");
  const hour = parseInt(h);
  const ampm = hour >= 12 ? "PM" : "AM";
  return `${hour % 12 || 12}:${m} ${ampm}`;
}

function showConfirmed(msg) {
  confirmedMsg.textContent = msg;
  confirmedCard.style.display = "block";
  confirmedCard.scrollIntoView({ behavior: "smooth", block: "center" });
  statusBadge.className = "convo-badge done";
  statusBadge.textContent = "Done";

  document.querySelectorAll(".step").forEach(s => s.classList.add("done"));
  document.querySelectorAll(".step-connector").forEach(c => c.classList.add("done"));
}

// ── Review Modal ──────────────────────────
/**
 * Called when the server says it has all the info (doctor, date/time, name, email)
 * and is ABOUT to create the booking. Instead of immediately sending to the server,
 * we intercept and show the review modal so the user can verify/correct first.
 *
 * @param {object} state  - the latest state from the last API response
 * @param {string} summaryReply - assistant's "all set, here's what I have" reply
 */
function openReviewModal(state, summaryReply) {
  // Fill in modal fields from current state
  rvDoctor.value   = state.doctor_name  || currentState.doctor_name  || "";
  rvName.value     = state.patient_name || currentState.patient_name || "";
  rvEmail.value    = state.patient_email|| currentState.patient_email|| "";

  const date = state.requested_date  || currentState.requested_date  || "";
  const time = state.requested_time  || currentState.requested_time  || "";
  rvDatetime.value = date + (time ? " at " + formatTime(time) : "");

  reviewModal.classList.add("open");
  reviewConfirmBtn.disabled = false;
}

function closeReviewModal() {
  reviewModal.classList.remove("open");
}

reviewCancelBtn.addEventListener("click", () => {
  closeReviewModal();
  pendingReviewText = null;
  // Resume conversation — let user re-state things
  speak(
    "No problem! You can change any detail by just telling me the correction, " +
    "or type it in the box below.",
    false
  );
});

reviewConfirmBtn.addEventListener("click", async () => {
  reviewConfirmBtn.disabled = true;

  // Read possibly-edited values back
  const editedName    = rvName.value.trim();
  const editedEmail   = rvEmail.value.trim();
  const editedDoctor  = rvDoctor.value.trim();
  const editedDatetime= rvDatetime.value.trim();

  closeReviewModal();

  // Build a confirmation utterance that incorporates any edits
  const confirmText =
    `Confirm booking. My name is ${editedName}. My email is ${editedEmail}. ` +
    `Doctor ${editedDoctor}. ${editedDatetime}.`;

  addBubble("user", `✓ Confirmed: ${editedName} · ${editedEmail}`);
  await sendTranscript(confirmText, /* skipReviewGate= */ true);
});

// ── TTS ───────────────────────────────────
function clearSilenceTimer() {
  if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
}

function stopAssistantSpeech() {
  if (speechSynthesis.speaking || speechSynthesis.pending) speechSynthesis.cancel();
  isSpeaking = false;
}

function scheduleAutoListen() {
  clearSilenceTimer();
  silenceTimer = setTimeout(() => {
    if (!isListening && !isSpeaking && autoContinue) startListening();
  }, 600);
}

function speak(text, done = false) {
  stopAssistantSpeech();
  addBubble("assistant", text);

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang  = "en-IN";
  utter.rate  = 1;
  utter.pitch = 1;
  isSpeaking  = true;

  setMicMode("speaking");

  utter.onend = () => {
    isSpeaking = false;
    if (done) {
      setMicMode("waiting", "Booking complete!");
      return;
    }
    setMicMode("waiting", "Tap mic to reply\u2026");
    if (autoContinue) scheduleAutoListen();
  };
  utter.onerror = () => {
    isSpeaking = false;
    setMicMode("waiting", "Tap mic or type below to continue");
  };

  speechSynthesis.speak(utter);
}

// ── Detect when server has all info but hasn't booked yet ─────────────────────
/**
 * Returns true if we should intercept and show the review modal instead of
 * immediately creating the booking.
 *
 * The server sets done=false while collecting info, and done=true only after
 * booking. We need to show the review modal *after* all 4 fields are known
 * but *before* the final booking call goes through.
 *
 * Strategy: we detect when the server reply says something like
 * "Could I get your full name" or "email address" — meaning it's still gathering.
 * When the state has all 4 fields populated AND done===false, we've just filled
 * in the last piece and should review.
 */
function allFieldsReady(state) {
  const s = { ...currentState, ...state };
  return !!(s.doctor_name && s.requested_date && s.patient_name && s.patient_email);
}

// ── API ───────────────────────────────────
/**
 * @param {string}  text           - utterance to send
 * @param {boolean} skipReviewGate - true when called from the review confirm button
 */
async function sendTranscript(text, skipReviewGate = false) {
  showTyping();
  setMicMode("processing");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, text }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    sessionId = data.session_id;
    if (data.state) updateProgress(data.state);

    if (data.done) {
      // Booking created — show confirmation
      speak(data.reply, true);
      showConfirmed(data.reply);
      return;
    }

    // Check if this is the moment all fields are ready and review gate fires
    if (!skipReviewGate && allFieldsReady(data.state || {})) {
      // Remove typing indicator
      const typing = convoBody.querySelector(".bubble.typing");
      if (typing) typing.remove();

      // Speak a transition line, then open the review modal
      const transitionLine =
        "Great, I have everything I need. Please review your booking details.";
      speak(transitionLine, false);

      // Open modal after a short pause for the speech to start
      setTimeout(() => openReviewModal(data.state || {}, data.reply), 500);
      return;
    }

    // Normal conversational reply
    speak(data.reply, false);

  } catch (err) {
    const typing = convoBody.querySelector(".bubble.typing");
    if (typing) typing.remove();
    addBubble("assistant", "Something went wrong. Please try again or type below.");
    setMicMode("error", "Server error \u2014 please retry");
    console.error(err);
  }
}

// ── Recognition ───────────────────────────
function startListening() {
  if (!recognition || isListening) return;
  clearSilenceTimer();
  try { recognition.start(); } catch (e) { /* already started */ }
}

function stopListening() {
  autoContinue = false;
  clearSilenceTimer();
  if (recognition && isListening) recognition.stop();
  stopAssistantSpeech();
  stopBtn.disabled = true;
  setMicMode("waiting", "Stopped \u2014 tap mic to continue");
}

function startConversation() {
  if (introPlayed) { startListening(); return; }
  introPlayed = true;

  // Add the intro bubble and speak it — exactly once
  speak(
    "Hello! I can help you book a doctor appointment. " +
    "Please tell me which doctor or specialty, your preferred date and time, " +
    "your name, and your email address."
  );
}

async function sendManual() {
  const text = manualInput.value.trim();
  if (!text) return;
  stopAssistantSpeech();
  clearSilenceTimer();
  addBubble("user", text);
  manualInput.value = "";
  await sendTranscript(text);
}

// ── Reset ─────────────────────────────────
function resetUI() {
  introPlayed   = false;
  autoContinue  = true;
  currentState  = {};
  pendingReviewText = null;

  convoBody.innerHTML = "";   // empty — will be populated when user taps mic

  document.querySelectorAll(".step").forEach(s => s.classList.remove("done"));
  document.querySelectorAll(".step-connector").forEach(c => c.classList.remove("done"));
  valDoctor.textContent = valDate.textContent = valPatient.textContent = valEmail.textContent = "\u2014";

  confirmedCard.style.display = "none";
  closeReviewModal();
  setMicMode("waiting");
}

async function resetSession() {
  stopAssistantSpeech();
  clearSilenceTimer();

  try {
    const res = await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await res.json();
    sessionId = data.session_id;
  } catch {
    sessionId = null;
  }

  resetUI();
}

// ── Start Screen ──────────────────────────
startBtn.addEventListener("click", () => {
  // Dismiss start screen with a fade
  startScreen.style.transition = "opacity .5s ease";
  startScreen.style.opacity = "0";
  startScreen.style.pointerEvents = "none";
  setTimeout(() => { startScreen.style.display = "none"; }, 520);

  // Auto-start the conversation
  autoContinue = true;
  startConversation();
});

// ── Init ──────────────────────────────────
if (!SpeechRecognition) {
  // Update start screen note
  const note = startScreen.querySelector(".start-note");
  if (note) note.textContent = "Voice not supported in this browser — please use Chrome on desktop.";

  // Set up text fallback
  const errorMsg =
    "This browser doesn\u2019t support voice. Please use Chrome on desktop, or type below.";

  // The convoBody will get this message when the user eventually dismisses the start screen
  startBtn.addEventListener("click", () => {
    addBubble("assistant", errorMsg);
    setMicMode("error", "Voice not supported \u2014 type below");
  }, { once: true });   // fires before the main listener above; main listener runs too
} else {
  recognition = new SpeechRecognition();
  recognition.lang            = "en-IN";
  recognition.interimResults  = false;
  recognition.continuous      = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isListening      = true;
    talkBtn.disabled = false;
    stopBtn.disabled = false;
    setMicMode("listening");
  };

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) return;
    addBubble("user", transcript);
    if (recognition && isListening) recognition.stop();
    await sendTranscript(transcript);
  };

  recognition.onerror = (event) => {
    isListening      = false;
    talkBtn.disabled = false;
    stopBtn.disabled = true;

    if (event.error === "no-speech") {
      setMicMode("waiting", "Didn\u2019t catch that \u2014 try again or type below");
      if (autoContinue) scheduleAutoListen();
      return;
    }
    if (event.error === "not-allowed") {
      setMicMode("error", "Allow microphone in browser settings");
      return;
    }
    if (event.error === "audio-capture") {
      setMicMode("error", "No microphone detected");
      return;
    }
    if (event.error === "network") {
      setMicMode("error", "Network issue \u2014 type below instead");
      return;
    }
    setMicMode("error", `Speech error: ${event.error}`);
  };

  recognition.onend = () => {
    isListening      = false;
    talkBtn.disabled = false;
    stopBtn.disabled = true;
  };

  // Mic button
  talkBtn.addEventListener("click", () => {
    autoContinue = true;
    if (isSpeaking) { stopAssistantSpeech(); startListening(); return; }
    startConversation();
  });

  // Space bar shortcut
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && document.activeElement === document.body) {
      e.preventDefault();
      autoContinue = true;
      if (isSpeaking) { stopAssistantSpeech(); startListening(); return; }
      startConversation();
    }
  });

  stopBtn.addEventListener("click", stopListening);
  sendBtn.addEventListener("click", sendManual);
  bookAnotherBtn.addEventListener("click", resetSession);

  manualInput.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") await sendManual();
  });
}