// Схватка: WebSocket relay for online duels (the game itself is on GitHub Pages).
const http=require('http'),fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const {WebSocketServer}=require('ws');
const bot=require('./bot');
const PORT=process.env.PORT||8080,ROOT=path.join(__dirname,'docs');
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.json':'application/json','.txt':'text/plain; charset=utf-8','.jpg':'image/jpeg','.png':'image/png','.mp3':'audio/mpeg','.svg':'image/svg+xml','.ico':'image/x-icon'};
const gzCache=new Map();
const server=http.createServer((req,res)=>{
  if(bot.handles(req))return bot.handle(req,res);
  let u=decodeURIComponent((req.url||'/').split('?')[0]);if(u==='/')u='/index.html';
  if(u==='/health'||(u==='/index.html'&&!fs.existsSync(ROOT))){res.setHeader('access-control-allow-origin','*');res.writeHead(200,{'content-type':'text/plain'});return res.end('ok')}
  const f=path.normalize(path.join(ROOT,u));if(!f.startsWith(ROOT)){res.writeHead(403);return res.end()}
  fs.stat(f,(err,st)=>{if(err||!st.isFile()){res.writeHead(404);return res.end('Not found')}
    const ext=path.extname(f),type=MIME[ext]||'application/octet-stream';
    const headers={'content-type':type,'cache-control':ext==='.html'?'no-cache':'public, max-age=604800'};
    const gz=/gzip/.test(req.headers['accept-encoding']||'')&&['.html','.js','.css','.json','.txt'].includes(ext);
    if(gz){const key=f+':'+st.mtimeMs;let buf=gzCache.get(key);if(!buf){buf=zlib.gzipSync(fs.readFileSync(f),{level:6});gzCache.set(key,buf)}
      headers['content-encoding']='gzip';headers['content-length']=buf.length;res.writeHead(200,headers);return res.end(buf)}
    if(ext==='.mp3'&&req.headers.range){const m=/bytes=(\d*)-(\d*)/.exec(req.headers.range);const start=+m[1]||0,end=m[2]?+m[2]:st.size-1;
      res.writeHead(206,{...headers,'accept-ranges':'bytes','content-range':`bytes ${start}-${end}/${st.size}`,'content-length':end-start+1});return fs.createReadStream(f,{start,end}).pipe(res)}
    headers['content-length']=st.size;if(ext==='.mp3')headers['accept-ranges']='bytes';res.writeHead(200,headers);fs.createReadStream(f).pipe(res)});
});
// --- relay: rooms of peers, each peer keeps a small presence object; everyone in a room gets the whole room ~30 times a second
const wss=new WebSocketServer({server,path:'/ws',maxPayload:16*1024});
const rooms=new Map();const dirty=new Set();
function room(n){if(!rooms.has(n))rooms.set(n,new Map());return rooms.get(n)}
wss.on('connection',ws=>{
  ws.id=crypto.randomBytes(8).toString('hex');ws.rooms=new Set(['lobby']);ws.alive=true;room('lobby').set(ws.id,{ws,p:{}});dirty.add('lobby');
  ws.send(JSON.stringify({t:'hello',id:ws.id}));
  ws.on('pong',()=>ws.alive=true);
  ws.on('message',raw=>{let d;try{d=JSON.parse(raw)}catch(e){return}
    const name=typeof d.room==='string'?d.room.slice(0,48):null;if(!name||!/^[a-z0-9][a-z0-9_.-]*$/i.test(name))return;
    if(d.t==='join'){if(ws.rooms.size>16)return;ws.rooms.add(name);room(name).set(ws.id,{ws,p:{}});dirty.add(name)}
    else if(d.t==='leave'){ws.rooms.delete(name);const r=rooms.get(name);if(r){r.delete(ws.id);if(!r.size)rooms.delete(name);else dirty.add(name)}}
    else if(d.t==='p'&&ws.rooms.has(name)){const r=room(name);const e=r.get(ws.id);if(e&&d.p&&typeof d.p==='object'){e.p=d.p;dirty.add(name)}}});
  ws.on('close',()=>{for(const n of ws.rooms){const r=rooms.get(n);if(r){r.delete(ws.id);if(!r.size)rooms.delete(n);else dirty.add(n)}}});
});
setInterval(()=>{for(const n of dirty){const r=rooms.get(n);if(!r)continue;const msg=JSON.stringify({t:'peers',room:n,peers:[...r].map(([id,e])=>({id,p:e.p}))});for(const [,e] of r)if(e.ws.readyState===1)e.ws.send(msg)}dirty.clear()},33);
setInterval(()=>{for(const ws of wss.clients){if(!ws.alive){ws.terminate();continue}ws.alive=false;try{ws.ping()}catch(e){}}},15000);
// --- Python-боты (зеркальный бот и напоминалка) работают в этом же сервисе
const {spawn}=require('child_process');
function startPyBots(){
  if(!fs.existsSync(path.join(__dirname,'bots','app.py')))return;
  if(!process.env.MIRROR_TOKEN&&!process.env.REMINDER_TOKEN){console.log('Python-боты: нет MIRROR_TOKEN/REMINDER_TOKEN — пропускаю');return}
  const env={...process.env,PYTHONPATH:path.join(__dirname,'pydeps'),PYTHONUNBUFFERED:'1',MALLOC_ARENA_MAX:'2',TG_BACKUP:'1'};delete env.PORT;
  const py=spawn('python3',[path.join(__dirname,'bots','app.py')],{env,stdio:'inherit'});
  py.on('exit',code=>{console.log('Python-боты остановились (код '+code+'), перезапуск через 15 с');setTimeout(startPyBots,15000)});
}
// --- бесплатный Render засыпает без входящих запросов: раз в 10 минут стучимся сами к себе
function keepAwake(){const u=process.env.RENDER_EXTERNAL_URL;if(!u)return;
  setInterval(()=>{fetch(u.replace(/\/$/,'')+'/health').catch(()=>{})},10*60*1000)}
server.listen(PORT,()=>{console.log('Схватка on :'+PORT);bot.setup();startPyBots();keepAwake()});
