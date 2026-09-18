// Mise a l'echelle de la composition centrale.
//
// Principe : le bloc central porte UNE taille de police de reference, et tout
// ce qu'il contient est dimensionne en em par rapport a elle. On cherche par
// dichotomie la plus grande valeur qui ne debode pas de la zone. Le resultat
// remplit le cadre au lieu de flotter au milieu du vide.
//
// L'erreur de la version precedente etait de ne savoir que reduire, avec une
// hauteur estimee a partir d'un nombre de lignes suppose. Ici on mesure la
// zone reelle, et on grandit autant que possible.
(function () {
  function debode(bloc, zone) {
    return bloc.scrollWidth > zone.clientWidth + 1 ||
           bloc.scrollHeight > zone.clientHeight + 1;
  }

  function ajuster(bloc) {
    var zone = bloc.closest("[data-fit-zone]") || bloc.parentElement;
    var min = parseFloat(bloc.dataset.fitMin || "20");
    var max = parseFloat(bloc.dataset.fitMax || "260");
    var cible = parseFloat(bloc.dataset.fitFill || "0.94");  // marge de respiration

    // Verrou de securite : si meme le minimum debode, on s'y tient.
    bloc.style.fontSize = min + "px";
    if (debode(bloc, zone)) return;

    var bas = min, haut = max, garde = min;
    for (var i = 0; i < 26; i++) {
      var milieu = (bas + haut) / 2;
      bloc.style.fontSize = milieu + "px";
      if (debode(bloc, zone)) {
        haut = milieu;
      } else {
        garde = milieu;
        bas = milieu;
      }
    }
    bloc.style.fontSize = (garde * cible) + "px";
  }

  function lancer() {
    document.querySelectorAll("[data-fit]").forEach(ajuster);
    window.__fitDone = true;
  }

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(lancer).catch(lancer);
  } else {
    lancer();
  }
})();
