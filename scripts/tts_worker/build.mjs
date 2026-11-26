import { build } from 'esbuild'; import fs from 'fs';
const patch = { name: 'local-voices', setup(b) { b.onLoad({ filter: /kokoro-js[\\/]dist[\\/]kokoro\.js$/ }, (a) => {
  let t = fs.readFileSync(a.path, 'utf8'); const from = 'https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/voices/';
  if (!t.includes(from)) throw new Error('voice URL not found'); return { contents: t.replace(from, '${globalThis.__KOKORO_BASE}models/onnx-community/Kokoro-82M-v1.0-ONNX/voices/'), loader: 'js' }; }); } };
await build({ entryPoints: ['worker.src.js'], bundle: true, format: 'iife', platform: 'browser', outfile: 'kokoro-worker.js', minify: true, plugins: [patch], logLevel: 'info', define: { 'process.env.NODE_ENV': '"production"' } });
