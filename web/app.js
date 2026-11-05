/* No cloud speech APIs, remote assets, HTML injection, or persisted bearer tokens. */
const $ = id => document.getElementById(id);
let token = window.__deviceToken || '', device=null, cfg=null, controller=null;
let socket=null, audioContext=null, media=null, processor=null, source=null, silence=null;
let speaking=false, talking=false, lastStatus=null;
window.provideNativeToken=function(value){window.__deviceToken=value;token=value;if(token)connect()};
const conversation='main';
async function api(path,opts={}){
  const headers={Authorization:'Bearer '+token,...opts.headers};
  if(opts.body && typeof opts.body!=='string'){opts.body=JSON.stringify(opts.body);headers['Content-Type']='application/json'}
  const r=await fetch('/api/'+path,{...opts,headers});
  if(!r.ok){let detail;try{detail=(await r.json()).detail}catch{}throw Error(detail||('Request failed: '+r.status))}
  return r.json();
}
function error(e){$('error').textContent=e.message||String(e)}
function native(action,data={}){if(window.webkit?.messageHandlers?.native){window.webkit.messageHandlers.native.postMessage({action,...data});return true}return false}
function message(role,text){const d=document.createElement('div');d.className='message '+role;const label=document.createElement('span');label.className='role';label.textContent=role==='assistant'?'Jarvis':'You';d.append(label,document.createTextNode(text));$('messages').append(d);$('messages').scrollTop=$('messages').scrollHeight}
async function connect(){
  try{token=window.__deviceToken||$('token').value.trim();const s=await api('status');device=s.device;$('login').hidden=true;$('workspace').hidden=false;
    $('connection').textContent='Connected securely';$('messages').replaceChildren();for(const m of await api('history?conversation='+conversation))message(m.role,m.content);
    native('saveToken',{token});await refresh();await memories();await settings();
  }catch(e){$('loginError').textContent=e.message;$('connection').textContent='Server unavailable'}
}
$('connect').onclick=connect;
$('chatForm').onsubmit=async e=>{e.preventDefault();const text=$('prompt').value.trim();if(!text||controller)return;$('prompt').value='';message('user',text);$('error').textContent='';controller=new AbortController();$('send').disabled=true;
  try{const r=await api('chat',{method:'POST',body:{text,conversation},signal:controller.signal});message('assistant',r.text);metrics(r.metrics);await refresh()}catch(e){if(e.name!=='AbortError')error(e)}finally{controller=null;$('send').disabled=false}
};
$('prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chatForm').requestSubmit()}};
function metrics(m){if(m)$('metrics').textContent=`Reply ${m.total_seconds?.toFixed(2)} s · First token ${m.first_token_seconds?.toFixed(2)} s · ${m.tokens_per_second?.toFixed(1)} tokens/s`}
for(const b of document.querySelectorAll('nav button'))b.onclick=()=>{for(const p of document.querySelectorAll('.panel'))p.hidden=p.id!==b.dataset.panel;for(const n of document.querySelectorAll('nav button'))n.classList.toggle('selected',n===b)};
async function refresh(){if(!device)return;try{const s=await api('status');lastStatus=s;$('model').textContent=(s.active_model||s.model)+(s.busy?' · Thinking':'');$('storage').textContent=s.ssd_online?'SSD connected':'SSD unavailable';$('connection').textContent=s.runtime_online?'Local AI online':'Model server unavailable';
  $('status').textContent=JSON.stringify({host:s.runtime_status,model:s.model,external_storage:s.ssd_online,devices:s.devices.map(d=>({name:d.name,last_seen:d.last_seen?new Date(d.last_seen*1000).toLocaleString():'Never'})),voice:s.voice_sessions},null,2);
  $('capabilities').textContent=s.filesystem_mode==='full'?'Files: Mac + mounted drives · Changes require your approval · Web search available':'Files: approved inbox · Web search available';
  $('events').replaceChildren();for(const ev of s.events){const d=document.createElement('div');d.className='event';d.textContent=`${ev.tool} · ${ev.status} · ${new Date(ev.created*1000).toLocaleTimeString()}`;$('events').append(d)}
  $('approvals').replaceChildren();for(const a of s.approvals){const d=document.createElement('div');d.className='card approval';const title=document.createElement('p');let payload;try{payload=JSON.parse(a.args)}catch{payload={arguments:a.args}}const labels={edit_file:'Edit file',write_file:'Create or replace file',delete_file:payload.arguments?.permanent?'Permanently delete file':'Move to Trash',move_file:'Move or rename',browser:'Browser action',launch_application:'Launch application',read_file:'Read private file',registered_action:'Run registered action'};title.textContent=labels[a.tool]||a.tool;const preview=document.createElement('pre');preview.textContent=JSON.stringify(payload.preview||payload.arguments,null,2);d.append(title,preview);const details=document.createElement('details');const label=document.createElement('summary');label.textContent='Full request';const full=document.createElement('pre');full.textContent=JSON.stringify(payload,null,2);details.append(label,full);d.append(details);for(const allow of [true,false]){const b=document.createElement('button');b.textContent=allow?(payload.arguments?.permanent?'Permanently delete':a.tool==='delete_file'?'Move to Trash':'Approve once'):'Deny';b.onclick=async()=>{try{b.disabled=true;const r=await api('approvals/'+a.id,{method:'POST',body:{allow}});const summary=r.error?'Action failed: '+r.error:r.changed?'Updated '+r.changed:r.trashed?'Moved to Trash: '+r.trashed:r.moved?'Moved '+r.moved+' to '+r.destination:r.permanently_deleted?'Permanently deleted '+r.permanently_deleted:r.denied?'Action denied.':JSON.stringify(r);message('assistant',summary);if(socket?.readyState===1)speak(summary);await refresh()}catch(e){error(e);b.disabled=false}};d.append(b)}$('approvals').append(d)}
  native('status',{text:s.runtime_online?'Jarvis · Ready':'Jarvis · Offline'});
 }catch(e){$('connection').textContent='Server unavailable';native('status',{text:'Jarvis · Offline'})}}
