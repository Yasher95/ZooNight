// ZOO NIGHT — сборка для Steam (Electron). Игра — тот же index.html, Steam отвечает за игру с друзьями:
// лобби «только для друзей», приглашение через оверлей Steam (Shift+Tab) и пакеты через сеть Steam (обходит роутеры).
// App ID: 480 (тестовый Spacewar) — пока у игры нет своего. Свой вписать в APP_ID и в steam_appid.txt.
const { app, BrowserWindow, ipcMain, protocol, net } = require('electron');
const path = require('path');
const url = require('url');

const APP_ID = 480;
const GAME_DIR = path.join(__dirname, 'game');

let steam = null, steamErr = '';
try {
  const sw = require('steamworks.js');
  steam = sw.init(APP_ID);
  sw.electronEnableSteamOverlay();
} catch (e) { steamErr = String(e && e.message || e); }

app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required'); // музыка меню сразу
protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } }]);

let win = null, lobby = null;
const send = (ch, ...a) => { if (win && !win.isDestroyed()) win.webContents.send(ch, ...a); };
const sid = p => (p && p.steamId64 !== undefined ? p.steamId64 : p).toString();

function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 720, minWidth: 960, minHeight: 540, backgroundColor: '#000', title: 'ZOO NIGHT', autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, backgroundThrottling: false },
  });
  win.setMenu(null);
  win.loadURL('app://game/index.html');
  win.webContents.on('before-input-event', (e, i) => {
    if (i.type === 'keyDown' && i.key === 'F11') { win.setFullScreen(!win.isFullScreen()); e.preventDefault(); }
  });
}

// ---------- Steam: лобби, приглашения, пакеты ----------
ipcMain.handle('steam:info', () => steam
  ? { ok: true, name: steam.localplayer.getName(), id: sid(steam.localplayer.getSteamId()) }
  : { ok: false, err: steamErr || 'Steam не запущен' });

ipcMain.handle('steam:host', async () => {
  if (!steam) return null;
  if (lobby) { try { lobby.leave(); } catch (e) {} lobby = null; }
  lobby = await steam.matchmaking.createLobby(1 /* FriendsOnly */, 2);
  lobby.setData('game', 'zoonight');
  return lobby.id.toString();
});
ipcMain.handle('steam:invite', () => {
  if (!steam || !lobby) return false;
  steam.overlay.activateInviteDialog(lobby.id);
  return true;
});
ipcMain.handle('steam:join', async (e, id) => {
  if (!steam) return null;
  if (lobby) { try { lobby.leave(); } catch (e) {} lobby = null; }
  lobby = await steam.matchmaking.joinLobby(BigInt(id));
  return sid(lobby.getOwner());
});
ipcMain.handle('steam:leave', () => { if (lobby) { try { lobby.leave(); } catch (e) {} lobby = null; } });
ipcMain.on('steam:send', (e, to, str) => {
  if (!steam) return;
  try { steam.networking.sendP2PPacket(BigInt(to), 2 /* Reliable */, Buffer.from(str, 'utf8')); } catch (err) {}
});

function steamLoop() {
  if (!steam) return;
  const cb = steam.callback.SteamCallback;
  steam.callback.register(cb.P2PSessionRequest, v => steam.networking.acceptP2PSession(v.remote));
  steam.callback.register(cb.GameLobbyJoinRequested, v => send('steam:invited', v.lobby_steam_id.toString()));
  steam.callback.register(cb.LobbyChatUpdate, v => {
    if (!lobby || v.lobby.toString() !== lobby.id.toString()) return;
    send('steam:member', v.user_changed.toString(), v.member_state_change); // 0 — вошёл, 1..4 — вышел
  });
  // входящие пакеты — часто, чтобы не добавлять задержку
  setInterval(() => {
    let n;
    while ((n = steam.networking.isP2PPacketAvailable()) > 0) {
      const p = steam.networking.readP2PPacket(n);
      send('steam:data', sid(p.steamId), p.data.toString('utf8'));
    }
  }, 2);
}

app.whenReady().then(() => {
  protocol.handle('app', req => {
    const u = new URL(req.url);
    const f = path.normalize(path.join(GAME_DIR, decodeURIComponent(u.pathname)));
    if (!f.startsWith(GAME_DIR)) return new Response('', { status: 403 });
    return net.fetch(url.pathToFileURL(f).toString());
  });
  createWindow();
  steamLoop();
  if (process.env.ZN_SELFTEST) selfTest(process.env.ZN_SELFTEST); // проверка сборки без окна: Steam, страница, лобби
  // запуск игры по приглашению, когда она была закрыта: Steam передаёт +connect_lobby <id>
  const i = process.argv.indexOf('+connect_lobby');
  if (i >= 0 && process.argv[i + 1]) win.webContents.once('did-finish-load', () => send('steam:invited', process.argv[i + 1]));
});
function selfTest(outFile) {
  win.hide();
  win.webContents.once('did-finish-load', () => setTimeout(async () => {
    const r = { steam: !!steam, steamErr };
    try {
      r.page = await win.webContents.executeJavaScript(`({phase:G.phase,steamOn:STEAM.on,steamOk:STEAM.ok,name:STEAM.name,chars:CH.length,imgs:document.images.length})`);
      r.audio = await win.webContents.executeJavaScript(`(audioInit(),new Promise(res=>setTimeout(()=>res(Object.keys(BUFS).length),2500)))`);
      if (steam) { const l = await steam.matchmaking.createLobby(1, 2); r.lobby = l.id.toString(); r.owner = sid(l.getOwner()) === sid(steam.localplayer.getSteamId()); l.leave(); }
    } catch (e) { r.err = String(e && e.message || e); }
    require('fs').writeFileSync(outFile, JSON.stringify(r, null, 1));
    app.quit();
  }, 3000));
}
app.on('window-all-closed', () => { if (lobby) try { lobby.leave(); } catch (e) {} app.quit(); });
