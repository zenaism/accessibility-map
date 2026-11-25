/* Theme boot (session B0). Runs in <head> before first paint, so there is no flash.
   Light is the default. The app never follows the device setting. The choice is kept on this device only.
   API: window.atlasTheme.get() -> "light" | "dark";  window.atlasTheme.set("light" | "dark") -> the theme now in use.
   set() also fires the event atlas:theme-changed on document, detail {theme}. */
(function (w) {
  var KEY = "atlas.theme", root = document.documentElement, cur = "light";
  function read() { try { return w.localStorage.getItem(KEY) === "dark" ? "dark" : "light"; } catch (e) { return "light"; } }
  function apply(t, announce) {
    cur = t === "dark" ? "dark" : "light";
    root.setAttribute("data-theme", cur);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute("content", cur === "dark" ? "#15252E" : "#FFFFFF");
    if (announce) {
      try { document.dispatchEvent(new CustomEvent("atlas:theme-changed", { detail: { theme: cur } })); } catch (e) { /* old browser */ }
    }
  }
  apply(read(), false);
  w.atlasTheme = {
    get: function () { return cur; },
    set: function (t) {
      t = t === "dark" ? "dark" : "light";
      if (t === cur) return cur;
      try { w.localStorage.setItem(KEY, t); } catch (e) { /* storage blocked: the choice lasts until the page closes */ }
      apply(t, true);
      return cur;
    }
  };
  w.addEventListener("storage", function (e) { if (e.key === KEY) { var t = read(); if (t !== cur) apply(t, true); } });
})(window);
