/* Openway Assistant: photo questions. The photo is shrunk and re-drawn on a canvas in the browser, which drops
   all metadata (including location), and is used for one question only. Nothing is stored. */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const MAX_SIDE = 768, QUALITY = 0.8;
  async function load(file) {
    if (typeof createImageBitmap === 'function') {
      try { return await createImageBitmap(file, { imageOrientation: 'from-image' }); } catch (e) { /* fall through to <img> */ }
    }
    return await new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file), img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('unreadable')); };
      img.src = url;
    });
  }
  /** -> {dataUrl, width, height, bytes}. Throws an Error with a plain-words message. */
  async function shrink(file) {
    if (!file || !/^image\//.test(file.type)) throw new Error('That file is not a picture. Please choose a photo.');
    let bmp;
    try { bmp = await load(file); } catch (e) { throw new Error('I could not read that picture. Try a different photo.'); }
    const w0 = bmp.width || bmp.naturalWidth, h0 = bmp.height || bmp.naturalHeight;
    const k = Math.min(1, MAX_SIDE / Math.max(w0, h0));
    const w = Math.max(1, Math.round(w0 * k)), h = Math.max(1, Math.round(h0 * k));
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    c.getContext('2d').drawImage(bmp, 0, 0, w, h);
    if (bmp.close) bmp.close();
    const dataUrl = c.toDataURL('image/jpeg', QUALITY);
    return { dataUrl, width: w, height: h, bytes: Math.round(dataUrl.length * 0.75) };
  }
  const Ph = { shrink, MAX_SIDE };
  O.photo = Ph;
  if (typeof module !== 'undefined') module.exports = Ph;
})(typeof globalThis !== 'undefined' ? globalThis : this);
