'use strict';
chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true}).catch(console.error);
const DEMO='http://127.0.0.1:8765/capture-demo.html';
// The page itself is the final authority; tab.url may be absent in Brave.
function readSelectedFile(){
 if(location.origin!=='http://127.0.0.1:8765'||location.pathname!=='/capture-demo.html')return {error:'Active page is not the local CardFlip demo.'};
 const file=document.getElementById('photo')?.files?.[0];
 if(!file||!['image/png','image/jpeg'].includes(file.type)||file.size>5000000)return {error:'Choose a PNG/JPEG under 5 MB on the demo page first.'};
 return new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve({data:reader.result});reader.onerror=()=>resolve({error:'Could not read demo image.'});reader.readAsDataURL(file);});
}
function isDemo(url){try{const u=new URL(url);return u.origin==='http://127.0.0.1:8765'&&u.pathname==='/capture-demo.html';}catch{return false;}}
async function readDemo(windowId,commandTab){
 let tab=Number.isInteger(commandTab?.id)&&commandTab.id>=0?commandTab:null;
 if(!tab){
  const validWindow=Number.isInteger(windowId)&&windowId>=0;
  const query=validWindow?{active:true,windowId}:{active:true,lastFocusedWindow:true};
  [tab]=await chrome.tabs.query(query);
  // The side panel can report a window without an active tab. Only fall back
  // to the actual focused window, never search or read background tabs.
  if(!tab&&validWindow)[tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true});
 }
 if(!Number.isInteger(tab?.id)||tab.id<0)throw Error('No active browser tab found. Click the demo page and retry.');
 if(tab.url&&!isDemo(tab.url))throw Error('Active tab is not the local demo. Open '+DEMO+' and try again.');
 let result;
 try{const rows=await chrome.scripting.executeScript({target:{tabId:tab.id},func:readSelectedFile});result=rows?.[0]?.result;}
 catch(e){throw Error('Brave could not read active tab '+tab.id+': '+(e.message||String(e))+(tab.url?'':' (Brave did not provide the tab URL.)')+' Open '+DEMO+' and check local site access.');}
 if(result?.error)throw Error(result.error);if(!result?.data)throw Error('No demo image returned.');
 const [after]=await chrome.tabs.query({active:true,windowId:tab.windowId});
 if(after?.id!==tab.id||(after.url&&!isDemo(after.url)))throw Error('Tab changed. Try again.');
 return {data:result.data,windowId:tab.windowId};
}
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
 if(sender.id!==chrome.runtime.id||sender.url!==chrome.runtime.getURL('index.html')||msg?.type!=='cardflip-request-demo')return;
 readDemo(msg.windowId).then(result=>reply(result),e=>reply({error:e.message}));return true;
});
chrome.commands.onCommand.addListener(async(command,tab)=>{
 if(command!=='capture-local-demo')return;
 try{
  await chrome.runtime.sendMessage({type:'cardflip-capture-progress',windowId:tab?.windowId}).catch(()=>{});
  const result=await readDemo(tab?.windowId,tab);
  await chrome.runtime.sendMessage({type:'cardflip-capture',...result});
 }catch(e){await chrome.runtime.sendMessage({type:'cardflip-capture-error',error:e.message||'Capture unavailable.',windowId:tab?.windowId}).catch(()=>{});}
});
