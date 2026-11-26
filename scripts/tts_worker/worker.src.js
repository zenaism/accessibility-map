// Natural-voice worker: Kokoro-82M (q8) running in the page with WASM. Everything is loaded from the page's own host.
import { env } from '@huggingface/transformers';
import { KokoroTTS } from 'kokoro-js';
const MODEL = 'onnx-community/Kokoro-82M-v1.0-ONNX';
let tts = null;
self.onmessage = async (e) => {
  const m = e.data;
  try {
    if (m.type === 'init') {
      const base = m.base;                       // e.g. https://host/data/map/tts/
      globalThis.__KOKORO_BASE = base;
      env.allowRemoteModels = false; env.allowLocalModels = true;
      env.localModelPath = base + 'models/';
      env.backends.onnx.wasm.wasmPaths = { mjs: base + 'wasm/ort-wasm-simd-threaded.mjs', wasm: base + 'wasm/ort-wasm-simd-threaded.wasm' };
      env.backends.onnx.wasm.numThreads = 1;     // no cross-origin isolation on GitHub Pages
      env.backends.onnx.wasm.proxy = false;
      tts = await KokoroTTS.from_pretrained(MODEL, { dtype: 'q8', device: 'wasm', progress_callback: (p) => self.postMessage({ type: 'progress', p }) });
      self.postMessage({ type: 'ready' });
    } else if (m.type === 'say') {
      const out = await tts.generate(m.text, { voice: m.voice || 'af_heart', speed: m.speed || 1 });
      const a = out.audio; self.postMessage({ type: 'audio', id: m.id, audio: a, sr: out.sampling_rate }, [a.buffer]);
    }
  } catch (err) { self.postMessage({ type: 'error', id: m.id, message: String(err && err.message || err) }); }
};
