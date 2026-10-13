// Telegram-бот «Схватка»: открывает игру кнопкой, работает через webhook на этом же сервере.
// Токен НЕ хранится в коде: его задают на Render в Environment как BOT_TOKEN.
const fs = require('fs'), path = require('path'), crypto = require('crypto');

const TOKEN = process.env.BOT_TOKEN || '';
const GAME_URL = process.env.GAME_URL || 'https://ars727973-ux.github.io/shvatka/';
const PUBLIC_URL = (process.env.RENDER_EXTERNAL_URL || process.env.PUBLIC_URL || 'https://shvatka-server.onrender.com').replace(/\/$/, '');
const API = (process.env.TG_API || 'https://api.telegram.org') + '/bot' + TOKEN + '/';
const HOOK_PATH = '/tg/' + crypto.createHash('sha256').update(TOKEN).digest('hex').slice(0, 24);
const SECRET = crypto.createHash('sha256').update('secret:' + TOKEN).digest('hex').slice(0, 32);
const COVER = path.join(__dirname, 'cover.jpg');

let botName = '', coverId = null;

async function api(method, body) {
  try {
    const opt = body instanceof FormData ? { method: 'POST', body } : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body || {}) };
    const r = await fetch(API + method, opt);
    const j = await r.json();
    if (!j.ok) console.log('TG', method, j.description);
    return j.result;
  } catch (e) { console.log('TG', method, e.message); }
}

const TEXT = {
  start: n =>
    `🥋 <b>Схватка</b> — 3D-файтинг один на один${n ? ', ' + n : ''}!\n\n` +
    `• 12 бойцов и 4 стиля: бокс, каратэ, муай-тай, тхэквондо\n` +
    `• 8 арен, вид сбоку, из-за спины и от первого лица\n` +
    `• Бой с ботом или онлайн с живым соперником\n` +
    `• Добей соперника эффектным фаталити 💀\n\n` +
    `Жми «Играть» 👇`,
  help:
    `🎮 <b>Управление</b>\n\n` +
    `<b>Телефон:</b> джойстик слева — ходьба, кнопки справа — быстрый, сильный удар, приём и блок.\n` +
    `<b>Компьютер:</b> WASD — ходьба, J / K / L — удары, Shift или Пробел — блок, C — камера, F — фаталити.\n\n` +
    `⚔️ <b>Онлайн:</b> «Онлайн» → «Найти соперника». Чтобы сыграть с другом, нажмите это одновременно.\n` +
    `💀 <b>Фаталити:</b> когда соперник шатается после последнего раунда — быстро жми кнопку «Фаталити».`,
  other: `Чтобы начать бой, нажми «Играть» 👇`,
};

function keyboard() {
  const share = 'https://t.me/share/url?url=' + encodeURIComponent('https://t.me/' + botName) +
    '&text=' + encodeURIComponent('Вызываю тебя на бой в «Схватке» 🥊 Заходи!');
  const rows = [[{ text: '🎮 Играть', web_app: { url: GAME_URL } }]];
  if (botName) rows.push([{ text: '⚔️ Позвать друга', url: share }]);
  rows.push([{ text: '❓ Как играть', callback_data: 'help' }]);
  return { inline_keyboard: rows };
}

async function sendCover(chat, caption) {
  const base = { chat_id: chat, caption, parse_mode: 'HTML', reply_markup: keyboard() };
  if (coverId) return api('sendPhoto', { ...base, photo: coverId });
  if (fs.existsSync(COVER)) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(base)) fd.append(k, typeof v === 'object' ? JSON.stringify(v) : String(v));
    fd.append('photo', new Blob([fs.readFileSync(COVER)], { type: 'image/jpeg' }), 'cover.jpg');
    const m = await api('sendPhoto', fd);
    if (m && m.photo) coverId = m.photo[m.photo.length - 1].file_id;
    return m;
  }
  return api('sendMessage', { chat_id: chat, text: caption, parse_mode: 'HTML', reply_markup: keyboard() });
}

async function onUpdate(u) {
  if (u.callback_query) {
    const q = u.callback_query;
    api('answerCallbackQuery', { callback_query_id: q.id });
    if (q.data === 'help' && q.message) api('sendMessage', { chat_id: q.message.chat.id, text: TEXT.help, parse_mode: 'HTML', reply_markup: keyboard() });
    return;
  }
  const m = u.message;
  if (!m || !m.chat || m.chat.type !== 'private') return;
  const t = (m.text || '').trim(), name = m.from && m.from.first_name ? m.from.first_name : '';
  if (t.startsWith('/start') || t.startsWith('/play')) return sendCover(m.chat.id, TEXT.start(name));
  if (t.startsWith('/help')) return api('sendMessage', { chat_id: m.chat.id, text: TEXT.help, parse_mode: 'HTML', reply_markup: keyboard() });
  return api('sendMessage', { chat_id: m.chat.id, text: TEXT.other, reply_markup: keyboard() });
}

async function setup() {
  if (!TOKEN) { console.log('BOT_TOKEN не задан — бот выключен, работает только онлайн-сервер'); return; }
  const me = await api('getMe');
  if (me) botName = me.username;
  await api('setWebhook', { url: PUBLIC_URL + HOOK_PATH, secret_token: SECRET, allowed_updates: ['message', 'callback_query'], drop_pending_updates: true });
  await api('setChatMenuButton', { menu_button: { type: 'web_app', text: 'Играть', web_app: { url: GAME_URL } } });
  await api('setMyCommands', { commands: [
    { command: 'start', description: 'Открыть «Схватку»' },
    { command: 'play', description: 'Начать бой' },
    { command: 'help', description: 'Как играть' },
  ] });
  await api('setMyShortDescription', { short_description: '3D-файтинг 1 на 1: бокс, каратэ, муай-тай, тхэквондо. Онлайн и фаталити.' });
  await api('setMyDescription', { description: '🥋 Схватка — 3D-файтинг один на один прямо в Telegram.\n\n12 бойцов, 4 боевых искусства, 8 арен, бой с ботом или онлайн с живым соперником и эффектные фаталити.\n\nНажми «Начать», чтобы выйти на ринг!' });
  console.log('Бот @' + botName + ' готов, webhook: ' + PUBLIC_URL + '/tg/…');
}

function handles(req) { return TOKEN && req.method === 'POST' && req.url === HOOK_PATH; }

function handle(req, res) {
  if (req.headers['x-telegram-bot-api-secret-token'] !== SECRET) { res.writeHead(403); return res.end(); }
  let body = '';
  req.on('data', c => { body += c; if (body.length > 1e6) req.destroy(); });
  req.on('end', () => {
    res.writeHead(200); res.end('ok');
    try { onUpdate(JSON.parse(body)).catch(e => console.log('update', e.message)); } catch (e) {}
  });
}

module.exports = { setup, handles, handle };
