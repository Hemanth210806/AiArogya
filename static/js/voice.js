// voice.js — Web Speech API voice input for ArogyaAI
let recognition = null;
let isListening = false;

function toggleVoice() {
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert('Voice input is not supported in this browser. Please use Chrome.');
    return;
  }
  if (isListening) {
    recognition.stop();
    return;
  }
  const lang = document.getElementById('voice-lang')?.value || 'en-IN';
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = lang;
  recognition.continuous = false;
  recognition.interimResults = true;

  const micBtn = document.getElementById('mic-btn');
  const status = document.getElementById('voice-status');
  const resultDiv = document.getElementById('voice-result');
  const voiceText = document.getElementById('voice-text');

  recognition.onstart = () => {
    isListening = true;
    micBtn.style.background = 'linear-gradient(135deg,#C62828,#E53935)';
    micBtn.style.animation = 'pulse-sos 1s infinite';
    status.textContent = '🔴 Listening... Speak now';
  };

  recognition.onresult = (e) => {
    let transcript = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript;
    }
    voiceText.textContent = transcript;
    resultDiv.style.display = 'block';
    // Also put in main text area
    const ta = document.getElementById('symptoms_text');
    if (ta) ta.value = transcript;
  };

  recognition.onerror = (e) => {
    let msg = e.error;
    if (e.error === 'not-allowed') msg = 'Microphone permission denied. Please allow it in browser settings.';
    if (e.error === 'network') msg = 'Network error. Voice recognition requires internet.';
    status.textContent = '❌ Error: ' + msg;
    resetMic();
  };

  recognition.onend = () => {
    status.textContent = '✅ Done! You can submit now.';
    resetMic();
  };

  recognition.start();
}

function resetMic() {
  isListening = false;
  const micBtn = document.getElementById('mic-btn');
  if (micBtn) {
    micBtn.style.background = 'linear-gradient(135deg,#2E7D32,#1565C0)';
    micBtn.style.animation = 'none';
  }
}
