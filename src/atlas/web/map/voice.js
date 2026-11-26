/* Spoken route directions.
   Three parts in one file so the page and the tests load the same code:
     AtlasVoice.words   pure wording: route step -> one short sentence to say aloud (distance first)
     AtlasVoice.create  controller: Voice on or off, speed, repeat, device voice and the optional natural voice
   Engines: the device voice (speechSynthesis, nothing to download) and the natural voice (Kokoro-82M, int8, in a Web
   Worker, files served from this site under tts/). If the natural voice is off, still loading or fails, the device
   voice speaks. Nothing is sent anywhere: the position and the route stay on the phone. Prefs: localStorage "atlas.voice". */
(function (g) {
  'use strict';

  // ---------------------------------------------------------------- wording (pure)
  const LEAD_FT = 100;                                   // say the next step this far before the current one ends
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  const low = (s) => (s ? s.charAt(0).toLowerCase() + s.slice(1) : s);
  const feetWord = (ft) => Math.max(10, Math.round(ft / 10) * 10) + ' feet';

  // A step text from the router, e.g. "Cross at the marked crosswalk, 40 feet (no signal); caution: 1 short section steeper than a ramp."
  // Spoken: the action first, then each warning as its own short sentence.
  function sentences(step) {
    let t = String((step && step.text) || '').trim().replace(/\.$/, '');
    const extra = [];
    t = t.replace(/\s*\(([^)]*)\)/g, (m, d) => { extra.push(cap(d.trim())); return ''; });
    const parts = t.split(/;\s*/);
    const action = parts.shift();
    parts.forEach((p) => extra.push(cap(p.trim())));
    return { action: action.trim(), extra };
  }
  const join = (action, extra) => [cap(action)].concat(extra).map((s) => s.replace(/[.\s]+$/, '')).join('. ') + '.';
  function step(s) { const p = sentences(s); return join(p.action, p.extra); }
  // "Turn right onto the Bishop Street sidewalk for 510 feet" -> "turn right onto the Bishop Street sidewalk"
  const dropLength = (a) => a.replace(/\s+for\s+[\d.,]+\s+(?:feet|miles?)$/, '').replace(/,\s*[\d.,]+\s+feet$/, '');
  function ahead(s, feet) {
    const p = sentences(s);
    return 'In ' + feetWord(feet) + ', ' + low(dropLength(p.action)) + (p.extra.length ? '. ' + p.extra.map((e) => e.replace(/[.\s]+$/, '')).join('. ') : '') + '.';
  }
  const start = (s) => 'Route started. ' + step(s);
  const arrive = (name) => 'You have arrived' + (name ? ' at ' + name : '') + '.';
  const words = { step, ahead, start, arrive, LEAD_FT, feetWord };

  // ---------------------------------------------------------------- device voice
  const PLAIN = /^(Fred|Albert|Bad News|Bahh|Bells|Boing|Bubbles|Cellos|Wobble|Zarvox|Trinoids|Whisper|Hysterical|Organ|Superstar|Jester|Junior|Ralph|Kathy|Good News|Grandma|Grandpa|Rocko|Eddy|Flo|Reed|Sandy|Shelley)/;
  function pickDeviceVoice(list) {
    const en = (list || []).filter((v) => /^en([-_]|$)/i.test(v.lang || ''));
    if (!en.length) return null;
    const score = (v) => (/natural|neural|premium|enhanced|siri/i.test(v.name) ? 8 : 0) + (/en[-_]US/i.test(v.lang) ? 4 : 0) + (v.localService ? 1 : 0)
      + (/Samantha|Ava|Allison|Susan|Zoe|Aria|Jenny|Google US English|Microsoft .* Online/i.test(v.name) ? 3 : 0) - (PLAIN.test(v.name) ? 6 : 0);
    return en.slice().sort((a, b) => score(b) - score(a))[0];
  }
  const RATE = { slow: 0.85, normal: 1, fast: 1.2 };

  // ---------------------------------------------------------------- controller
  function create(opt) {
    opt = opt || {};
    const win = opt.window || (typeof window !== 'undefined' ? window : {});
    const store = opt.storage || (win.localStorage || null);
    const base = opt.base || (win.location ? new URL('tts/', win.location.href).href : 'tts/');
    const onChange = opt.onChange || function () {};
    let prefs = { on: false, natural: false, speed: 'normal', voice: 'af_heart' };
    try { Object.assign(prefs, JSON.parse(store.getItem('atlas.voice') || '{}')); } catch (e) { /* first visit */ }
    const V = { prefs, natural: 'off', progress: 0, last: '', speaking: false, seq: 0, worker: null, ctx: null, src: null, wait: new Map(), nextId: 1, size: '92 MB' };
    const save = () => { try { store.setItem('atlas.voice', JSON.stringify(V.prefs)); } catch (e) { /* private mode */ } };
    const changed = () => { try { onChange(V); } catch (e) { /* the page decides what to redraw */ } };
    const synth = () => win.speechSynthesis || null;
    const supported = () => !!(synth() && win.SpeechSynthesisUtterance) || V.natural === 'ready';

    function stopAudio() {
      V.seq++;
      if (synth()) { try { synth().cancel(); } catch (e) { /* ignore */ } }
      if (V.src) { try { V.src.onended = null; V.src.stop(); } catch (e) { /* already stopped */ } V.src = null; }
      V.speaking = false;
    }
    function deviceSpeak(text, seq) {
      const s = synth(); if (!s || !win.SpeechSynthesisUtterance) return false;
      const u = new win.SpeechSynthesisUtterance(text);
      const v = pickDeviceVoice(s.getVoices ? s.getVoices() : []);
      if (v) { u.voice = v; u.lang = v.lang; } else u.lang = 'en-US';
      u.rate = RATE[V.prefs.speed] || 1;
      u.onstart = () => { if (seq === V.seq) V.speaking = true; };
      u.onend = u.onerror = () => { if (seq === V.seq) { V.speaking = false; } };
      s.speak(u); return true;
    }
    function playPCM(f32, sr, seq) {
      if (seq !== V.seq || !V.ctx) return;
      const buf = V.ctx.createBuffer(1, f32.length, sr); buf.copyToChannel(f32, 0);
      const src = V.ctx.createBufferSource(); src.buffer = buf; src.connect(V.ctx.destination);
      src.onended = () => { if (V.src === src) { V.src = null; V.speaking = false; } };
      V.src = src; V.speaking = true; src.start();
    }
    function naturalSpeak(text, seq) {
      const id = V.nextId++;
      V.wait.set(id, { seq, text });
      V.worker.postMessage({ type: 'say', id, text, voice: V.prefs.voice, speed: RATE[V.prefs.speed] || 1 });
    }
    function failNatural(msg) {
      V.natural = 'failed'; V.error = msg || ''; V.prefs.natural = false; save();
      try { if (V.worker) V.worker.terminate(); } catch (e) { /* ignore */ }
      V.worker = null;
      V.wait.forEach((w) => { if (w.seq === V.seq) deviceSpeak(w.text, w.seq); });   // whatever was waiting is spoken by the device voice
      V.wait.clear(); changed();
    }
    function loadNatural() {
      if (V.natural === 'loading' || V.natural === 'ready') return;
      if (typeof win.Worker === 'undefined') { failNatural('no worker'); return; }
      V.natural = 'loading'; V.progress = 0; V.error = ''; changed();
      try { V.worker = new win.Worker(base + 'kokoro-worker.js'); } catch (e) { failNatural(String(e)); return; }
      let lastPct = -1;
      V.worker.onmessage = (e) => {
        const m = e.data || {};
        if (m.type === 'progress' && m.p && m.p.status === 'progress' && /\.onnx$/.test(m.p.file || '')) {
          const pct = Math.round(m.p.progress || 0); if (pct !== lastPct && (pct % 5 === 0 || pct === 100)) { lastPct = pct; V.progress = pct; changed(); }
        } else if (m.type === 'ready') { V.natural = 'ready'; changed(); }
        else if (m.type === 'audio') { const w = V.wait.get(m.id); V.wait.delete(m.id); if (w) playPCM(m.audio, m.sr, w.seq); }
        else if (m.type === 'error') { if (m.id) { const w = V.wait.get(m.id); V.wait.delete(m.id); if (w) deviceSpeak(w.text, w.seq); } else failNatural(m.message); }
      };
      V.worker.onerror = () => failNatural('worker error');
      V.worker.postMessage({ type: 'init', base });
    }
    // Must run inside a tap: phones only allow audio after one.
    function unlock() {
      try { const AC = win.AudioContext || win.webkitAudioContext; if (AC && !V.ctx) V.ctx = new AC(); if (V.ctx && V.ctx.state === 'suspended') V.ctx.resume(); } catch (e) { /* the device voice still works */ }
      if (synth() && win.SpeechSynthesisUtterance) { try { const u = new win.SpeechSynthesisUtterance(' '); u.volume = 0; synth().speak(u); } catch (e) { /* ignore */ } }
      if (V.prefs.on && V.prefs.natural && V.natural === 'off') loadNatural();
    }
    // Waiting for the natural voice: the device voice speaks, so a step is never silent.
    function speak(text) {
      if (!V.prefs.on || !text) return false;
      V.last = text; stopAudio(); const seq = V.seq;
      if (V.natural === 'ready' && V.worker) { naturalSpeak(text, seq); return true; }
      return deviceSpeak(text, seq);
    }
    const api = {
      state: V,
      isOn: () => !!V.prefs.on,
      supported,
      unlock,
      speak,
      repeat: (fallback) => { const t = V.last || fallback; if (!t) return false; const was = V.prefs.on; V.prefs.on = true; const r = speak(t); V.prefs.on = was; return r; },
      stop: stopAudio,
      setOn(on) { V.prefs.on = !!on; if (!on) stopAudio(); else unlock(); save(); changed(); },
      setSpeed(s) { if (RATE[s]) { V.prefs.speed = s; save(); changed(); } },
      setVoice(v) { V.prefs.voice = v; save(); changed(); },
      setNatural(on) {
        V.prefs.natural = !!on; save();
        if (on) { V.natural = V.natural === 'failed' ? 'off' : V.natural; unlock(); loadNatural(); }
        else { if (V.worker) { V.worker.terminate(); V.worker = null; } V.natural = 'off'; V.wait.clear(); }
        changed();
      },
    };
    return api;
  }

  const api = { words, create, pickDeviceVoice, RATE };
  g.AtlasVoice = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
