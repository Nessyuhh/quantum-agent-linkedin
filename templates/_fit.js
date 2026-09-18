// Ajuste automatiquement la taille des gros titres pour qu'ils tiennent dans
// le nombre de lignes prevu. Les textes generes ont une longueur variable :
// sans ca, une phrase trop longue casse la mise en page du visuel.
(function () {
  function fit(el) {
    var lines = parseInt(el.dataset.fitLines || '0', 10) ||
                ((el.innerHTML.match(/<br/gi) || []).length + 1);
    var min = parseFloat(el.dataset.fitMin || '40');
    var size = parseFloat(getComputedStyle(el).fontSize);
    for (var i = 0; i < 400 && size > min; i++) {
      var lh = parseFloat(getComputedStyle(el).lineHeight) || size * 1.2;
      if (el.getBoundingClientRect().height <= lines * lh + 2) break;
      size -= 2;
      el.style.fontSize = size + 'px';
    }
  }
  function run() {
    document.querySelectorAll('[data-fit]').forEach(fit);
    window.__fitDone = true;
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(run).catch(run);
  } else {
    run();
  }
})();
