let isCallActive = false;
let isSpeaking = false;
let isMuted = false;
let recognition = null;
let audioContext = null;
let timerInterval = null;
let callSeconds = 0;

// Dual-Tone Telephone Ringtone Synthesizer (440Hz + 480Hz)
function startRingtone() {
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        playRingPulse();
    } catch(e) {
        console.log("AudioContext blocked until user interaction:", e);
    }
}

function playRingPulse() {
    if (isCallActive || !audioContext) return;
    const now = audioContext.currentTime;

    const osc1 = audioContext.createOscillator();
    const osc2 = audioContext.createOscillator();
    const gain = audioContext.createGain();

    osc1.frequency.value = 440;
    osc2.frequency.value = 480;

    gain.gain.setValueAtTime(0.18, now);
    gain.gain.setValueAtTime(0, now + 1.2);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(audioContext.destination);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 1.2);
    osc2.stop(now + 1.2);

    if (navigator.vibrate) {
        navigator.vibrate([400, 200, 400]);
    }

    if (!isCallActive) {
        setTimeout(playRingPulse, 3000);
    }
}

// Continuous Hands-Free Speech Recognition Setup
function setupSpeechRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        appendTranscript("JARVIS", "Web Speech API not supported in this browser. Please use Chrome or Edge.");
        return;
    }

    recognition = new SpeechRec();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-IN'; // Optimized for Indian English & Tanglish

    recognition.onstart = () => {
        document.getElementById('callStatus').innerText = "LISTENING TO BOSS...";
        document.getElementById('muteBtn').classList.add('listening');
    };

    recognition.onresult = (event) => {
        const speechText = event.results[0][0].transcript;
        appendTranscript("Mukil", speechText);
        sendTurnToJARVIS(speechText);
    };

    recognition.onerror = (event) => {
        console.log("Speech Recognition Status:", event.error);
        if (isCallActive && !isSpeaking && !isMuted) {
            setTimeout(listenAgain, 1000);
        }
    };

    recognition.onend = () => {
        document.getElementById('muteBtn').classList.remove('listening');
        if (isCallActive && !isSpeaking && !isMuted) {
            setTimeout(listenAgain, 500);
        }
    };
}

function listenAgain() {
    if (isCallActive && !isSpeaking && !isMuted && recognition) {
        try {
            recognition.start();
        } catch(e) {
            // Already active
        }
    }
}

function appendTranscript(sender, text) {
    const box = document.getElementById('transcriptBox');
    const bubble = document.createElement('div');
    bubble.className = `msg-bubble ${sender === 'Mukil' ? 'msg-mukil' : 'msg-jarvis'}`;
    bubble.innerHTML = `<strong>${sender}:</strong> ${text}`;
    box.appendChild(bubble);
    box.scrollTop = box.scrollHeight;
}

async function acceptCall() {
    isCallActive = true;
    document.getElementById('hudOrb').classList.remove('ringing');
    document.getElementById('phoneContainer').classList.add('active-call');
    document.getElementById('incomingControls').classList.add('hidden');
    document.getElementById('activeControls').classList.remove('hidden');
    document.getElementById('callStatus').innerText = "CALL CONNECTED";

    // Start Call Clock
    timerInterval = setInterval(() => {
        callSeconds++;
        const mins = String(Math.floor(callSeconds / 60)).padStart(2, '0');
        const secs = String(callSeconds % 60).padStart(2, '0');
        document.getElementById('callClock').innerText = `${mins}:${secs}`;
    }, 1000);

    setupSpeechRecognition();

    // Trigger Initial AI Spoken Greeting
    try {
        const res = await fetch('/api/reset', { method: 'POST' });
        const data = await res.json();
        appendTranscript("JARVIS", data.greeting);
        if (data.audio_b64) {
            await playAudioBase64(data.audio_b64);
        }
    } catch(e) {
        appendTranscript("JARVIS", "Vanakkam Boss! JARVIS continuous call active. Sollinga Mapla!");
    }

    listenAgain();
}

async function sendTurnToJARVIS(text) {
    document.getElementById('callStatus').innerText = "JARVIS THINKING...";
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        appendTranscript("JARVIS", data.reply);
        if (data.audio_b64) {
            await playAudioBase64(data.audio_b64);
        }
    } catch(e) {
        appendTranscript("JARVIS", "Boss, connection issue. Repeat panlama?");
    }

    listenAgain();
}

function playAudioBase64(b64) {
    return new Promise((resolve) => {
        isSpeaking = true;
        document.getElementById('callStatus').innerText = "JARVIS SPEAKING...";
        if (recognition) {
            try { recognition.stop(); } catch(e) {}
        }

        const audio = new Audio("data:audio/mp3;base64," + b64);
        audio.onended = () => {
            isSpeaking = false;
            document.getElementById('callStatus').innerText = "LISTENING TO BOSS...";
            resolve();
        };
        audio.onerror = () => {
            isSpeaking = false;
            resolve();
        };
        audio.play().catch(e => {
            console.log("Audio play gesture error:", e);
            isSpeaking = false;
            resolve();
        });
    });
}

function declineCall() {
    endCall();
}

function endCall() {
    isCallActive = false;
    clearInterval(timerInterval);
    if (recognition) {
        try { recognition.stop(); } catch(e) {}
    }
    document.getElementById('callStatus').innerText = "CALL TERMINATED";
    document.getElementById('phoneContainer').classList.remove('active-call');
    document.getElementById('activeControls').classList.add('hidden');
    document.getElementById('incomingControls').classList.remove('hidden');
    appendTranscript("JARVIS", "Call ended. Ready for the next mission, Boss! 🫡");
}

function toggleMute() {
    isMuted = !isMuted;
    document.getElementById('micLabel').innerText = isMuted ? "Unmute" : "Mute";
    if (isMuted && recognition) {
        try { recognition.stop(); } catch(e) {}
    } else if (!isMuted) {
        listenAgain();
    }
}

// Start ringtone on initial user tap
window.addEventListener('load', () => {
    startRingtone();
});
document.addEventListener('click', () => {
    if (!audioContext) startRingtone();
}, { once: true });
