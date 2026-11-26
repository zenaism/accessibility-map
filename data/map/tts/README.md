# Natural voice files (spoken directions)

Served to the map page only when a person turns on "Natural voice". Nothing here is loaded from another site.

| File | What | Licence |
|---|---|---|
| `models/onnx-community/Kokoro-82M-v1.0-ONNX/onnx/model_quantized.onnx` (92 MB), `config.json`, `tokenizer*.json` | Kokoro-82M, int8 | Apache-2.0 (hexgrad/Kokoro; ONNX export by onnx-community) |
| `models/.../voices/af_heart.bin`, `am_michael.bin` | two voices (US female, US male), 0.5 MB each | Apache-2.0 |
| `kokoro-worker.js` (2.1 MB) | kokoro-js 1.2.1 + transformers.js 3.8.1 (+ phonemizer 1.2.1), bundled with esbuild; the one hard-coded voice URL is patched to this site | Apache-2.0 |
| `wasm/ort-wasm-simd-threaded.{mjs,wasm}` | onnxruntime-web (single-thread WebAssembly) | MIT |

Do not edit or re-commit the model: every version stays in git history. To rebuild the worker: `npm i kokoro-js esbuild`, run `scripts/tts_worker/build.mjs` on `worker.src.js` (same folder; needs `npm i kokoro-js esbuild` next to it), copy the two ort files.
Licences, including the GPL-3.0 part (eSpeak NG inside `kokoro-worker.js`): see `NOTICE.md`.
