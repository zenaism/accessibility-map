# Third-party licences in this folder

This folder holds the files for the optional "Natural voice" (spoken directions, decision D-102). They are separate files that the map page loads in a Web Worker only when a person turns the voice on. The map page code itself does not contain them and talks to them only by messages.

| Part | Licence | Source |
|---|---|---|
| Kokoro-82M model and voices (`models/`) | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M, ONNX export https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX |
| kokoro-js, transformers.js (inside `kokoro-worker.js`) | Apache-2.0 (text: `LICENSE-kokoro-js-Apache-2.0.txt`) | https://github.com/hexgrad/kokoro, https://github.com/huggingface/transformers.js |
| onnxruntime-web (`wasm/`, and inside `kokoro-worker.js`) | MIT, Copyright (c) Microsoft Corporation | https://github.com/microsoft/onnxruntime |
| **eSpeak NG**, compiled to WebAssembly inside `kokoro-worker.js` through the `phonemizer` package | **GPL-3.0-or-later** (text: `LICENSE-GPL-3.0.txt`) | https://github.com/espeak-ng/espeak-ng, packaged by https://github.com/xenova/phonemizer.js |

**What this means.** `kokoro-worker.js` contains eSpeak NG, so that one file is distributed under the GPL-3.0-or-later. Its source is the three projects linked above plus the build recipe in `scripts/tts_worker/` (`worker.src.js`, `build.mjs`). The rest of this repository is MIT (see `/LICENSE`) and is not combined with it into one program: the page loads the worker as a separate file. If you copy `kokoro-worker.js` somewhere else, keep this notice and the GPL text with it. The `phonemizer` package labels itself Apache-2.0 and does not mention eSpeak NG's licence; the eSpeak NG project states the GPL.
This is the maintainers' reading, not legal advice. If the project is ever published beyond a research repository, ask the university's technology-transfer office.
