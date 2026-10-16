// Jawdrop — puente en la página de la demo.
// Recoge de la cola los hoteles elegidos en Booking y se los entrega a la página de la demo
// (con window.postMessage): al cargar, en cuanto llegan, al volver a esta pestaña y cada segundo.
(function () {
  "use strict";
  if (!document.getElementById("lista") || !document.getElementById("cal")) return;   // no es la demo

  var ocupado = false;
  function entregar() {
    if (ocupado) return;
    try {
      ocupado = true;
      chrome.storage.local.get({ escapadas_cola: [] }, function (d) {
        ocupado = false;
        var cola = (d && d.escapadas_cola) || [];
        if (!cola.length) return;
        cola.forEach(function (x) {
          window.postMessage({ tipo: "escapadas-hotel", clave: x.clave, hotel: x.hotel }, "*");
        });
        try { chrome.storage.local.set({ escapadas_cola: [] }); } catch (e) {}
      });
    } catch (e) { ocupado = false; }   // la extensión se recargó: esta pestaña necesita F5
  }

  entregar();
  try {
    chrome.storage.onChanged.addListener(function (cambios, area) {
      if (area === "local" && cambios.escapadas_cola) entregar();
    });
  } catch (e) {}
  document.addEventListener("visibilitychange", function () { if (!document.hidden) entregar(); });
  window.addEventListener("focus", entregar);
  setInterval(entregar, 1000);
  document.documentElement.setAttribute("data-escapadas-puente", "1");
})();