setInterval(refresh,10000);
setInterval(()=>{if(token&&!device)connect()},5000);
async function memories(){if(!device)return;$('memories').replaceChildren();for(const m of await api('memory')){const d=document.createElement('div');d.className='card';const t=document.createElement('p');t.textContent=m.text;const b=document.createElement('button');b.textContent='Forget';b.onclick=async()=>{await api('memory/'+m.id,{method:'DELETE'});memories()};d.append(t,b);$('memories').append(d)}}
$('memoryForm').onsubmit=async e=>{e.preventDefault();try{await api('memory',{method:'POST',body:{text:$('memoryText').value}});$('memoryText').value='';await memories()}catch(e){error(e)}};
$('searchForm').onsubmit=async e=>{e.preventDefault();try{const rs=await api('search?q='+encodeURIComponent($('searchText').value));$('searchResults').replaceChildren();for(const r of rs){const d=document.createElement('div');d.className='card';d.textContent=r.content;$('searchResults').append(d)}}catch(e){error(e)}};
$('export').onclick=async()=>{try{const data=await api('export');const text=JSON.stringify(data,null,2);if(native('exportData',{text}))return;const blob=new Blob([text],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='jarvis-memory.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}catch(e){error(e)}};
async function settings(){
  $('adminSettings').hidden=!device.admin;if(!device.admin)return;cfg=await api('settings');$('modelSelect').replaceChildren();for(const model of cfg.models){const o=new Option(model,model);$('modelSelect').add(o)}$('modelSelect').value=cfg.model;$('toolModelSelect').replaceChildren();for(const model of cfg.models)$('toolModelSelect').add(new Option(model,model));$('toolModelSelect').value=cfg.tool_model||cfg.model;
  const voices=window.__voices||speechSynthesis.getVoices().filter(v=>v.localService).map(v=>({name:v.name,identifier:v.voiceURI}));$('voiceSelect').replaceChildren();if(!voices.length)voices.push({name:'Samantha'});for(const v of voices)$('voiceSelect').add(new Option(v.name,v.name));$('voiceSelect').value=cfg.voice.voice;$('rate').value=cfg.voice.rate;$('followup').value=cfg.voice.follow_up_seconds;$('retention').value=cfg.retention_days;
}
$('saveSettings').onclick=async()=>{try{await api('settings',{method:'PATCH',body:{model:$('modelSelect').value,tool_model:$('toolModelSelect').value,retention_days:Number($('retention').value),voice:{voice:$('voiceSelect').value,rate:Number($('rate').value),follow_up_seconds:Number($('followup').value)}}});await settings();$('error').textContent='Settings saved'}catch(e){error(e)}};
$('exportSettings').onclick=async()=>{try{const text=JSON.stringify(await api('settings'),null,2);if(native('exportData',{text,kind:'settings'}))return;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'application/json'}));a.download='jarvis-settings.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}catch(e){error(e)}};
$('reloadModel').onclick=async()=>{try{await api('model/unload',{method:'POST'});$('error').textContent='Model unloaded; the next request reloads it.'}catch(e){error(e)}};
function downsample(input,rate){if(rate===16000)return new Float32Array(input);const ratio=rate/16000;const out=new Float32Array(Math.floor(input.length/ratio));for(let i=0;i<out.length;i++){let start=Math.floor(i*ratio),end=Math.floor((i+1)*ratio),sum=0;for(let j=start;j<end;j++)sum+=input[j];out[i]=sum/Math.max(1,end-start)}return out}
function command(action){if(socket?.readyState===1)socket.send(JSON.stringify({action}))}
async function microphone(){
  if(socket?.readyState===1)return;
  media=await navigator.mediaDevices.getUserMedia({audio:{deviceId:$('micSelect').value?{exact:$('micSelect').value}:undefined,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
  socket=new WebSocket('wss://'+location.host+'/voice');socket.binaryType='arraybuffer';
  await new Promise((resolve,reject)=>{socket.onopen=()=>{socket.send(JSON.stringify({token}));resolve()};socket.onerror=()=>reject(Error('Voice connection unavailable'))});
  socket.onclose=()=>{closeMicrophone();$('voiceState').textContent='Microphone off'};
  socket.onmessage=e=>{const r=JSON.parse(e.data);if(r.event==='status')$('voiceState').textContent=r.status;else if(r.event==='error')error(r.text);else if(r.event==='transcript')message('user',r.text);else if(r.event==='ack')speak(r.text);else if(r.event==='speak'){message('assistant',r.text);metrics(r.metrics);speak(r.text);refresh()}else if(r.event==='stop_speaking'){speechSynthesis.cancel();native('cancelSpeech');speaking=false}};
  audioContext=new (window.AudioContext||window.webkitAudioContext)();await audioContext.resume();source=audioContext.createMediaStreamSource(media);processor=audioContext.createScriptProcessor(4096,1,1);silence=audioContext.createGain();silence.gain.value=0;source.connect(processor);processor.connect(silence);silence.connect(audioContext.destination);
  processor.onaudioprocess=e=>{if(!speaking&&socket?.readyState===1)socket.send(downsample(e.inputBuffer.getChannelData(0),audioContext.sampleRate).buffer)};
  const selected=$('micSelect').value;$('micSelect').replaceChildren(new Option('System default',''));for(const d of await navigator.mediaDevices.enumerateDevices())if(d.kind==='audioinput')$('micSelect').add(new Option(d.label||'Microphone',d.deviceId));$('micSelect').value=selected;
}
window.closeMicrophone=function(){const old=socket;socket=null;if(old)old.close();if(processor){processor.disconnect();processor.onaudioprocess=null;processor=null}source?.disconnect();source=null;silence?.disconnect();silence=null;if(audioContext){audioContext.close();audioContext=null}if(media){media.getTracks().forEach(t=>t.stop());media=null}talking=false;$('ptt').textContent='Push to talk';$('voiceState').textContent='Microphone off'};
window.nativeSpokenDone=function(){speaking=false;command('spoken_done')};
function speak(text){speaking=true;const voice=cfg?.voice||lastStatus?.voice||{};if(native('speak',{text,voice:voice.voice||'Samantha',rate:voice.rate||185}))return;
  const voices=speechSynthesis.getVoices().filter(v=>v.localService);if(!voices.length){speaking=false;error('No offline voice available on this device');command('spoken_done');return}const u=new SpeechSynthesisUtterance(text);u.voice=voices.find(v=>v.name===voice.voice)||voices[0];u.rate=(voice.rate||185)/185;u.onend=u.onerror=window.nativeSpokenDone;speechSynthesis.speak(u)}
$('wake').onclick=async()=>{try{await microphone();command('wake')}catch(e){closeMicrophone();error(e)}};
$('ptt').onclick=async()=>{try{await microphone();talking=!talking;command(talking?'ptt':'finish');$('ptt').textContent=talking?'Finish speaking':'Push to talk'}catch(e){closeMicrophone();error(e)}};
$('mute').onclick=()=>{command('mute');closeMicrophone();speechSynthesis.cancel();native('cancelSpeech');speaking=false};
$('cancel').onclick=()=>{controller?.abort();controller=null;$('send').disabled=false;api('cancel',{method:'POST'}).catch(error);command('cancel');speechSynthesis.cancel();native('cancelSpeech');speaking=false};
document.onkeydown=e=>{if(e.key==='Escape')$('cancel').click()};
$('disconnect').onclick=()=>{closeMicrophone();token='';device=null;$('workspace').hidden=true;$('login').hidden=false;$('token').value='';$('connection').textContent='Disconnected'};
if(token)connect();
