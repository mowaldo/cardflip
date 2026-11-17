const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
const demo='http://127.0.0.1:8765/capture-demo.html';let tab={id:3,windowId:1,url:demo};let listener,command;let injected=0;const sent=[];let response={data:'data:image/png;base64,YQ=='};let queries=[];let failFirst=false;let injectError=null;
const chrome={sidePanel:{setPanelBehavior:async()=>{}},tabs:{query:async q=>{queries.push(q);if(failFirst&&q.windowId===9)return [];return [tab];}},scripting:{executeScript:async ({target,func})=>{assert.equal(target.tabId,3);assert.equal(typeof func,'function');injected++;if(injectError)throw Error(injectError);return [{result:response}];}},runtime:{id:'test',getURL:p=>'chrome-extension://test/'+p,onMessage:{addListener:f=>listener=f},sendMessage:async m=>{sent.push(m);return {ok:true};}},commands:{onCommand:{addListener:f=>command=f}}};
vm.runInNewContext(fs.readFileSync('extension/background.js','utf8'),{chrome,console,URL});
const ask=(windowId=1)=>new Promise(r=>{assert.equal(listener({type:'cardflip-request-demo',windowId},{id:'test',url:chrome.runtime.getURL('index.html')},r),true);});
(async()=>{assert.equal((await ask()).data,response.data);assert.equal(injected,1);queries=[];await command('capture-local-demo',tab);assert.equal(sent[0].type,'cardflip-capture-progress');assert.equal(sent[1].data,response.data);assert.equal(queries.length,1,'shortcut should use its own tab ID');
 tab={...tab,url:'https://example.com/'};assert.match((await ask()).error,/not the local demo/);assert.equal(injected,2);
 tab={...tab,url:demo+'?test=1#photo'};assert.equal((await ask()).data,response.data);
 delete tab.url;assert.equal((await ask()).data,response.data,'missing URL metadata should reach guarded reader');
 failFirst=true;assert.equal((await ask(9)).data,response.data);failFirst=false;
 response={error:'Choose a PNG/JPEG'};assert.match((await ask()).error,/Choose a PNG/);
 injectError='Cannot access contents';assert.match((await ask()).error,/Cannot access contents/);injectError=null;
 assert.equal(listener({type:'cardflip-request-demo'},{id:'other'},()=>{}),undefined);
 // Execute the actual injected reader on a wrong page; accessing any DOM would fail.
 let guard;const source=fs.readFileSync('extension/background.js','utf8');const testChrome={...chrome,scripting:{executeScript:async({func})=>{guard=func;return [{result:{error:'not demo'}}];}}};
 let testListener;testChrome.runtime={...chrome.runtime,onMessage:{addListener:f=>testListener=f}};vm.runInNewContext(source,{chrome:testChrome,console,URL,location:{origin:'https://example.com',pathname:'/capture-demo.html'}});
 await new Promise(r=>testListener({type:'cardflip-request-demo',windowId:1},{id:'test',url:chrome.runtime.getURL('index.html')},r));assert.match(guard().error,/not the local/);
 // The timed demo selects the current file, not always the first image.
 const files=[{type:'image/png',size:1,tag:'first'},{type:'image/jpeg',size:1,tag:'second'}];
 let actualReader;let actualListener;const readerChrome={...chrome,scripting:{executeScript:async({func})=>{actualReader=func;return [{result:{error:'test'}}];}},runtime:{...chrome.runtime,onMessage:{addListener:f=>actualListener=f}}};
 class Reader{readAsDataURL(f){this.result=f.tag;this.onload();}}
 vm.runInNewContext(source,{chrome:readerChrome,console,URL,location:{origin:'http://127.0.0.1:8765',pathname:'/capture-demo.html'},document:{getElementById:()=>({files,dataset:{index:'1'}})},FileReader:Reader});
 await new Promise(r=>actualListener({type:'cardflip-request-demo',windowId:1},{id:'test',url:chrome.runtime.getURL('index.html')},r));assert.equal((await actualReader()).data,'second');
 console.log('Capture worker tests passed: direct command tab, missing URL, hash/query, window fallback, page guard, denied access and sender restriction');})().catch(e=>{console.error(e);process.exitCode=1;});
