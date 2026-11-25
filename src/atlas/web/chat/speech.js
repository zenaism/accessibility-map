/* Speech input for the chat (session B3): tap to start, tap Stop, 60 second cap, restart after a pause, keep what was said.
   Openway.speech.create(options) -> controller {start(), stop(), clear(), state}. Callbacks:
     onState(name, info)  name: idle | recording | warning | restarting | processing | transcript | limit | denied | unsupported
                          info: {seconds, left, words}
     onText(text)         the whole text so far (kept words + the words being heard); the box shows it
   Never sends anything and never throws text away: stop, a browser pause, an error and the 60 second limit all keep it.
   Timing options (tests shorten them): max (seconds, 60), warn (seconds before the end, 10), restartMs (350). */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const w = typeof window !== 'undefined' ? window : {};
  const supported = () => !!(w.SpeechRecognition || w.webkitSpeechRecognition);
  const words = (t) => (String(t).trim() ? String(t).trim().split(/\s+/).length : 0);

  function create(opt) {
    opt = opt || {};
    const MAX = opt.max || 60, WARN = opt.warn || 10, RESTART = opt.restartMs === undefined ? 350 : opt.restartMs;
    const on = opt.onState || function () {}, onText = opt.onText || function () {};
    const C = { state: 'idle', kept: '', interim: '', base: '', rec: null, t0: 0, tick: null, wantStop: false, restarts: 0, lastStart: 0, timer: null };
    const clock = () => (w.performance ? w.performance.now() : Date.now());
    const seconds = () => Math.min(MAX, Math.floor((clock() - C.t0) / 1000));
    const text = () => [C.base, C.kept, C.interim].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
    const emit = (name) => { C.state = name; on(name, { seconds: C.t0 ? seconds() : 0, left: Math.max(0, MAX - (C.t0 ? seconds() : 0)), words: words(text()), max: MAX }); };
    const stopTick = () => { if (C.tick) { w.clearInterval(C.tick); C.tick = null; } };

    function begin() {
      const SR = w.SpeechRecognition || w.webkitSpeechRecognition;
      let rec;
      try { rec = new SR(); } catch (e) { fail('unsupported'); return false; }
      rec.lang = opt.lang || 'en-US'; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
      rec.onstart = () => { C.lastStart = clock(); if (C.state === 'restarting' || C.state === 'idle' || C.state === 'transcript' || C.state === 'limit') emit(seconds() >= MAX - WARN ? 'warning' : 'recording'); };
      rec.onresult = (ev) => {
        let interim = '', fin = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) { const r = ev.results[i]; if (r.isFinal) fin += r[0].transcript + ' '; else interim += r[0].transcript; }
        if (fin) C.kept = (C.kept + ' ' + fin).trim();
        C.interim = interim.trim();
        onText(text());
      };
      rec.onerror = (ev) => {
        if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') { C.wantStop = true; finish('denied'); }
        else if (ev.error === 'audio-capture') { C.wantStop = true; finish('unsupported'); }
        // no-speech, network, aborted: onend follows; the restart logic or the transcript state handles it and the text is kept
        C.lastError = ev.error;
      };
      rec.onend = () => {
        if (C.interim) { C.kept = (C.kept + ' ' + C.interim).trim(); C.interim = ''; onText(text()); }
        if (C.rec !== rec) return;
        if (C.hitLimit) { finish('limit'); return; }
        if (C.wantStop || C.state === 'denied' || C.state === 'unsupported') { finish('transcript'); return; }
        if (seconds() >= MAX) { finish('limit'); return; }
        // the browser ended at a pause: keep the words and listen again after a short gap
        C.restarts = clock() - C.lastStart < 1500 ? C.restarts + 1 : 0;
        if (C.restarts >= 4 || C.lastError === 'network') { C.lastError = null; finish('transcript'); return; }
        emit('restarting');
        C.timer = w.setTimeout(() => { if (C.state === 'restarting') { C.rec = null; if (!begin()) finish('transcript'); } }, RESTART);
      };
      C.rec = rec;
      try { rec.start(); } catch (e) { C.rec = null; return false; }
      return true;
    }
    function finish(name) {
      stopTick(); w.clearTimeout(C.timer);
      const r = C.rec; C.rec = null; C.wantStop = false;
      if (r) { try { r.abort ? r.abort() : r.stop(); } catch (e) { /* already stopped */ } }
      if (C.interim) { C.kept = (C.kept + ' ' + C.interim).trim(); C.interim = ''; }
      onText(text());
      emit(name);
    }
    function fail(name) { finish(name); }
    return {
      get state() { return C.state; },
      supported,
      text,
      start(existing) {
        if (!supported()) { emit('unsupported'); return false; }
        if (C.state === 'recording' || C.state === 'warning' || C.state === 'restarting') return true;
        C.base = String(existing || '').trim(); C.kept = ''; C.interim = ''; C.restarts = 0; C.wantStop = false; C.lastError = null;
        C.t0 = clock(); C.hitLimit = false;
        C.tick = w.setInterval(() => {
          if (!['recording', 'warning', 'restarting'].includes(C.state)) return;
          const s = seconds();
          if (s >= MAX) { C.wantStop = true; if (C.rec) { try { C.rec.stop(); } catch (e) { /* ignore */ } } else finish('limit'); C.hitLimit = true; return; }
          if (s >= MAX - WARN && C.state === 'recording') emit('warning'); else on(C.state, { seconds: s, left: MAX - s, words: words(text()), max: MAX });
        }, 250);
        if (!begin()) { stopTick(); emit('unsupported'); return false; }
        emit('recording');
        return true;
      },
      stop() {
        if (!['recording', 'warning', 'restarting'].includes(C.state)) return;
        C.wantStop = true; emit('processing');
        if (C.state === 'processing' && C.rec) { try { C.rec.stop(); } catch (e) { finish('transcript'); } w.clearTimeout(C.timer); }
        else finish('transcript');
      },
      clear() { C.base = ''; C.kept = ''; C.interim = ''; onText(''); emit('idle'); },
      reset() { stopTick(); w.clearTimeout(C.timer); if (C.rec) { try { C.rec.abort(); } catch (e) { /* ignore */ } } C.rec = null; C.state = 'idle'; },
      limitHit() { return !!C.hitLimit; },
    };
  }
  O.speech = { create, supported };
  if (typeof module !== 'undefined') module.exports = O.speech;
})(typeof globalThis !== 'undefined' ? globalThis : this);
