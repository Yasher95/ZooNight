// Steam в отдельном процессе. Зачем: игра идёт под тестовым App ID 480 (Spacewar), у которого в Steam своя
// поддержка геймпада — если Steam API живёт в процессе окна, Steam Input забирает геймпад и игра его не видит.
// Здесь окно игры для Steam — обычная программа (как браузер), а лобби и пакеты идут через этот процесс.
const port = process.parentPort;
const APP_ID = Number(process.env.ZN_APPID || 480);
let steam = null, err = '', lobby = null;
try { steam = require('steamworks.js').init(APP_ID); } catch (e) { err = String(e && e.message || e); }
const out = (t, ...a) => port.postMessage({ t, a });
const sid = p => (p && p.steamId64 !== undefined ? p.steamId64 : p).toString();
const leave = () => { if (lobby) { try { lobby.leave(); } catch (e) {} lobby = null; } };

const H = {
  async info() { return steam ? { ok: true, name: steam.localplayer.getName(), id: sid(steam.localplayer.getSteamId()), app: APP_ID } : { ok: false, err: err || 'Steam не запущен' }; },
  async host() {
    leave();
    lobby = await steam.matchmaking.createLobby(1 /* только друзья */, 2);
    lobby.setData('game', 'zoonight');
    steam.localplayer.setRichPresence('connect', '+connect_lobby ' + lobby.id.toString()); // «Присоединиться» в списке друзей
    return { lobby: lobby.id.toString(), link: `steam://joinlobby/${APP_ID}/${lobby.id}/${sid(steam.localplayer.getSteamId())}` };
  },
  async invite() { if (!lobby) return false; steam.overlay.activateInviteDialog(lobby.id); return true; },
  async join(id) { leave(); lobby = await steam.matchmaking.joinLobby(BigInt(id)); return sid(lobby.getOwner()); },
  async leave() { leave(); try { steam.localplayer.setRichPresence('connect', null); } catch (e) {} return true; },
};

port.on('message', async ({ data: m }) => {
  if (m.t === 'send') { // самый частый вызов — без ответа
    if (steam) try { steam.networking.sendP2PPacket(BigInt(m.to), 2 /* Reliable */, Buffer.from(m.s, 'utf8')); } catch (e) {}
    return;
  }
  let r = null, e = null;
  try { if (!steam && m.t !== 'info') throw new Error('Steam не запущен'); r = await H[m.t](...(m.a || [])); } catch (x) { e = String(x && x.message || x); }
  port.postMessage({ id: m.id, r, e });
});

if (steam) {
  const cb = steam.callback.SteamCallback;
  steam.callback.register(cb.P2PSessionRequest, v => steam.networking.acceptP2PSession(v.remote));
  steam.callback.register(cb.GameLobbyJoinRequested, v => out('invited', v.lobby_steam_id.toString()));
  steam.callback.register(cb.LobbyChatUpdate, v => { if (lobby && v.lobby.toString() === lobby.id.toString()) out('member', v.user_changed.toString(), v.member_state_change); });
  setInterval(() => {
    let n;
    while ((n = steam.networking.isP2PPacketAvailable()) > 0) { const p = steam.networking.readP2PPacket(n); out('data', sid(p.steamId), p.data.toString('utf8')); }
  }, 2);
}
