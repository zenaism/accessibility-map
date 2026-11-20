/* Openway Assistant: speech in and out through the browser (feature-detected; text always works). */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const w = typeof window !== 'undefined' ? window : {};
  const SR = w.SpeechRecognition || w.webkitSpeechRecognition || null;
  const supportsIn = () => !!SR;
  const supportsOut = () => typeof w.speechSynthesis !== 'undefined' && typeof w.SpeechSynthesisUtterance !== 'undefined';

  /** Starts listening once; returns a handle with stop(). Callbacks: onstart, onresult(text, final), onerror(words), onend. */
  function listen(cb) {
    if (!SR) { cb.onerror && cb.onerror("Voice input is not available in this browser. You can type your question, or use the dictation key on your keyboard or phone."); return null; }
    let rec;
    try { rec = new SR(); } catch (e) { cb.onerror && cb.onerror('Voice input could not start. You can type your question instead.'); return null; }
    rec.lang = 'en-US'; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    rec.onstart = () => cb.onstart && cb.onstart();
    rec.onresult = ev => {
      let text = '', final = false;
      for (let i = ev.resultIndex; i < ev.results.length; i++) { text += ev.results[i][0].transcript; if (ev.results[i].isFinal) final = true; }
      cb.onresult && cb.onresult(text.trim(), final);
    };
    rec.onerror = ev => {
      const map = {
        'not-allowed': 'The microphone is blocked. Allow it in your browser settings, or type your question.',
        'service-not-allowed': 'The microphone is blocked. Allow it in your browser settings, or type your question.',
        'no-speech': 'I did not hear anything. Try again, or type your question.',
        'audio-capture': 'No microphone was found. You can type your question instead.',
        'network': 'Voice input needs an internet connection in this browser. You can type your question instead.',
      };
      cb.onerror && cb.onerror(map[ev.error] || 'Voice input stopped. You can type your question instead.');
    };
    rec.onend = () => cb.onend && cb.onend();
    try { rec.start(); } catch (e) { cb.onerror && cb.onerror('Voice input could not start. You can type your question instead.'); return null; }
    return { stop() { try { rec.stop(); } catch (e) { /* already stopped */ } } };
  }

  let current = null;
  function speak(text, opts) {
    opts = opts || {};
    if (!supportsOut()) return false;
    stop();
    const u = new w.SpeechSynthesisUtterance(text);
    u.rate = opts.rate || 1; u.lang = 'en-US';
    u.onend = u.onerror = () => { if (current === u) current = null; opts.onend && opts.onend(); };
    current = u;
    w.speechSynthesis.speak(u);
    return true;
  }
  const stop = () => { if (supportsOut()) w.speechSynthesis.cancel(); current = null; };
  const pause = () => { if (supportsOut()) w.speechSynthesis.pause(); };
  const resume = () => { if (supportsOut()) w.speechSynthesis.resume(); };
  const V = { supportsIn, supportsOut, listen, speak, stop, pause, resume };
  O.voice = V;
  if (typeof module !== 'undefined') module.exports = V;
})(typeof globalThis !== 'undefined' ? globalThis : this);
