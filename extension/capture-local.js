// Only injected on the bundled demo. Transfer the explicitly selected local file; no page capture elsewhere.
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
 if(sender.id!==chrome.runtime.id||msg?.type!=='cardflip-read-demo')return;
 if(location.href!=='http://127.0.0.1:8765/capture-demo.html'){reply({error:'Open the exact local demo page.'});return;}
 const file=document.getElementById('photo')?.files?.[0];
 if(!file||!['image/png','image/jpeg'].includes(file.type)||file.size>5000000){reply({error:'Choose a PNG/JPEG under 5 MB on the demo page first.'});return;}
 const reader=new FileReader();reader.onload=()=>reply({data:reader.result});reader.onerror=()=>reply({error:'Could not read demo image.'});reader.readAsDataURL(file);return true;
});
