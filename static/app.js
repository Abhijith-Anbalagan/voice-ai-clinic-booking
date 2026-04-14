const talkBtn       = document.getElementById("talkBtn");
const stopBtn       = document.getElementById("stopBtn");
const sendBtn       = document.getElementById("sendBtn");
const manualInput   = document.getElementById("manualInput");
const userText      = document.getElementById("userText");
const botText       = document.getElementById("botText");
const userBubble    = document.getElementById("userBubble");
const orbRings      = document.getElementById("orbRings");
const orbLabel      = document.getElementById("orbLabel");
const stateDot      = document.getElementById("stateDot");
const stateText     = document.getElementById("stateText");
const bookingPanel  = document.getElementById("bookingPanel");
const confirmPanel  = document.getElementById("confirmationPanel");
const confirmSub    = document.getElementById("confirmSub");
const bookAnotherBtn = document.getElementById("bookAnotherBtn");

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition   = null;
let sessionId     = null;
let isListening   = false;
let isSpeaking    = false;
let autoContinue  = true;
let silenceTimer  = null;
let introPlayed   = false;

function setOrbMode(mode) {
  talkBtn.className = "orb";
  orbRings.className = "orb-rings";
  stateDot.className = "state-dot";

  const micIcon  = talkBtn.querySelector(".mic-icon");
  const stopIcon = talkBtn.querySelector(".stop-icon");
  micIcon.classList.remove("hidden");
  stopIcon.classList.add("hidden");

  switch (mode) {
    case "listening":
      talkBtn.classList.add("listening");
      orbRings.classList.add("active");
      stateDot.classList.add("listening");
      orbLabel.textContent = "Listening…";
      stateText.textContent = "Listening — speak now";
      micIcon.classList.add("hidden");
      stopIcon.classList.remove("hidden");
      break;
    case "speaking":
      talkBtn.classList.add("speaking");
      orbRings.classList.add("active");
      stateDot.classList.add("speaking");
      orbLabel.textContent = "Assistant speaking";
      stateText.textContent = "Speaking — tap orb to interrupt";
      break;
    case "processing":
      stateDot.classList.add("processing");
      orbLabel.textContent = "Processing…";
      stateText.textContent = "Checking availability…";
      break;
    case "error":
      talkBtn.classList.add("error");
      stateDot.classList.add("error");
      orbLabel.textContent = "Voice error";
      stateText.textContent = "Microphone issue — type below";
      break;
    default:
      orbLabel.textContent = "Tap to speak";
      stateText.textContent = "Ready";
  }
}

function clearSilenceTimer() {
  if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
}

function stopAssistantSpeech() {
  if (speechSynthesis.speaking || speechSynthesis.pending) speechSynthesis.cancel();
  isSpeaking = false;
}

function startListening() {
  if (!recognition || isListening) return;
  clearSilenceTimer();
  try { recognition.start(); } catch(e) {}
}

function scheduleAutoListen() {
  clearSilenceTimer();
  silenceTimer = setTimeout(() => {
    if (!isListening && !isSpeaking && autoContinue) startListening();
  }, 500);
}

function showConfirmation(replyText) {
  bookingPanel.classList.add("hidden");
  confirmPanel.classList.remove("hidden");
  confirmSub.textContent = replyText || "Your booking is complete. A calendar invite has been sent to your email.";
}

function speak(text, done = false) {
  stopAssistantSpeech();
  botText.textContent = text;

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "en-IN";
  utter.rate = 1;
  utter.pitch = 1;

  isSpeaking = true;
  setOrbMode("speaking");

  utter.onend = () => {
    isSpeaking = false;
    if (done) {
      setOrbMode("idle");
      showConfirmation(text);
      return;
    }
    setOrbMode("idle");
    if (autoContinue) scheduleAutoListen();
  };

  utter.onerror = () => {
    isSpeaking = false;
    setOrbMode("idle");
  };

  speechSynthesis.speak(utter);
}

async function sendTranscript(text) {
  try {
    setOrbMode("processing");

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, text }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();
    sessionId = data.session_id;
    speak(data.reply, data.done);
  } catch (err) {
    console.error(err);
    botText.textContent = "Something went wrong. Please try again.";
    setOrbMode("error");
  }
}

function stopListening() {
  autoContinue = false;
  clearSilenceTimer();
  if (recognition && isListening) recognition.stop();
  stopAssistantSpeech();
  stopBtn.disabled = true;
  setOrbMode("idle");
}

async function sendManual() {
  const text = manualInput.value.trim();
  if (!text) return;
  stopAssistantSpeech();
  clearSilenceTimer();
  showUserBubble(text);
  manualInput.value = "";
  await sendTranscript(text);
}

function showUserBubble(text) {
  userText.textContent = text;
  userBubble.classList.remove("hidden");
}

function startConversation() {
  if (introPlayed) { startListening(); return; }
  introPlayed = true;
  speak("Hello! I can help you book a doctor appointment. Please tell me which doctor or specialty you'd like, your preferred date and time, your name, and your email address.");
}

function resetSession() {
  sessionId = null;
  introPlayed = false;
  autoContinue = true;
  isListening = false;
  isSpeaking = false;
  stopAssistantSpeech();
  clearSilenceTimer();

  botText.textContent = "Press the microphone to begin booking your appointment.";
  userBubble.classList.add("hidden");
  userText.textContent = "";

  confirmPanel.classList.add("hidden");
  bookingPanel.classList.remove("hidden");
  setOrbMode("idle");
}

bookAnotherBtn.addEventListener("click", resetSession);

if (!SpeechRecognition) {
  botText.textContent = "This browser does not support Web Speech API. Please use Chrome on desktop and type your request below.";
  setOrbMode("error");
} else {
  recognition = new SpeechRecognition();
  recognition.lang = "en-IN";
  recognition.interimResults = false;
  recognition.continuous = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isListening = true;
    stopBtn.disabled = false;
    setOrbMode("listening");
  };

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) return;
    showUserBubble(transcript);
    if (recognition && isListening) recognition.stop();
    await sendTranscript(transcript);
  };

  recognition.onerror = (event) => {
    isListening = false;
    stopBtn.disabled = true;

    if (event.error === "no-speech") {
      setOrbMode("idle");
      if (autoContinue) scheduleAutoListen();
      return;
    }
    if (event.error === "not-allowed") { setOrbMode("error"); return; }
    if (event.error === "audio-capture") { setOrbMode("error"); return; }
    if (event.error === "network") { setOrbMode("error"); return; }
    setOrbMode("error");
  };

  recognition.onend = () => {
    isListening = false;
    stopBtn.disabled = true;
  };

  talkBtn.addEventListener("click", () => {
    autoContinue = true;
    if (isSpeaking) { stopAssistantSpeech(); startListening(); return; }
    if (isListening) { recognition.stop(); return; }
    startConversation();
  });

  stopBtn.addEventListener("click", stopListening);
  sendBtn.addEventListener("click", sendManual);

  manualInput.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") await sendManual();
  });
}