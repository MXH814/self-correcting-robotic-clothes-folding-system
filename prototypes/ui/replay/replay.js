'use strict';
const el = id => document.getElementById(id);
let index = 0;
let timer = null;
function records() { return trajectories[el('run').value].records; }
function stop() {
  clearInterval(timer);
  timer = null;
  el('play').textContent = '播放回放';
}
function draw() {
  const rows = records(), row = rows[index];
  const file = 'frames/' + el('run').value + '/' + String(index).padStart(3,'0') + '.png';
  el('error').textContent = '';
  el('picture').src = file;
  el('picture').alt = el('run').value + ' ' + row.stage + ' 原始索引 ' + row.index;
  el('position').textContent = '第 ' + (index + 1) + ' / ' + rows.length + ' 帧';
  el('stageIndex').textContent = row.stage + ' ／ ' + row.index;
  el('frameId').textContent = row.frame_id;
  el('source').textContent = row.trajectory_id;
  el('rgbHash').textContent = row.rgb.sha256;
  el('missing').textContent = [row.sim_time_s,row.action,row.action_ack].map(v => v === null ? '未记录' : JSON.stringify(v)).join(' ／ ');
  el('stage').value = row.stage;
  el('seek').value = index;
  el('prev').disabled = index === 0;
  el('next').disabled = index === rows.length - 1;
  el('joints').replaceChildren(...row.joint_state.map(v => {
    const li = document.createElement('li'); li.textContent = String(v); return li;
  }));
}
function jump(to) {
  if (!Number.isInteger(to) || to < 0 || to >= records().length) return;
  stop();
  index = to;
  draw();
}
function selectRun() {
  const rows = records();
  el('stage').replaceChildren(...Array.from(new Set(rows.map(r => r.stage)), s => new Option(s,s)));
  el('seek').max = rows.length - 1;
  jump(0);
}
function play() {
  stop();
  if (index === records().length - 1) { index = 0; draw(); }
  el('play').textContent = '暂停回放';
  timer = setInterval(() => {
    index++; draw();
    if (index === records().length - 1) stop();
  }, 1000 / Number(el('speed').value));
}
el('picture').onerror = () => { stop(); el('error').textContent = '当前 RGB 图像读取失败，请检查 frames 目录。'; };
el('prev').onclick = () => jump(index-1);
el('next').onclick = () => jump(index+1);
el('run').onchange = selectRun;
el('seek').oninput = () => jump(Number(el('seek').value));
el('stage').onchange = () => jump(records().findIndex(r => r.stage === el('stage').value));
el('play').onclick = () => timer === null ? play() : stop();
el('speed').onchange = () => { if (timer !== null) play(); };
el('download').onclick = () => {
  const row = records()[index];
  const url = URL.createObjectURL(new Blob([JSON.stringify(row,null,2)],{type:'application/json'}));
  const a = document.createElement('a');
  a.href = url; a.download = el('run').value+'-'+row.stage+'-'+row.index+'.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url),1500);
};
function showCapture(){
  const stage = el('capture').value;
  el('capture-photo').src = '../../../docs/research/zhangmingbo/fold-experiments-20261108/'+stage+'.png';
  el('capture-photo').alt = '固定上衣实测取景：'+el('capture').selectedOptions[0].text;
}
function showGallery(){
  stop();
  el('full').hidden = true;
  el('gallery').hidden = false;
  showCapture();
}
function showFull(){
  el('gallery').hidden = true;
  el('full').hidden = false;
}
el('show-gallery').onclick = showGallery;
el('back').onclick = showFull;
el('capture').onchange = showCapture;
showGallery();
const localRecords = document.createElement('script');
localRecords.src = 'records.js';
localRecords.onload = () => {
  selectRun();
  el('back').hidden = false;
  el('install').hidden = true;
  showFull();
};
localRecords.onerror = () => {
  el('install').hidden = false;
  el('load-status').textContent = '完整轨迹未载入。请按下方步骤导入，或检查浏览器的本地文件权限。';
};
document.body.append(localRecords);
