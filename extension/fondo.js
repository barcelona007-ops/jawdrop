// Recibe el hotel elegido en Booking, lo deja en una cola (chrome.storage) para que lo recoja la demo
// y cierra la pestaña de Booking.
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (!msg || msg.tipo !== "escapadas-hotel") return;
  chrome.storage.local.get({ escapadas_cola: [] }, (d) => {
    const cola = (d.escapadas_cola || []).filter((x) => x.clave !== msg.clave);
    cola.push({ clave: msg.clave, hotel: msg.hotel, t: Date.now() });
    chrome.storage.local.set({ escapadas_cola: cola }, () => {
      if (sender.tab && sender.tab.id != null) chrome.tabs.remove(sender.tab.id);
    });
  });
});
