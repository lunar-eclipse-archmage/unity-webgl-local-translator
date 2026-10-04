// ==UserScript==
// @name         Unity Translation Toolkit
// @namespace    local.unity.translation.toolkit
// @version      1.0.0
// @description  本地字体加载、文本bundle采集、动态CRC补丁；统一可隐藏面板
// @match        https://example.invalid/*
// @run-at       document-start
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        unsafeWindow
// @connect      127.0.0.1
// ==/UserScript==


// 用户配置：同时修改上方 @match，使其匹配目标游戏页面。
const GAME_CONFIG = Object.freeze({
  serviceToken: "", // 与local.py的LOCAL_SERVICE_TOKEN一致，至少32字符
  resourceHosts: [], // 精确主机名，不含协议；留空时不采集或清理资源
  catalogURL: "", // Catalog地址；留空时禁用目录修改
  catalogIgnoreSearch: true, // 仅Catalog忽略动态查询参数；设false时匹配完整URL
  mainPatch: { enabled: false, url: "", bytes: 0 } // URL包含版本查询参数；仅支持解压后的UnityWebData1.0
});
const resourceAllowed = value => {
  try { return GAME_CONFIG.resourceHosts.includes(new URL(value, location.href).hostname); }
  catch { return false; }
};

const UnityPanel=(()=>{
  const state={logs:[],sections:new Map(),root:null,body:null,logBox:null,logging:localStorage.getItem('unity-tools-logging')!=='off'};
  function log(category,...values){
    if(!state.logging)return;
    const detail=values.map(x=>x instanceof Error?x.message:typeof x==='string'?x:JSON.stringify(x)).join(' ');
    const line=new Date().toLocaleTimeString()+' ['+category+'] '+detail;
    state.logs.push(line);if(state.logs.length>10000)state.logs.shift();
    unsafeWindow.console.log('[Unity Tools]',line);
    if(state.logBox){state.logBox.textContent=state.logs.slice(-200).join('\n');state.logBox.scrollTop=state.logBox.scrollHeight;}
  }
  function expanded(value){
    if(!state.root)return;
    state.body.hidden=!value;state.root.style.width=value?'390px':'auto';
    state.root.querySelector('[data-toggle]').textContent=value?'最小化':'译文工具';
  }
  function show(){mount();if(state.root){state.root.hidden=false;localStorage.removeItem('unity-tools-hide');expanded(true);}}
  function section(name){
    if(state.sections.has(name))return state.sections.get(name);
    const box=document.createElement('div');box.style.cssText='padding:8px 0;border-top:1px solid #536171';
    const title=document.createElement('b');title.textContent=name;box.append(title);
    state.sections.set(name,box);if(state.body)state.body.insertBefore(box,state.logBox);
    return box;
  }
  function button(parent,text,click){const b=document.createElement('button');b.textContent=text;b.style.cssText='margin:5px 5px 0 0;padding:4px 7px;cursor:pointer';b.onclick=click;parent.append(b);return b;}
  function mount(){
    if(state.root||!document.body)return;
    const root=document.createElement('div');root.id='unity-tools-panel';
    root.style.cssText='position:fixed;right:10px;bottom:10px;z-index:2147483647;background:#202936;color:#fff;padding:7px;border:1px solid #79879a;border-radius:6px;font:12px sans-serif;max-width:calc(100vw - 34px);';
    const toggle=button(root,'译文工具',()=>expanded(state.body.hidden));toggle.dataset.toggle='1';
    button(root,'隐藏',()=>{root.hidden=true;localStorage.setItem('unity-tools-hide','1');});
    const body=document.createElement('div');body.style.cssText='max-height:65vh;overflow:auto';root.append(body);
    const note=document.createElement('div');note.textContent='字体加载 / 资源采集 / 目录补丁';body.append(note);
    const logs=document.createElement('pre');logs.style.cssText='white-space:pre-wrap;word-break:break-word;max-height:190px;overflow:auto;background:#121a23;padding:6px;font:11px monospace';
    const logControl=document.createElement('label');const logSwitch=document.createElement('input');logSwitch.type='checkbox';logSwitch.checked=state.logging;logControl.append(logSwitch,document.createTextNode('记录日志（面板和控制台）'));body.append(logControl);
    logSwitch.onchange=()=>{state.logging=logSwitch.checked;localStorage.setItem('unity-tools-logging',state.logging?'on':'off');logs.hidden=!state.logging;};logs.hidden=!state.logging;
    body.append(logs);state.root=root;state.body=body;state.logBox=logs;
    for(const box of state.sections.values())body.insertBefore(box,logs);
    document.body.append(root);root.hidden=localStorage.getItem('unity-tools-hide')==='1';expanded(false);
    log('面板','已启动；默认最小化。可通过油猴菜单重新打开。');
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
  GM_registerMenuCommand('打开统一翻译面板',show);
  return {log,section,button,expanded,show,history:()=>state.logs.join("\n")};
})();

// Module: local main font loader
(() => {
  'use strict';
  const window=unsafeWindow;
  const console={info:(...x)=>UnityPanel.log('字体',...x)};
  const settings = GAME_CONFIG.mainPatch;
  if (!settings.enabled) return;
  if (!settings.url || !Number.isSafeInteger(settings.bytes) || settings.bytes <= 0) { console.info("字体补丁配置无效，跳过"); return; }
  const SIZE = settings.bytes;
  let selected, label;
  let resolveFile;
  const fileReady = new Promise(resolve => { resolveFile = resolve; });
  function matches(value) {
    if (typeof value !== 'string') return false;
    try {
      const u = new URL(value, location.href);
      return u.href === new URL(settings.url, location.href).href;
    } catch { return false; }
  }
  function say(text) {
    if (label) label.textContent = text;
    console.info('[Unity Local Main]', text);
  }

  function mount(){
    const box=UnityPanel.section('本地字体主资源');
    label=document.createElement('div');label.textContent='每次刷新请选择 '+SIZE+' 字节的解压后主资源补丁';box.append(label);
    const input=document.createElement('input');input.type='file';input.style.cssText='display:block;max-width:100%;margin-top:6px';box.append(input);
    input.addEventListener('change',async()=>{
      const file=input.files[0];if(!file)return;
      try{
        if(file.size!==SIZE)throw new Error('大小不符，应为 '+SIZE+' 字节');
        if(new TextDecoder().decode(await file.slice(0,16).arrayBuffer())!=='UnityWebData1.0\0')throw new Error('文件头不符，请选择解压后的字体主资源补丁');
        selected=file;resolveFile(file);input.disabled=true;say('补丁已选择：'+file.name);UnityPanel.expanded(false);
      }catch(e){say(e.message);}
    });
  }
  mount();
  function recordMatches(cursor) {
    const v = cursor.value;
    return matches(cursor.primaryKey) || matches(cursor.key) ||
      (Array.isArray(cursor.primaryKey) && cursor.primaryKey.some(matches)) ||
      (v && typeof v === 'object' && ['url','URL','requestUrl'].some(k => matches(v[k])));
  }
  async function clearMain() {
    let count = 0;
    if ('caches' in window) {
      for (const name of await caches.keys()) {
        const cache = await caches.open(name);
        for (const request of await cache.keys()) if (matches(request.url) && await cache.delete(request)) count++;
      }
    }
    if (!indexedDB.databases) throw new Error('浏览器不支持数据库枚举，无法确认主资源缓存已清理');
    for (const info of await indexedDB.databases()) {
      if (!info.name || !/^UnityCache(?:[._-].*)?$/.test(info.name)) continue;
      const db = await new Promise((resolve,reject) => {
        const r = indexedDB.open(info.name);
        r.onsuccess = () => resolve(r.result);
        r.onerror = () => reject(r.error);
        r.onblocked = () => reject(new Error('缓存数据库被占用，请关闭其他游戏标签页'));
      });
      try {
        const names = [...db.objectStoreNames];
        if (!names.length) continue;
        await new Promise((resolve,reject) => {
          const tx = db.transaction(names,'readwrite');
          tx.oncomplete = resolve;
          tx.onerror = () => reject(tx.error);
          tx.onabort = () => reject(tx.error || new Error('缓存清理中止'));
          for (const name of names) {
            const r = tx.objectStore(name).openCursor();
            r.onsuccess = () => {
              const c = r.result;
              if (!c) return;
              if (recordMatches(c)) { c.delete(); count++; }
              c.continue();
            };
          }
        });
      } finally { db.close(); }
    }
    console.info('[Unity Local Main] 主资源缓存清理完成：', count);
  }
  const cleanup = clearMain();
  cleanup.catch(error => say('主资源缓存清理失败：' + error.message + '；请刷新重试'));
  const nativeFetch = window.fetch;
  window.fetch = async function(input,init) {
    const url = typeof input === 'string' || input instanceof URL ? String(input) : input?.url;
    if (!matches(url)) return nativeFetch.apply(this,arguments);
    try { await cleanup; } catch { return nativeFetch.apply(this,arguments); }
    const method = String(init?.method || input?.method || 'GET').toUpperCase();
    if (!['GET','HEAD'].includes(method)) return nativeFetch.apply(this,arguments);
    const file = selected || await fileReady;
    say('本地补丁交给 Unity：' + method + '，'+file.size+' 字节');
    const response = new Response(method === 'HEAD' ? null : file.stream(), {
      status:200,
      headers:{'Content-Type':'application/octet-stream','Content-Length':String(file.size),'Cache-Control':'no-store'}
    });
    Object.defineProperty(response,'url',{value:new URL(url,location.href).href});
    return response;
  };
})();
// Module: dynamic catalog patch
(() => {
  'use strict';
  const window=unsafeWindow,XMLHttpRequest=window.XMLHttpRequest;
  const console={info:(...x)=>UnityPanel.log('目录',...x),warn:(...x)=>UnityPanel.log('目录警告',...x),error:(...x)=>UnityPanel.log('目录错误',...x)};
  if (!GAME_CONFIG.catalogURL || !GAME_CONFIG.resourceHosts.length) return;
  const TARGETS = {};

  // Clean only deployed bundle URLs on configured resource hosts.
  const CLEAR_KEY = 'unity-local-clear-v2';
  const fontHashes = new Set();
  function isFontURL(value) {
    if (typeof value !== 'string') return false;
    try {
      const url = new URL(value, location.href);
      const match = url.pathname.match(/([a-f0-9]{32})\.bundle$/i);
      return !!match && fontHashes.has(match[1].toLowerCase()) &&
        resourceAllowed(url.href);
    } catch { return false; }
  }
  function recordMatches(cursor) {
    const value = cursor.value;
    return isFontURL(cursor.primaryKey) || isFontURL(cursor.key) ||
      (Array.isArray(cursor.primaryKey) && cursor.primaryKey.some(isFontURL)) ||
      (value && typeof value === 'object' && ['url', 'URL', 'requestUrl'].some(key => isFontURL(value[key])));
  }
  async function clearFontCache() {
    let count = 0;
    if ('caches' in window) {
      for (const name of await caches.keys()) {
        const cache = await caches.open(name);
        for (const request of await cache.keys()) {
          if (isFontURL(request.url) && await cache.delete(request)) count++;
        }
      }
    }
    if (indexedDB.databases) {
      for (const info of await indexedDB.databases()) {
        if (!info.name || !/^UnityCache(?:[._-].*)?$/.test(info.name)) continue;
        const db = await new Promise((resolve, reject) => {
          const req = indexedDB.open(info.name);
          req.onsuccess = () => resolve(req.result);
          req.onerror = () => reject(req.error);
          req.onblocked = () => reject(new Error('Unity cache database blocked; close other game tabs'));
        });
        try {
          const stores = [...db.objectStoreNames];
          if (stores.length) await new Promise((resolve, reject) => {
            const tx = db.transaction(stores, 'readwrite');
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error || new Error('Cache cleanup aborted'));
            for (const name of stores) {
              const req = tx.objectStore(name).openCursor();
              req.onsuccess = () => {
                const cursor = req.result;
                if (!cursor) return;
                if (recordMatches(cursor)) { cursor.delete(); count++; }
                cursor.continue();
              };
            }
          });
        } finally { db.close(); }
      }
    } else console.warn('[Unity CN] IndexedDB enumeration unavailable; Cache Storage cleaned only');
    console.info('[Unity CN] Font cache cleanup complete:', count, 'entries');
    return count;
  }
  let cleanupError = null;
  const cacheReady=new Promise((resolve,reject)=>{
    GM_xmlhttpRequest({method:'GET',url:'http://127.0.0.1:8765/patches',headers:{'X-Local-Token':GAME_CONFIG.serviceToken},timeout:10000,
      onload:r=>{try{
        if(r.status!==200)throw new Error('本地部署清单HTTP '+r.status);
        const manifest=JSON.parse(r.responseText);
        for(const [hash,item] of Object.entries(manifest.targets||{})){
          if(!/^[a-f0-9]{32}$/.test(hash)||!Number.isSafeInteger(item.bytes)||item.bytes<=0)throw new Error('无效部署清单');
          TARGETS[hash]=item.bytes;fontHashes.add(hash);
        }
        const signature=JSON.stringify(manifest);
        const changed=localStorage.getItem('unity-local-manifest-v2')!==signature;
        const forced=sessionStorage.getItem(CLEAR_KEY)==='1';sessionStorage.removeItem(CLEAR_KEY);
        const cleanup=changed||forced?clearFontCache():Promise.resolve();
        cleanup.then(()=>{localStorage.setItem('unity-local-manifest-v2',signature);console.info('[Unity Local Catalog] 已读取部署清单',Object.keys(manifest.targets||{}).length);resolve();}).catch(reject);
      }catch(e){reject(e);}},
      onerror:()=>reject(new Error('本地服务未启动：请先运行collector.py再刷新')),
      ontimeout:()=>reject(new Error('本地服务读取部署清单超时'))
    });
  });
  cacheReady.catch(error=>{cleanupError=error;console.error('[Unity Local Catalog]',error);});

  function addCacheButton(){
    const box=UnityPanel.section('目录与本地服务');
    const serviceStatus=document.createElement('div');serviceStatus.textContent='请保持本地collector运行';box.append(serviceStatus);
    UnityPanel.button(box,'清理补丁缓存并刷新',()=>{sessionStorage.setItem(CLEAR_KEY,'1');location.reload();});
    UnityPanel.button(box,'检查本地服务',()=>GM_xmlhttpRequest({method:'GET',url:'http://127.0.0.1:8765/patches',headers:{'X-Local-Token':GAME_CONFIG.serviceToken},timeout:10000,
      onload:r=>{try{const value=JSON.parse(r.responseText);serviceStatus.textContent='HTTP '+r.status+'；已部署 '+Object.keys(value.targets||{}).length+' 个bundle';UnityPanel.log('服务',serviceStatus.textContent);}catch{serviceStatus.textContent='响应格式无效';UnityPanel.log('服务',serviceStatus.textContent);}},
      onerror:()=>{serviceStatus.textContent='连接失败，请运行start_collector.bat';UnityPanel.log('服务',serviceStatus.textContent);},ontimeout:()=>{serviceStatus.textContent='连接超时';UnityPanel.log('服务',serviceStatus.textContent);}}));
  }
  addCacheButton();
  const isCatalog = url => {
    try {
      const actual = new URL(url, location.href);
      const configured = new URL(GAME_CONFIG.catalogURL, location.href);
      return GAME_CONFIG.catalogIgnoreSearch === false ? actual.href === configured.href :
        actual.origin === configured.origin && actual.pathname === configured.pathname;
    } catch { return false; }
  };
  function patch(text) {
    const catalog = JSON.parse(text);
    const data = Uint8Array.from(atob(catalog.m_ExtraDataString), c => c.charCodeAt(0));
    const view = new DataView(data.buffer);
    let p = 0, hits = 0;
    const decoder = new TextDecoder('utf-16le');
    while (p < data.length) {
      if (data[p++] !== 7) throw new Error('Unexpected catalog extra-data type');
      const assemblyLength = data[p++]; p += assemblyLength;
      const classLength = data[p++]; p += classLength;
      const length = view.getInt32(p, true); p += 4;
      if (length < 0 || p + length > data.length || length % 2) throw new Error('Invalid record length');
      const record = JSON.parse(decoder.decode(data.subarray(p, p + length)));
      if (Object.hasOwn(TARGETS, record.m_Hash)) {
        record.m_Crc = 0;
        record.m_BundleSize = TARGETS[record.m_Hash];
        const json = JSON.stringify(record);
        if (json.length * 2 > length) throw new Error('Patched record exceeds original length');
        const padded = json.padEnd(length / 2, ' ');
        for (let i = 0; i < padded.length; i++) view.setUint16(p + i * 2, padded.charCodeAt(i), true);
        hits++;
      }
      p += length;
    }
    if (hits !== Object.keys(TARGETS).length) console.warn('[Unity Local Catalog] 部分目标不在当前catalog；匹配',hits,'预期',Object.keys(TARGETS).length);
    let binary = '';
    for (let i = 0; i < data.length; i += 16384) binary += String.fromCharCode(...data.subarray(i, i + 16384));
    catalog.m_ExtraDataString = btoa(binary);
    console.info('[Unity Local Catalog] Catalog patched: target CRC=0；匹配 '+hits+' 个，清单 '+Object.keys(TARGETS).length+' 个');
    return JSON.stringify(catalog);
  }
  const nativeFetch = window.fetch;
  window.fetch = async function(input, init) {
    const requestURL = typeof input === 'string' || input instanceof URL ? String(input) : input?.url;
    if (!isCatalog(requestURL)) return nativeFetch.apply(this, arguments);
    try { await cacheReady; } catch { return nativeFetch.apply(this, arguments); }
    const response = await nativeFetch.apply(this, arguments);
    const url = typeof input === 'string' || input instanceof URL ? String(input) : input.url;
    if (!isCatalog(url) || !response.ok || (init?.method || input?.method || 'GET').toUpperCase() === 'HEAD') return response;
    try {
      const body = patch(await response.clone().text());
      const headers = new Headers(response.headers);
      headers.delete('content-length'); headers.delete('content-encoding');
      const result = new Response(body, {status: response.status, statusText: response.statusText, headers});
      for (const key of ['url', 'redirected', 'type']) Object.defineProperty(result, key, {value: response[key]});
      return result;
    } catch (error) { console.error('[Unity CN] Catalog patch failed', error); return response; }
  };
  // XHR fallback; only catalog responses are affected.
  const proto = XMLHttpRequest.prototype;
  const nativeOpen = proto.open;
  const nativeSend = proto.send;
  const asyncRequests = new WeakMap();
  proto.send = function() {
    const xhr = this, args = arguments;
    if (asyncRequests.get(xhr) === false || !targets.has(xhr)) return nativeSend.apply(xhr, args);
    cacheReady.then(() => nativeSend.apply(xhr, args)).catch(error => { console.error('[Unity CN] XHR send failed', error); nativeSend.apply(xhr, args); });
  };
  const targets = new WeakSet(), memo = new WeakMap();
  proto.open = function(method, url) {
    asyncRequests.set(this, arguments[2] !== false);
    targets.delete(this); memo.delete(this);
    if (String(method).toUpperCase() === 'GET' && isCatalog(String(url))) targets.add(this);
    return nativeOpen.apply(this, arguments);
  };
  const textDesc = Object.getOwnPropertyDescriptor(proto, 'responseText');
  const responseDesc = Object.getOwnPropertyDescriptor(proto, 'response');
  function translated(xhr) {
    if (memo.has(xhr)) return memo.get(xhr);
    let result;
    try {
      const type = xhr.responseType;
      const original = responseDesc.get.call(xhr);
      if (!type || type === 'text') result = patch(textDesc.get.call(xhr));
      else if (type === 'arraybuffer') result = new TextEncoder().encode(patch(new TextDecoder().decode(original))).buffer;
      else if (type === 'json') result = JSON.parse(patch(JSON.stringify(original)));
      else { console.warn('[Unity CN] Unsupported XHR responseType', type); return original; }
    } catch (error) { console.error('[Unity CN] XHR patch failed', error); result = responseDesc.get.call(xhr); }
    memo.set(xhr, result); return result;
  }
  Object.defineProperty(proto, 'response', {...responseDesc, get() {
    if (!cleanupError && targets.has(this) && this.readyState === 4 && this.status === 200) return translated(this);
    return responseDesc.get.call(this);
  }});
  Object.defineProperty(proto, 'responseText', {...textDesc, get() {
    if (!cleanupError && targets.has(this) && this.readyState === 4 && this.status === 200 && (!this.responseType || this.responseType === 'text')) return translated(this);
    return textDesc.get.call(this);
  }});
  console.info('[Unity CN] Catalog hook installed', location.origin);
})();
// Module: text bundle collector
(() => {
  'use strict';
  const w=unsafeWindow, seen=new Set(), pending=new Set(), cachePending=new Map(), queue=[];
  let active=0, panel, sequence=0;
  const concurrency=3, history=[], session=Date.now().toString(36);
  const limit=128*1024*1024;
  let enabled=localStorage.getItem('unity-tools-capture')!=='off';
  function log(s){UnityPanel.log('采集',s);}
  const controls=UnityPanel.section('文本资源采集');
  const captureLabel=document.createElement('label');const captureBox=document.createElement('input');captureBox.type='checkbox';captureBox.checked=enabled;
  captureBox.onchange=()=>{enabled=captureBox.checked;localStorage.setItem('unity-tools-capture',enabled?'on':'off');log(enabled?'采集已启用':'采集已暂停；已入队任务继续完成');};
  captureLabel.append(captureBox,document.createTextNode('启用采集'));controls.append(captureLabel);
  UnityPanel.button(controls,'导出完整日志',()=>{const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([UnityPanel.history()],{type:'text/plain;charset=utf-8'}));link.download='unity-translation-toolkit.log';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);});
  function valid(url) {
    try {const u=new URL(url,w.location.href);return resourceAllowed(u.href)&&/\.bundle$/i.test(u.pathname);}catch{return false;}
  }
  // Persistent per-origin queue. Failed jobs remain until explicit retry/removal.
  const running=new Set();
  let scheduling=false;
  const queueDB=new Promise((resolve,reject)=>{
    const request=w.indexedDB.open('UnityTranslationQueue',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('jobs',{keyPath:'url'});
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>reject(request.error);
  });
  queueDB.catch(e=>log('持久队列不可用：'+e.message+'；资源无法可靠采集'));
  function submit(url, bytes) {
    if(!bytes.byteLength){log('跳过空文件：'+url.split('/').pop());return false;}
    if(bytes.byteLength>limit){log('跳过超过128MiB：'+url.split('/').pop());return false;}
    if(seen.has(url))return true;
    // Resolve seen only after durable commit, so storage failure can be retried.
    queueDB.then(db=>new Promise((resolve,reject)=>{
      const tx=db.transaction('jobs','readwrite'),store=tx.objectStore('jobs');
      let count=0,total=0,existing=false;
      const cursor=store.openCursor();
      cursor.onsuccess=()=>{
        const c=cursor.result;
        if(c){count++;total+=c.value.bytes.byteLength;existing ||= c.key===url;c.continue();return;}
        if(existing){return;}
        if(count>=64||total+bytes.byteLength>256*1024*1024){tx.abort();return;}
        store.put({url,name:new URL(url).pathname.split('/').pop(),bytes,id:session+'-'+(++sequence),queued:Date.now(),attempts:0,next:0});
      };
      tx.oncomplete=resolve;
      tx.onerror=()=>reject(tx.error||new Error('队列写入失败'));
      tx.onabort=()=>reject(tx.error||new Error('队列已满（64项/256MiB），未保存；请处理后重新加载资源'));
    })).then(()=>{seen.add(url);log('已持久化入队：'+url.split('/').pop());drain();}).catch(e=>log('入队失败：'+e.message));
    return true;
  }
  async function drain(){
    if(scheduling||active>=concurrency)return;
    scheduling=true;
    try {
      const db=await queueDB;
      const jobs=await new Promise((resolve,reject)=>{
        const found=[],tx=db.transaction('jobs','readonly'),cursor=tx.objectStore('jobs').openCursor();
        cursor.onsuccess=()=>{
          const c=cursor.result;if(!c)return;
          const job=c.value;
          if(valid(job.url)&&!running.has(job.url)&&job.attempts<5&&job.next<=Date.now()&&found.length<concurrency-active)found.push(job);
          c.continue();
        };
        tx.oncomplete=()=>resolve(found);tx.onerror=()=>reject(tx.error);
      });
      for(const job of jobs)sendJob(job);
    }catch(e){log('队列读取失败：'+e.message);}
    finally{scheduling=false;}
  }
  async function updateJob(job,success){
    const db=await queueDB;
    await new Promise((resolve,reject)=>{
      const tx=db.transaction('jobs','readwrite'),store=tx.objectStore('jobs');
      if(success)store.delete(job.url);
      else {job.attempts++;job.next=Date.now()+Math.min(60000,2000*2**job.attempts);store.put(job);}
      tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
    });
  }
  function sendJob(job){
    active++;running.add(job.url);let finished=false;
    const done=async(success,message)=>{
      if(finished)return;finished=true;
      try{await updateJob(job,success);log(job.name+' | '+message+(success?'；队列完成':job.attempts>=5?'；已暂停，任务仍保存在队列':'；将自动重试'));}
      catch(e){log('队列更新失败，任务保留：'+e.message);}
      finally{active--;running.delete(job.url);job.bytes=null;drain();}
    };
    try{GM_xmlhttpRequest({method:'POST',url:'http://127.0.0.1:8765/inspect',headers:{'X-Local-Token':GAME_CONFIG.serviceToken,'Content-Type':'application/octet-stream','X-Bundle-Name':encodeURIComponent(job.name),'X-Task-ID':job.id,'X-Override-Path':encodeURIComponent(new URL(job.url).search?'':new URL(job.url).hostname+new URL(job.url).pathname)},data:job.bytes,timeout:180000,
      onload:r=>{try{const x=JSON.parse(r.responseText);done(r.status>=200&&r.status<300,'HTTP '+r.status+'；'+(x.error||x.status));}catch{done(false,'响应格式无效');}},
      onerror:()=>done(false,'连接失败'),ontimeout:()=>done(false,'请求超时'),onabort:()=>done(false,'请求中止')});}
    catch(e){done(false,e.message);}
  }
  UnityPanel.button(controls,'重试暂停队列',async()=>{
    try{const db=await queueDB;await new Promise((resolve,reject)=>{
      const tx=db.transaction('jobs','readwrite'),cursor=tx.objectStore('jobs').openCursor();
      cursor.onsuccess=()=>{const c=cursor.result;if(!c)return;if(valid(c.key)&&!running.has(c.key)){const j=c.value;j.attempts=0;j.next=0;c.update(j);}c.continue();};
      tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);
    });drain();}catch(e){log(e.message);}
  });
  UnityPanel.button(controls,'查看队列',async()=>{
    try{const db=await queueDB;let total=0,paused=0,size=0;const tx=db.transaction('jobs','readonly'),cursor=tx.objectStore('jobs').openCursor();
      cursor.onsuccess=()=>{const c=cursor.result;if(!c)return;total++;size+=c.value.bytes.byteLength;if(c.value.attempts>=5)paused++;c.continue();};
      tx.oncomplete=()=>log('持久队列：'+total+'项；暂停 '+paused+'项；'+(size/1048576).toFixed(1)+'MiB');
    }catch(e){log(e.message);}
  });
  setInterval(drain,2000);queueDB.then(drain).catch(()=>{});

  function absolute(url){return new URL(url,w.location.href).href;}
  // Query parameters remain part of the key: do not mix bundle versions.
  function matches(value,url){
    if(typeof value==='string'){try{return absolute(value)===url;}catch{return false;}}
    if(Array.isArray(value))return value.some(x=>matches(x,url));
    return false;
  }
  async function body(value,depth=0){
    if(!value || depth>4)return null;
    const tag=Object.prototype.toString.call(value);
    if(tag==='[object ArrayBuffer]')return value;
    if(ArrayBuffer.isView(value))return value.buffer.slice(value.byteOffset,value.byteOffset+value.byteLength);
    if(tag==='[object Blob]')return value.arrayBuffer();
    if(tag==='[object Response]')return value.clone().arrayBuffer();
    if(typeof value==='object'){
      for(const key of ['body','data','response','content','buffer','bytes','blob']){
        if(value[key]!==undefined){const b=await body(value[key],depth+1);if(b)return b;}
      }
    }
    return null;
  }
  async function fromCaches(url){
    if(!w.caches)return null;
    for(const name of await w.caches.keys()){
      const cache=await w.caches.open(name);
      const response=await cache.match(url,{ignoreSearch:false});
      if(response&&response.ok){const bytes=await response.arrayBuffer();if(bytes.byteLength)return {bytes,source:'Cache Storage / '+name};}
    }
    return null;
  }
  function openDB(name){return new Promise((resolve,reject)=>{
    const r=w.indexedDB.open(name);
    r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);
    r.onblocked=()=>reject(new Error('UnityCache数据库被占用'));
  });}
  function records(db,store,url){return new Promise((resolve,reject)=>{
    const values=[],tx=db.transaction(store,'readonly'),req=tx.objectStore(store).openCursor();
    req.onsuccess=()=>{
      const c=req.result;if(!c)return;
      const v=c.value;
      if(matches(c.primaryKey,url)||matches(c.key,url)||(v&&['url','URL','requestUrl'].some(k=>matches(v[k],url))))values.push(v);
      c.continue();
    };
    tx.oncomplete=()=>resolve(values);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||new Error('缓存读取中止'));
  });}
  async function fromIDB(url){
    if(!w.indexedDB?.databases)throw new Error('浏览器不支持IndexedDB数据库枚举');
    let matched=false;
    for(const info of await w.indexedDB.databases()){
      if(!info.name||!/^UnityCache(?:[._-].*)?$/i.test(info.name))continue;
      const db=await openDB(info.name);
      try{
        for(const store of Array.from(db.objectStoreNames)){
          for(const value of await records(db,store,url)){
            matched=true;const bytes=await body(value);
            if(bytes?.byteLength)return {bytes,source:'UnityCache / '+store};
          }
        }
      }finally{db.close();}
    }
    if(matched)throw new Error('找到对应缓存记录，但未读到支持的二进制内容');
    return null;
  }
  async function checkCache(url){
    if(seen.has(url)||cachePending.has(url))return;
    const work=(async()=>{
      log('HEAD：查找缓存 '+url.split('/').pop());
      let hit=null;const errors=[];
      try{hit=await fromCaches(url);}catch(e){errors.push(e.message);}
      if(!hit)try{hit=await fromIDB(url);}catch(e){errors.push(e.message);}
      if(seen.has(url))return;
      if(hit){log('读取缓存成功：'+url.split('/').pop()+'；来源 '+hit.source+'；字节 '+hit.bytes.byteLength);submit(url,hit.bytes);}
      else log('HEAD：未检查文本；'+(errors.length?errors.join('；'):'缓存未找到')+'；等待GET');
    })();
    cachePending.set(url,work);
    try{await work;}finally{cachePending.delete(url);}
  }
  function capture(url,read){
    if(seen.has(url)||pending.has(url))return;
    pending.add(url);log('GET：开始读取 '+url.split('/').pop());
    Promise.resolve().then(read).then(bytes=>submit(url,bytes)).catch(e=>log('读取失败：'+e.message)).finally(()=>pending.delete(url));
  }
  const original=w.fetch;
  w.fetch=function(...args){return original.apply(this,args).then(response=>{
    try{
      const request=args[0], raw=typeof request==='string'?request:request?.url||String(request);
      const url=absolute(response.url||raw);
      const method=String(args[1]?.method||request?.method||'GET').toUpperCase();
      if(enabled&&response.ok&&valid(url)){
        if(method==='HEAD')void checkCache(url).catch(e=>log('缓存检查失败：'+e.message));
        else if(method==='GET'&&!seen.has(url)&&!pending.has(url)){
          const declared=Number(response.headers.get('content-length'));
          if(declared>limit){log('跳过超大响应：'+url);return response;}
          const copy=response.clone();capture(url,async()=>{
            if(!copy.body)return copy.arrayBuffer();
            const reader=copy.body.getReader(),chunks=[];let size=0;
            try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){void reader.cancel();throw new Error('响应超过128MiB');}chunks.push(value);}}
            finally{reader.releaseLock();}
            const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}return bytes.buffer;
          });
        }
      }
    }catch(e){log('捕获失败：'+e.message);}
    return response;
  });};
  const open=w.XMLHttpRequest.prototype.open,send=w.XMLHttpRequest.prototype.send;
  const requests=new WeakMap();
  w.XMLHttpRequest.prototype.open=function(method,url,...rest){requests.set(this,{method:String(method).toUpperCase(),url:absolute(String(url))});return open.call(this,method,url,...rest);};
  w.XMLHttpRequest.prototype.send=function(...args){
    const onload=()=>{
      this.removeEventListener('load',onload);
      const request=requests.get(this);if(!request)return;
      const url=absolute(this.responseURL||request.url);
      if(!enabled||this.status<200||this.status>=300||!valid(url))return;
      if(request.method==='HEAD'){void checkCache(url).catch(e=>log('缓存检查失败：'+e.message));return;}
      if(request.method!=='GET'||seen.has(url)||pending.has(url))return;
      if(this.responseType==='arraybuffer')capture(url,()=>this.response);
      else if(this.responseType==='blob'){const blob=this.response;capture(url,()=>blob.arrayBuffer());}
      else log('XHR响应不是二进制，未检查：'+url.split('/').pop());
    };
    this.addEventListener('load',onload);return send.apply(this,args);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>log('Unity Translation Toolkit 已启动；请运行本地服务'),{once:true});
  else log('Unity Translation Toolkit 已启动；请运行本地服务');
})();
