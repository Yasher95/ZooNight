// Сборка ZOO NIGHT для Steam: копирует игру (index.html + assets) в game/, упаковывает Electron в dist/ и делает zip.
// Запуск: Y:\tools\node\node.exe build.js   (из папки steam)
const fs = require('fs'), path = require('path'), { execSync } = require('child_process');
const { packager } = require('@electron/packager');

const ROOT = path.resolve(__dirname, '..'), GAME = path.join(__dirname, 'game'), DIST = path.join(__dirname, 'dist');
const APP_ID = 480;

(async () => {
  fs.rmSync(GAME, { recursive: true, force: true });
  fs.mkdirSync(GAME, { recursive: true });
  fs.copyFileSync(path.join(ROOT, 'index.html'), path.join(GAME, 'index.html'));
  fs.cpSync(path.join(ROOT, 'assets'), path.join(GAME, 'assets'), { recursive: true });

  // чистим только свою папку сборки (в dist может лежать распакованная и запущенная копия игры)
  fs.mkdirSync(DIST, { recursive: true });
  fs.rmSync(path.join(DIST, 'ZooNight-win32-x64'), { recursive: true, force: true });
  const [out] = await packager({
    dir: __dirname, out: DIST, name: 'ZooNight', platform: 'win32', arch: 'x64', overwrite: true, asar: false, prune: true,
    ignore: [/^\/dist($|\/)/, /^\/build\.js$/, /^\/README/],
    appCopyright: 'ZOO NIGHT', win32metadata: { ProductName: 'ZOO NIGHT', FileDescription: 'ZOO NIGHT' },
  });
  fs.writeFileSync(path.join(out, 'steam_appid.txt'), String(APP_ID));
  fs.writeFileSync(path.join(out, 'КАК ИГРАТЬ ПО СЕТИ.txt'),
`ZOO NIGHT — игра с другом через Steam

1. Steam должен быть запущен у обоих (войти в свой аккаунт).
2. Оба запускают ZooNight.exe. В Steam у вас будет написано «играет в Spacewar» — это тестовый номер игры, так и должно быть.
3. Один открывает в меню «Игра по сети» и жмёт [3] / △ «Пригласить друга из Steam».
   Ссылка-приглашение сразу копируется — вставь её другу в чат Steam (Ctrl+V).
4. Друг (игра у него уже запущена) жмёт на ссылку в чате Steam — или в списке друзей Steam жмёт на тебя →
   «Присоединиться к игре». Игра сама зайдёт в лобби.

F11 — полный экран. Если Steam не запущен, работает обычная игра по коду комнаты.
`, 'utf8');
  const zip = path.join(DIST, 'ZooNight-Steam-win64.zip');
  execSync(`powershell -NoProfile -Command "Compress-Archive -Path '${out}\\*' -DestinationPath '${zip}' -Force"`, { stdio: 'inherit' });
  console.log('BUILD OK', out, zip);
})().catch(e => { console.error(e); process.exit(1); });
