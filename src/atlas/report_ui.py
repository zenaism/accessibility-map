"""The "Report a problem" form of the map (CSS + JavaScript, inserted into the map page by map_viewer.py).

Design choices (UX and accessibility):
  * One short screen, one job. Three questions: what kind of problem (tap one of five), what happened (a sentence is enough),
    and an optional photo. Contact details are optional and clearly explained.
  * A native <dialog>: the browser traps the keyboard focus inside, Escape closes it, the page behind is inert, screen
    readers announce it as a dialog. Focus goes to the heading on open and back to the button on close.
  * Large tap targets (44 px or more), 16 px text (no zoom on phones), labels and hints tied to fields, errors named in words
    in a summary and next to the field, never by colour alone, and the text is kept if sending fails.
  * Photo: "Take a photo" (phones open the camera) and "Choose a photo"; the photo is shrunk to about 300 KB and re-encoded in
    the browser, which also removes location data, and a preview with a Remove button is shown.
  * Drafts are saved on the device while typing, so closing the dialog by accident loses nothing.
  * The button only appears once the database answers report_ping(), i.e. after supabase/problem_reports.sql has been run.
Needs these globals from the map page: RATECFG, DEVICE, esc(), apiHeaders(), store.
"""

CSS = r"""
 /* report a problem */
 .rp-row{margin:.5rem 0 0} .report-btn{color:#374151}
 .rp-fab{position:absolute;left:12px;bottom:36px;z-index:1001}
 @media (max-width:720px){ .rp-fab{bottom:auto;top:12px} }  /* on phones the list sheet covers the bottom of the map */
 .rp-fab .report-btn{min-height:48px;padding:10px 16px;border-radius:24px;background:#fff;border:1.5px solid #9ca3af;box-shadow:0 2px 8px rgba(17,24,39,.25);font-weight:600;font-size:15.5px}
 dialog.rp{border:0;border-radius:16px;padding:0;width:min(560px,calc(100% - 24px));max-height:calc(100dvh - 24px);overflow:auto;
   box-shadow:0 10px 40px rgba(17,24,39,.35);color:var(--ink);background:#fff}
 dialog.rp::backdrop{background:rgba(17,24,39,.55)}
 .rp,.rp *{box-sizing:border-box}
 .rp-body{padding:20px 20px 22px} .rp h2{font-size:20px;line-height:1.25;margin:0 36px 2px 0;font-weight:650} .rp h2:focus{outline:none}
 .rp .rp-place{margin:0 0 14px;color:#374151;font-size:15px}
 .rp button,.rp .btn{min-height:44px;font-size:16px;padding:10px 16px;border-radius:12px}
 .rp .rp-x{position:absolute;top:10px;right:10px;min-height:44px;min-width:44px;padding:0;justify-content:center;font-size:22px;line-height:1;border-color:transparent;background:transparent}
 .rp fieldset{border:0;margin:0 0 16px;padding:0} .rp legend,.rp .lbl{font-weight:650;font-size:16px;padding:0;margin:0 0 6px;display:block}
 .rp .req{font-weight:400;color:#4b5563;font-size:14px}
 .rp .hint{margin:0 0 6px;color:#4b5563;font-size:14px}
 .rp-opt{display:flex;gap:12px;align-items:center;border:1.5px solid #d1d5db;border-radius:12px;padding:10px 14px;margin:0 0 8px;cursor:pointer;min-height:48px}
 .rp-more summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font-weight:600;font-size:16px}
 .rp-more .lbl{margin-top:4px}
 .rp details.priv summary{cursor:pointer;min-height:36px;display:flex;align-items:center}
 .rp-opt:hover{background:var(--soft)} .rp-opt input{margin:0;width:22px;height:22px;flex:none;accent-color:#111827}
 .rp-opt:has(input:checked){border:2.5px solid #111827;padding:8.5px 12.5px;background:#f3f4f6}
 .rp-opt b{display:block;font-weight:600;font-size:16px} .rp-opt small{display:block;color:#4b5563;font-size:14px;margin-top:2px}
 .rp textarea,.rp input[type=text]{width:100%;font:inherit;font-size:16px;padding:12px;border-radius:12px;border:1.5px solid #9ca3af;background:#fff;color:var(--ink)}
 .rp textarea{min-height:110px;resize:vertical} .rp textarea:focus,.rp input[type=text]:focus{outline:2.5px solid var(--focus);outline-offset:1px}
 .rp [aria-invalid=true]{border-color:#b91c1c;border-width:2px}
 .rp .count{margin:4px 0 0;font-size:13px;color:#4b5563;text-align:right}
 .rp .err{color:#991b1b;font-weight:600;margin:4px 0 0;font-size:14.5px}
 .rp .errsum{border:2px solid #b91c1c;background:#fef2f2;color:#7f1d1d;border-radius:12px;padding:12px 14px;margin:0 0 16px}
 .rp .errsum:focus{outline:2.5px solid var(--focus)} .rp .errsum ul{margin:6px 0 0;padding-left:20px} .rp .errsum a{color:#7f1d1d;font-weight:600}
 .rp-field{margin:0 0 16px}
 .rp-photo-btns{display:flex;gap:10px;flex-wrap:wrap} .rp-prev{display:flex;gap:12px;align-items:center;margin-top:10px;padding:10px;border:1px solid #d1d5db;border-radius:12px}
 .rp-prev img{width:84px;height:84px;object-fit:cover;border-radius:8px;flex:none;background:#f3f4f6} .rp-prev p{margin:0 0 6px;font-size:14px;color:#374151}
 .rp-photo-msg{margin:6px 0 0;font-size:14px} .rp-photo-msg.err{color:#991b1b}
 .rp-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px} .rp .primary[disabled]{opacity:.65;cursor:progress}
 .rp-hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
 .rp .priv{font-size:13.5px;color:#4b5563;margin:14px 0 0}
 .rp-ok h2{margin-bottom:8px} .rp-ref{font-size:18px;font-weight:700;letter-spacing:.06em;background:#f3f4f6;display:inline-block;padding:6px 12px;border-radius:10px}
 @media (max-width:600px){ dialog.rp{width:100%;max-width:none;margin:auto 0 0;border-radius:18px 18px 0 0;max-height:94dvh} .rp-body{padding:18px 16px 24px}}
 @media (prefers-reduced-motion:no-preference){ dialog.rp[open]{animation:rpin .16s ease-out} @keyframes rpin{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}} }
"""

