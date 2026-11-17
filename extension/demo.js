'use strict';
const $=id=>document.getElementById(id);
let url=null,index=0,deadline=0,timer=null;
function valid(f){return f&&['image/png','image/jpeg'].includes(f.type)&&f.size<=5000000;}
function render(){
 const files=$('photo').files, file=files[index];$('photo').dataset.index=String(index);
 if(url)URL.revokeObjectURL(url);url=null;
 const img=$('photoPreview');img.hidden=!valid(file);
 if(valid(file)){url=URL.createObjectURL(file);img.src=url;}else img.removeAttribute('src');
 $('position').textContent=files.length?`Card ${index+1} of ${files.length}${valid(file)?'':' · Unsupported or too large'}`:'';
 $('prev').disabled=index<=0||Boolean(timer);$('next').disabled=index>=files.length-1||Boolean(timer);
 $('startPractice').disabled=!files.length||Boolean(timer);$('stopPractice').disabled=!timer;
}
function stop(message='Stopped'){if(timer)clearInterval(timer);timer=null;$('clock').textContent=message;render();}
function startRound(){deadline=performance.now()+Number($('duration').value)*1000;}
function tick(){const remaining=Math.max(0,deadline-performance.now());$('clock').textContent=(remaining/1000).toFixed(1)+'s';if(remaining===0){if(index+1>=$('photo').files.length){stop('Finished');return;}index++;render();startRound();}}
$('photo').onchange=()=>{index=0;stop('Ready');};
$('prev').onclick=()=>{if(index>0){index--;render();}};$('next').onclick=()=>{if(index+1<$('photo').files.length){index++;render();}};
$('startPractice').onclick=()=>{if(timer||!$('photo').files.length)return;index=0;startRound();timer=setInterval(tick,100);render();tick();};
$('stopPractice').onclick=()=>stop();render();
