// Мост между игрой (страница) и Steam (главный процесс). В браузерной версии window.steamNet нет — там своя сеть.
const { contextBridge, ipcRenderer } = require('electron');
const on = ch => cb => ipcRenderer.on(ch, (e, ...a) => cb(...a));
contextBridge.exposeInMainWorld('steamNet', {
  info: () => ipcRenderer.invoke('steam:info'),
  host: () => ipcRenderer.invoke('steam:host'),
  invite: () => ipcRenderer.invoke('steam:invite'),
  join: id => ipcRenderer.invoke('steam:join', id),
  leave: () => ipcRenderer.invoke('steam:leave'),
  send: (to, str) => ipcRenderer.send('steam:send', to, str),
  onData: on('steam:data'),       // (от кого, строка)
  onMember: on('steam:member'),   // (кто, 0 — вошёл / иначе вышел)
  onInvited: on('steam:invited'), // (id лобби) — друг пригласил, игрок принял
});