JS = r"""
// ---------- report a problem (Supabase function submit_problem_report; the button shows once report_ping answers) ----------
const REPORT_KINDS = [
  ['blocked_or_broken', 'Blocked or broken', ''],
  ['wrong_info', 'Information is wrong', ''],
  ['less_accessible', 'Harder to use than shown', ''],
  ['missing_info', 'Something is missing', ''],
  ['other', 'Something else', ''],
];
let REPORT_OK = false;
const newId = () => (crypto.randomUUID ? crypto.randomUUID() : '10000000-1000-4000-8000-100000000000'.replace(/[018]/g,
  c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)));
function reportShow(){
  document.querySelectorAll('[data-report]').forEach(b => b.hidden = !REPORT_OK);
  document.querySelectorAll('[data-report-fallback]').forEach(b => b.hidden = REPORT_OK);
}
async function reportProbe(){
  if (!RATECFG) return false;
  const at = +(store.get('atlas-report-ok') || 0);
  if (at && Date.now() - at < 600000){ REPORT_OK = true; reportShow(); return true; }
  try {
    const r = await fetch(RATECFG.url + '/rest/v1/rpc/report_ping', {method:'POST', headers:apiHeaders({'Content-Type':'application/json'}), body:'{}'});
    REPORT_OK = r.ok;
    if (r.ok) store.set('atlas-report-ok', String(Date.now()));
  } catch (e) { REPORT_OK = false; }
  reportShow(); return REPORT_OK;
}
// The button. ctx = {link_id, name, region} for a place, or null for the map as a whole.
function reportButton(ctx, label){
  const b = document.createElement('button'); b.type = 'button'; b.className = 'ghost report-btn'; b.hidden = !REPORT_OK;
  b.setAttribute('data-report', '');
  b.innerHTML = `<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 17V3m0 0h9l-2 3.5L14 10H5" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    + `${label || 'Report a problem'}<span class="vh">${ctx ? ' with ' + esc(ctx.name) : ' with this map'}</span>`;
  b.onclick = () => openReport(ctx, b);
  return b;
}
const reportRow = it => { const p = document.createElement('p'); p.className = 'rp-row'; p.append(reportButton({link_id:it.p.link_id, name:it.p.name, region:it.p.region})); return p; };

async function shrinkPhoto(file){
  if (!/^image\//.test(file.type) && !/\.(jpe?g|png|webp|gif|heic|heif)$/i.test(file.name)) throw new Error('That file is not a photo.');
  let bmp;
  try { bmp = await createImageBitmap(file, {imageOrientation:'from-image'}); }
  catch (e) {
    bmp = await new Promise((ok, no) => { const im = new Image(); im.onload = () => ok(im);
      im.onerror = () => no(new Error('This photo format cannot be used here. Please try a JPEG or PNG, or take a new photo.'));
      im.src = URL.createObjectURL(file); });
  }
  const W = bmp.width || bmp.naturalWidth, H = bmp.height || bmp.naturalHeight;
  for (const max of [1280, 960, 720]){
    const k = Math.min(1, max / Math.max(W, H)), cv = document.createElement('canvas');
    cv.width = Math.max(1, Math.round(W * k)); cv.height = Math.max(1, Math.round(H * k));
    const g = cv.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, cv.width, cv.height); g.drawImage(bmp, 0, 0, cv.width, cv.height);
    for (const q of [0.8, 0.65, 0.5]){      // re-encoding drops all metadata, including GPS position
      const blob = await new Promise(r => cv.toBlob(r, 'image/jpeg', q));
      if (blob && blob.size <= 300000) return blob;
    }
  }
  throw new Error('This photo is too large to send. Please try a smaller one.');
}
const blobToB64 = blob => new Promise((ok, no) => { const f = new FileReader(); f.onload = () => ok(String(f.result).split(',')[1]); f.onerror = no; f.readAsDataURL(blob); });
const kb = n => n < 1024 ? n + ' bytes' : Math.round(n / 1024) + ' KB';

function openReport(ctx, opener){
  let dlg = document.getElementById('report-dialog');
  if (dlg) dlg.remove();
  dlg = document.createElement('dialog'); dlg.id = 'report-dialog'; dlg.className = 'rp';
  dlg.setAttribute('aria-labelledby', 'rp-title');
  document.body.append(dlg);
  const draftKey = 'atlas-report-draft-' + (ctx ? ctx.link_id : 'map');
  let draft = {}; try { draft = JSON.parse(store.get(draftKey)) || {}; } catch (e) {}
  const S = {id:newId(), photo:null, photoUrl:null, busy:false};
  const place = ctx ? esc(ctx.name) : 'This map';
  const touch = matchMedia('(pointer:coarse)').matches;
  dlg.innerHTML = `<div class="rp-body"><button type="button" class="rp-x" data-x aria-label="Close without sending">×</button>`
    + `<form novalidate><h2 id="rp-title" tabindex="-1">Report a problem</h2>`
    + `<p class="rp-place">${ctx ? 'About: <b>' + place + '</b>' : 'About this map and website'}</p>`
    + `<div class="errsum" id="rp-errs" role="alert" tabindex="-1" hidden></div>`
    + `<fieldset id="rp-kind"><legend>What is the problem?</legend>`
    + REPORT_KINDS.map(([v, t, h]) => `<label class="rp-opt"><input type="radio" name="kind" value="${v}"${draft.k === v ? ' checked' : ''}>`
        + `<span><b>${t}</b>${h ? `<small>${h}</small>` : ''}</span></label>`).join('')
    + `<p class="err" id="rp-kind-err" hidden></p></fieldset>`
    + `<div class="rp-field"><label class="lbl" for="rp-text">What happened?</label>`
    + `<textarea id="rp-text" rows="3" maxlength="1000" placeholder="For example: the ramp is blocked" aria-describedby="rp-count"></textarea>`
    + `<p class="count" id="rp-count">0 of 1000 characters</p><p class="err" id="rp-text-err" hidden></p></div>`
    + `<div class="rp-field"><span class="lbl" id="rp-photo-l">Photo <span class="req">(optional)</span></span>`
    + `<div class="rp-photo-btns" role="group" aria-labelledby="rp-photo-l">`
    + (touch ? `<button type="button" data-cam>Take a photo</button>` : '')
    + `<button type="button" data-pick>${touch ? 'Choose a photo' : 'Choose a photo from this device'}</button></div>`
    + `<input type="file" accept="image/*" capture="environment" id="rp-cam" hidden><input type="file" accept="image/*" id="rp-file" hidden>`
    + `<div id="rp-prev" hidden></div><p class="rp-photo-msg" id="rp-pmsg" role="status" aria-live="polite"></p></div>`
    + `<details class="rp-field rp-more"${draft.c ? ' open' : ''}><summary>Want a reply?</summary>`
    + `<label class="lbl" for="rp-contact">Your email or phone <span class="req">(optional)</span></label>`
    + `<input type="text" id="rp-contact" maxlength="200" autocomplete="off"></details>`
    + `<div class="rp-hp" aria-hidden="true"><label>Website<input type="text" id="rp-web" tabindex="-1" autocomplete="off"></label></div>`
    + `<div class="rp-actions"><button type="submit" class="primary" id="rp-send">Send report</button><button type="button" data-x>Cancel</button></div>`
    + `<p class="priv" id="rp-status" role="status" aria-live="polite">Anonymous. Read only by the accessibility team.</p>`
    + `<details class="priv"><summary>How we use your report</summary><p>We use it only to find and fix accessibility problems. Only the accessibility team and the researchers read it. We keep reports for up to 24 months and never publish a photo or contact detail. Please do not write names, and avoid faces and number plates in photos. Location data is removed from photos. You can delete your report right after sending it.</p></details></form></div>`;
  const $ = id => dlg.querySelector('#' + id), form = dlg.querySelector('form'), text = $('rp-text'), contact = $('rp-contact');
  text.value = draft.t || ''; contact.value = draft.c || '';
  const kindNow = () => (form.querySelector('input[name=kind]:checked') || {}).value || '';
  const count = () => { $('rp-count').textContent = `${text.value.length} of 1000 characters`; };
  const keep = () => store.set(draftKey, JSON.stringify({k:kindNow(), t:text.value, c:contact.value}));
  count();
  text.addEventListener('input', () => { count(); keep(); }); contact.addEventListener('input', keep);
  form.addEventListener('change', e => { if (e.target.name === 'kind'){ keep(); $('rp-kind-err').hidden = true; } });
  const closeIt = () => { if (S.photoUrl) URL.revokeObjectURL(S.photoUrl); dlg.close(); };
  dlg.querySelectorAll('[data-x]').forEach(b => b.onclick = closeIt);
  dlg.addEventListener('close', () => { if (S.photoUrl) URL.revokeObjectURL(S.photoUrl); dlg.remove(); if (opener && document.contains(opener)) opener.focus(); });
  dlg.addEventListener('click', e => { if (e.target === dlg) closeIt(); });      // a tap on the dimmed background closes it

  const pmsg = $('rp-pmsg');
  const showPhoto = () => {
    const box = $('rp-prev');
    if (!S.photo){ box.hidden = true; box.innerHTML = ''; return; }
    box.hidden = false; box.className = 'rp-prev';
    box.innerHTML = `<img alt="Preview of the photo you added" src="${S.photoUrl}"><div><p>Photo ready (${kb(S.photo.size)}).</p><button type="button" data-rm>Remove photo</button></div>`;
    box.querySelector('[data-rm]').onclick = () => { if (S.photoUrl) URL.revokeObjectURL(S.photoUrl); S.photo = S.photoUrl = null; showPhoto();
      pmsg.className = 'rp-photo-msg'; pmsg.textContent = 'Photo removed.'; (dlg.querySelector('[data-pick]')).focus(); };
  };
  const take = async file => {
    if (!file) return;
    pmsg.className = 'rp-photo-msg'; pmsg.textContent = 'Preparing your photo…';
    try {
      const blob = await shrinkPhoto(file);
      if (S.photoUrl) URL.revokeObjectURL(S.photoUrl);
      S.photo = blob; S.photoUrl = URL.createObjectURL(blob); showPhoto(); pmsg.textContent = 'Photo added.';
    } catch (e) { pmsg.className = 'rp-photo-msg err'; pmsg.textContent = e.message || 'The photo could not be used.'; }
  };
  const cam = $('rp-cam'), pick = $('rp-file');
  cam.onchange = () => { take(cam.files[0]); cam.value = ''; }; pick.onchange = () => { take(pick.files[0]); pick.value = ''; };
  dlg.querySelector('[data-pick]').onclick = () => pick.click();
  const camBtn = dlg.querySelector('[data-cam]'); if (camBtn) camBtn.onclick = () => cam.click();

  const fail = list => {   // an error summary at the top (read out at once), links to each field, and a message at each field
    const box = $('rp-errs'); box.hidden = false;
    box.innerHTML = `<b>${list.length > 1 ? 'Please fix these ' + list.length + ' things' : 'Please fix this'} before sending:</b><ul>`
      + list.map(([id, msg]) => `<li><a href="#${id}">${msg}</a></li>`).join('') + '</ul>';
    box.querySelectorAll('a').forEach(a => a.onclick = e => { e.preventDefault(); const t = dlg.querySelector(a.getAttribute('href')) || $('rp-kind');
      (t.querySelector ? t.querySelector('input,textarea') || t : t).focus(); });
    box.focus();
  };
  form.addEventListener('submit', async e => {
    e.preventDefault(); if (S.busy) return;
    const errs = [], t = text.value.trim();
    $('rp-errs').hidden = true; $('rp-kind-err').hidden = $('rp-text-err').hidden = true; text.removeAttribute('aria-invalid');
    if (!kindNow()){ errs.push(['rp-kind', 'Choose the kind of problem.']); $('rp-kind-err').textContent = 'Choose the kind of problem.'; $('rp-kind-err').hidden = false; }
    if (t.length < 5){ errs.push(['rp-text', 'Tell us what happened (at least a few words).']); text.setAttribute('aria-invalid', 'true');
      $('rp-text-err').textContent = 'Tell us what happened (at least a few words).'; $('rp-text-err').hidden = false; }
    if (errs.length) return fail(errs);
    if (navigator.onLine === false){ return fail([['rp-send', 'You seem to be offline. Your text is kept: try again when you are connected.']]); }
    S.busy = true; const send = $('rp-send'); send.disabled = true; send.textContent = 'Sending…'; $('rp-status').textContent = 'Sending your report…';
    try {
      const photo = S.photo ? await blobToB64(S.photo) : null;
      const ref = await sendReport(ctx, {id:S.id, kind:kindNow(), text:t, contact:contact.value.trim(), photo, website:$('rp-web').value});
      store.set(draftKey, '');
      dlg.querySelector('.rp-body').innerHTML = `<button type="button" class="rp-x" data-x aria-label="Close">×</button><div class="rp-ok">`
        + `<h2 id="rp-title" tabindex="-1">Thank you. Your report was sent.</h2>`
        + `<p>The accessibility team will read it${ctx ? ' and check <b>' + place + '</b>' : ''}.</p>`
        + `<p>Your reference code: <span class="rp-ref">${esc(ref)}</span></p><p id="rp-del-msg" class="priv" role="status" aria-live="polite"></p>`
        + `<div class="rp-actions"><button type="button" class="primary" data-x>Close</button><button type="button" data-again>Report another problem</button><button type="button" data-del>Delete this report</button></div></div>`;
      dlg.querySelectorAll('[data-x]').forEach(b => b.onclick = closeIt);
      dlg.querySelector('[data-del]').onclick = async ev => {
        const b = ev.currentTarget; b.disabled = true;
        try { await deleteReport(S.id); dlg.querySelector('#rp-del-msg').textContent = 'Your report was deleted.'; b.hidden = true; }
        catch (e) { b.disabled = false; dlg.querySelector('#rp-del-msg').textContent = 'It could not be deleted just now. Please try again.'; }
      };
      dlg.querySelector('[data-again]').onclick = () => { closeIt(); setTimeout(() => openReport(ctx, opener), 0); };
      dlg.querySelector('#rp-title').focus();
    } catch (err){
      S.busy = false; send.disabled = false; send.textContent = 'Send report'; $('rp-status').textContent = '';
      fail([['rp-send', `The report could not be sent (${err.message}). Your text${S.photo ? ' and photo are' : ' is'} kept: please try again.`]]);
    }
  });
  dlg.showModal();
  $('rp-title').focus();
}
async function deleteReport(id){
  const r = await fetch(RATECFG.url + '/rest/v1/rpc/delete_problem_report',
    {method:'POST', headers:apiHeaders({'Content-Type':'application/json'}), body:JSON.stringify({p_report_id:id, p_device_id:DEVICE})});
  if (!r.ok) throw new Error('delete failed');
  return await r.json();
}
async function sendReport(ctx, v){
  const body = {p_report_id:v.id, p_device_id:DEVICE, p_category:v.kind, p_description:v.text,
    p_link_id:ctx ? ctx.link_id : null, p_place_name:ctx ? ctx.name : null, p_region:ctx ? ctx.region : null,
    p_contact:v.contact || null, p_photo_b64:v.photo || null, p_page_url:location.href.split('#')[0].slice(0, 300),
    p_user_agent:navigator.userAgent.slice(0, 300), p_website:v.website || ''};
  const r = await fetch(RATECFG.url + '/rest/v1/rpc/submit_problem_report',
    {method:'POST', headers:apiHeaders({'Content-Type':'application/json'}), body:JSON.stringify(body)});
  if (!r.ok){ let t = ''; try { t = (await r.json()).message; } catch (x) {} throw new Error(t || `the server said ${r.status}`); }
  return await r.json();
}
{ const slot = document.getElementById('rp-map'); if (slot && RATECFG) slot.append(reportButton(null, 'Report a problem')); }
reportProbe();
"""
