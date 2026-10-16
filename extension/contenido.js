// Jawdrop — botón «＋» en los resultados de Booking.
// Solo actúa si la pestaña se abrió desde la demo (lleva #escapadas=<clave> o window.name "escapadas:<clave>").
// No hace ninguna petición: lee lo que ya ves en la página y se lo manda a la pestaña que la abrió.
(function () {
  "use strict";

  function claveDeLaDemo() {
    var m = (location.hash || "").match(/escapadas=([^&]+)/);
    if (m) {
      var c = decodeURIComponent(m[1]);
      try { sessionStorage.setItem("escapadas_clave", c); } catch (e) {}
      return c;
    }
    try {
      var s = sessionStorage.getItem("escapadas_clave");
      if (s) return s;
    } catch (e) {}
    var n = (window.name || "").match(/^escapadas:(.+)$/);
    return n ? n[1] : "";
  }

  // Último importe en euros de un texto («€ 49 € 43» → 43; «1.234 €» → 1234).
  function ultimoEuro(texto) {
    var re = /(?:€\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?))|(?:(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*€)/g;
    var m, ultimo = null;
    while ((m = re.exec(texto || "")) !== null) {
      var bruto = m[1] || m[2];
      ultimo = parseFloat(bruto.replace(/\./g, "").replace(",", "."));
    }
    return ultimo;
  }

  function texto(el) { return el ? (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim() : ""; }

  function leerTarjeta(card) {
    var titulo = card.querySelector('[data-testid="title"]');
    var enlace = card.querySelector('a[data-testid="title-link"]') || card.querySelector('a[href*="/hotel/"]');
    var precioEl = card.querySelector('[data-testid="price-and-discounted-price"]');
    var nota = texto(card.querySelector('[data-testid="review-score"]'));
    var nNota = (nota.match(/(\d{1,2}[.,]\d)/) || [])[1] || "";
    var nOp = (nota.match(/([\d.]+)\s*(?:comentarios|opiniones|reviews)/i) || [])[1] || "";
    var unidades = card.querySelector('[data-testid="recommended-units"]');
    return {
      nombre: texto(titulo),
      enlace: enlace ? enlace.href : "",
      precio: ultimoEuro(texto(precioEl) || texto(card)),
      nota: nNota.replace(",", "."),
      opiniones: nOp.replace(/\./g, ""),
      distancia: texto(card.querySelector('[data-testid="distance"]')),
      zona: texto(card.querySelector('[data-testid="address"]')),
      habitacion: texto(unidades).slice(0, 220),
      resumen: texto(card).slice(0, 400)
    };
  }

  function aviso(msg, mal) {
    var d = document.getElementById("escapadas-aviso");
    if (!d) {
      d = document.createElement("div");
      d.id = "escapadas-aviso";
      d.style.cssText = "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:2147483647;" +
        "padding:12px 18px;border-radius:10px;font:600 15px/1.3 system-ui,sans-serif;color:#fff;" +
        "box-shadow:0 6px 24px rgba(0,0,0,.35);max-width:90vw";
      document.body.appendChild(d);
    }
    d.style.background = mal ? "#b3261e" : "#1f7a3d";
    d.textContent = msg;
    clearTimeout(aviso.t);
    aviso.t = setTimeout(function () { d.remove(); }, 6000);
  }

  function elegir(card, clave) {
    var hotel = leerTarjeta(card);
    if (!hotel.nombre || hotel.precio == null) {
      aviso("No he podido leer el nombre o el precio de este alojamiento. Dímelo y lo arreglo.", true);
      return;
    }
    var mensaje = { tipo: "escapadas-hotel", clave: clave, hotel: hotel };
    // 1) Camino principal: el fondo lo guarda en la cola, la demo lo recoge y esta pestaña se cierra.
    try { chrome.runtime.sendMessage(mensaje); } catch (e) {}
    // 2) Respaldo: si Booking ha dejado esta pestaña unida a la demo, también se lo digo directamente.
    try { if (window.opener && !window.opener.closed) window.opener.postMessage(mensaje, "*"); } catch (e) {}
    // 3) Y una copia en el portapapeles por si hiciera falta pegarlo en la demo.
    try { navigator.clipboard.writeText(JSON.stringify(mensaje)); } catch (e) {}
    aviso("✔ Elegido: " + hotel.nombre + " · " + hotel.precio + " €. Enviado a Jawdrop; cerrando esta pestaña…");
  }

  // Abajo a la izquierda de la foto, para no tapar la nota ni el precio.
  function colocar(b, card) {
    var img = card.querySelector("img");
    var cr = card.getBoundingClientRect();
    if (img) {
      var r = img.getBoundingClientRect();
      if (r.width > 40 && r.height > 40) {
        b.style.left = (r.left - cr.left + 8) + "px";
        b.style.top = (r.bottom - cr.top - 46) + "px";
        b.style.bottom = "auto";
        return;
      }
    }
    b.style.left = "8px"; b.style.top = "auto"; b.style.bottom = "8px";
  }

  function ponerBotones(clave) {
    var tarjetas = document.querySelectorAll('[data-testid="property-card"]');
    tarjetas.forEach(function (card) {
      if (card.getAttribute("data-escapadas")) return;
      card.setAttribute("data-escapadas", "1");
      if (getComputedStyle(card).position === "static") card.style.position = "relative";
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = "＋";
      b.title = "Elegir este alojamiento para Jawdrop";
      b.style.cssText = "position:absolute;z-index:50;width:38px;height:38px;border:0;" +
        "border-radius:8px;background:#1f7a3d;color:#fff;font:700 24px/1 system-ui,sans-serif;cursor:pointer;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.45);outline:2px solid #fff";
      colocar(b, card);
      var img = card.querySelector("img");
      if (img && !img.complete) img.addEventListener("load", function () { colocar(b, card); });
      window.addEventListener("resize", function () { colocar(b, card); });
      setTimeout(function () { colocar(b, card); }, 1200);
      b.addEventListener("click", function (ev) {
        ev.preventDefault(); ev.stopPropagation();
        elegir(card, clave);
      });
      card.appendChild(b);
    });
    return tarjetas.length;
  }

  var clave = claveDeLaDemo();
  if (!clave) return;

  var barra = document.createElement("div");
  barra.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:2147483646;background:#1f7a3d;color:#fff;" +
    "font:600 14px/1.2 system-ui,sans-serif;padding:6px 12px;text-align:center";
  barra.textContent = "Jawdrop: pulsa el botón ＋ verde del alojamiento que elijas";
  document.body.appendChild(barra);

  ponerBotones(clave);
  new MutationObserver(function () { ponerBotones(clave); })
    .observe(document.body, { childList: true, subtree: true });

  // Para las pruebas
  window.__escapadas = { leerTarjeta: leerTarjeta, ultimoEuro: ultimoEuro };
})();
