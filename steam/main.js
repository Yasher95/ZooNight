// ZOO NIGHT — сборка для Steam (Electron). Игра — тот же index.html, Steam отвечает за игру с друзьями:
// лобби «только для друзей», приглашение (ссылка для чата Steam / «Присоединиться» в списке друзей) и пакеты через
// сеть Steam (обходит роутеры). Steam API работает в отдельном процессе steamworker.js — иначе Steam Input
// тестового App ID 480 забирает геймпад у окна игры.
// App ID: 480 (тестовый Spacewar) — пока у игры нет своего. Свой вписать в APP_ID и в steam_appid.txt.
const { app, BrowserWindow, ipcMain, protocol, net, utilityProcess } = require('electron');
const path = require('path');
const url = require('url');
const fs = require('fs');
const { Readable } = require('stream');
const MIME = { '.mp4': 'video/mp4', '.mp3': 'audio/mpeg', '.png': 'image/png', '.jpg': 'image/jpeg', '.html': 'text/html' };

const APP_ID = 480;
const GAME_DIR = path.join(__dirname, 'game');

app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required'); // музыка меню сразу
protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } }]);

let win = null, worker = null, reqId = 0;
const pending = new Map();
const send = (ch, ...a) => { if (win && !win.isDestroyed()) win.webContents.send(ch, ...a); };

function startWorker() {
  worker = utilityProcess.fork(path.join(__dirname, 'steamworker.js'), [], { env: { ...process.env, ZN_APPID: String(APP_ID) }, serviceName: 'ZooNight Steam' });
  worker.on('message', m => {
    if (m.id !== undefined) { const p = pending.get(m.id); if (p) { pending.delete(m.id); m.e ? p.reject(new Error(m.e)) : p.resolve(m.r); } return; }
    send('steam:' + m.t, ...m.a);
  });
  worker.on('exit', () => { worker = null; for (const p of pending.values()) p.reject(new Error('Steam остановлен')); pending.clear(); });
}
const call = (t, ...a) => new Promise((resolve, reject) => {
  if (!worker) return reject(new Error('Steam остановлен'));
  const id = ++reqId; pending.set(id, { resolve, reject }); worker.postMessage({ id, t, a });
});

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

ipcMain.handle('steam:info', () => call('info').catch(e => ({ ok: false, err: e.message })));
ipcMain.handle('steam:host', () => call('host'));
ipcMain.handle('steam:invite', () => call('invite').catch(() => false));
ipcMain.handle('steam:join', (e, id) => call('join', id));
ipcMain.handle('steam:leave', () => call('leave').catch(() => false));
ipcMain.on('steam:send', (e, to, s) => { if (worker) worker.postMessage({ t: 'send', to, s }); });

app.whenReady().then(() => {
  protocol.handle('app', req => {
    const u = new URL(req.url);
    const f = path.normalize(path.join(GAME_DIR, decodeURIComponent(u.pathname)));
    if (!f.startsWith(GAME_DIR)) return new Response('', { status: 403 });
    // видео читается кусками (Range) — без этого ролики победы не играют (ошибка декодирования)
    const range = req.headers.get('range');
    if (range && fs.existsSync(f)) {
      const size = fs.statSync(f).size, m = /bytes=(\d*)-(\d*)/.exec(range) || [];
      const start = m[1] ? +m[1] : 0, end = Math.min(m[2] ? +m[2] : size - 1, size - 1);
      if (start >= size) return new Response('', { status: 416, headers: { 'Content-Range': `bytes */${size}` } });
      return new Response(Readable.toWeb(fs.createReadStream(f, { start, end })), {
        status: 206,
        headers: { 'Content-Type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream', 'Content-Range': `bytes ${start}-${end}/${size}`,
          'Content-Length': String(end - start + 1), 'Accept-Ranges': 'bytes' },
      });
    }
    return net.fetch(url.pathToFileURL(f).toString());
  });
  startWorker();
  createWindow();
  // запуск по приглашению, когда игра была закрыта: Steam передаёт +connect_lobby <id>
  const i = process.argv.indexOf('+connect_lobby');
  if (i >= 0 && process.argv[i + 1]) win.webContents.once('did-finish-load', () => setTimeout(() => send('steam:invited', process.argv[i + 1]), 1500));
  if (process.env.ZN_SELFTEST) selfTest(process.env.ZN_SELFTEST); // проверка сборки без окна
});

function selfTest(outFile) {
  win.hide();
  win.webContents.once('did-finish-load', () => setTimeout(async () => {
    const r = {};
    try {
      r.info = await call('info');
      r.page = await win.webContents.executeJavaScript(`({phase:G.phase,steamOn:STEAM.on,steamOk:STEAM.ok,name:STEAM.name})`);
      r.audio = await win.webContents.executeJavaScript(`(audioInit(),new Promise(res=>setTimeout(()=>res(Object.keys(BUFS).length),2500)))`);
      r.video = await win.webContents.executeJavaScript(`(G.mode=1,G.sel=[6,4],startMatch(),F[0].wins=2,G.phase='end',G.t=0,vidStart(CH[6]),new Promise(res=>setTimeout(()=>{const v=VID.el;res(v?{done:VID.done,rs:v.readyState,t:v.currentTime,err:v.error&&v.error.code,w:v.videoWidth}:'no');vidStop();G.phase='menu';},2500)))`);
      r.videoBlob = await win.webContents.executeJavaScript(`fetch('assets/win_pit.mp4').then(x=>x.blob()).then(b=>new Promise(res=>{const v=document.createElement('video');v.muted=true;v.src=URL.createObjectURL(b);v.play().catch(()=>{});setTimeout(()=>res({size:b.size,rs:v.readyState,t:v.currentTime,err:v.error&&v.error.code,msg:v.error&&v.error.message}),2500);}))`);
      r.codecs = await win.webContents.executeJavaScript(`({h264:MediaSource.isTypeSupported('video/mp4; codecs="avc1.640028"'),aac:MediaSource.isTypeSupported('audio/mp4; codecs="mp4a.40.2"'),canPlay:document.createElement('video').canPlayType('video/mp4; codecs="avc1.640028, mp4a.40.2"')})`);
      if (r.info.ok) { r.host = await call('host'); r.leave = await call('leave'); }
    } catch (e) { r.err = String(e && e.message || e); }
    require('fs').writeFileSync(outFile, JSON.stringify(r, null, 1));
    app.quit();
  }, 3000));
}
app.on('window-all-closed', () => { if (worker) { worker.postMessage({ id: -1, t: 'leave' }); setTimeout(() => { try { worker.kill(); } catch (e) {} app.quit(); }, 200); } else app.quit(); });
