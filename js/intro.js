/* Intro animada: una vez por sesión; se salta con clic, Enter o Escape. */
(function () {
  var intro = document.getElementById("intro");
  if (!intro) return;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var seen = false;
  try { seen = sessionStorage.getItem("tbf-intro") === "1"; } catch (e) { /* almacenamiento bloqueado */ }
  if (seen || reduce) return;

  intro.hidden = false;
  document.documentElement.style.overflow = "hidden";
  var done = false;
  function close() {
    if (done) return;
    done = true;
    try { sessionStorage.setItem("tbf-intro", "1"); } catch (e) { /* sin almacenamiento */ }
    intro.classList.add("is-out");
    document.documentElement.style.overflow = "";
    document.removeEventListener("keydown", onKey);
    setTimeout(function () { intro.hidden = true; }, 600);
  }
  function onKey(e) {
    if (e.key === "Enter" || e.key === "Escape" || e.key === " ") { e.preventDefault(); close(); }
  }
  intro.addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  setTimeout(close, 2600);
})();
