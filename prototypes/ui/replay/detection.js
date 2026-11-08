'use strict';
const byId = id => document.getElementById(id);
const titles = {first:'首袖远景', near:'指尖近景', full:'完整折叠', legacy:'历史正常示范'};
const condition = {normal:'正常持有及释放', release_regrasp:'提前开手及重抓', closed_hand_slip_candidate:'闭手滑移候选', contact_offset_candidate:'偏移候选', closed_hand_slip_regrasp:'闭手扰动后重抓', recovery:'脚本恢复与接续'};
const operations = {release:'释放', retreat:'退让', regrasp:'重抓', close:'闭手', lift:'抬升'};
const roles = {fit:'拟合', calibration:'校准', development:'开发诊断', evidence_only:'原始证据'};
const fmt = n => n.toFixed(5);
let run, atlas, pos = 0, timer = null;
let journal = [];
function showJournal(row) {
  const matches = journal.filter(e => e.observation_id && (row.observation_ids || [row.id]).includes(e.observation_id));
  const unaligned = journal.filter(e => !e.observation_id);
  const lines = matches.map(e => [e.method || e.kind, e.status || e.state, e.reason,
    e.score == null ? '' : '分数 '+e.score, e.threshold == null ? '' : '阈值 '+e.threshold,
    e.decision_wall_s == null ? '' : '判定单调时钟 '+e.decision_wall_s].filter(Boolean).join(' · '));
  for(const e of unaligned) lines.push('无帧关联 · '+e.kind+' · '+e.reason);
  byId('journalRows').textContent = lines.join('\n') || (journal.length?'本帧无报告。':'尚未导入日志。');
}
async function importJournal(files) {
  const selected = run;
  try {
    const parsed = [];
    const ids = new Set(run.rows.flatMap(r=>r.observation_ids || [r.id]));
    for(const file of files) {
      for(const line of (await file.text()).split(/\r?\n/).filter(s=>s.trim())) {
        const e = JSON.parse(line);
        if(e.trial_id!==selected.trial_id || !['observation-deviation-report/1','geometry-hold-report/1','diagnostic-recovery-event/1'].includes(e.schema)
            || (e.observation_id && !ids.has(e.observation_id))) throw Error('试次、观测编号或日志格式不匹配');
        parsed.push(e);
      }
    }
    if(!parsed.length) throw Error('日志为空');
    if(run!==selected)return;
    journal=parsed; byId('message').textContent='已导入 '+parsed.length+' 条日志，请核对原始采集清单。'; draw();
  } catch(error) { if(run===selected) byId('message').textContent='未导入：'+error.message; }
}
function stop() {
  clearInterval(timer);
  timer = null;
  byId('play').textContent = '播放回放';
}
function lineChart() {
  const canvas = byId('curve'), c = canvas.getContext('2d');
  c.clearRect(0,0,canvas.width,canvas.height);
  if (run.rows[pos].raw === undefined) return;
  const series = run.rows.slice(0,pos+1);
  const maxY = Math.max(1e-12,run.threshold || 0,...series.map(r => r.score));
  const y = v => 90 - 84*v/maxY;
  const x = i => 5 + 460*i/Math.max(1,run.rows.length-1);
  c.strokeStyle = '#335e61'; c.lineWidth = 2; c.beginPath();
  series.forEach((r,i) => { if(r.score==null) return; if(i===0 || series[i-1].score==null) c.moveTo(x(i),y(r.score)); else c.lineTo(x(i),y(r.score)); });
  c.stroke();
  if(run.threshold !== null) {
    c.strokeStyle = '#a94929'; c.setLineDash([5,4]); c.beginPath();
    c.moveTo(0,y(run.threshold)); c.lineTo(470,y(run.threshold)); c.stroke(); c.setLineDash([]);
    c.fillStyle = '#a94929'; series.forEach((r,i) => {if(r.alarm) c.fillRect(x(i)-2,y(r.score)-2,4,4);});
  }
  c.fillStyle = '#335e61'; if(series[pos].score!=null) c.fillRect(x(pos)-2,y(series[pos].score)-2,4,4);
}
function draw() {
  const row = run.rows[pos]; showJournal(row);
  const c = byId('picture').getContext('2d');
  c.clearRect(0,0,320,240);
  if(atlas.complete && atlas.naturalWidth) c.drawImage(atlas,(pos%10)*160,Math.floor(pos/10)*120,160,120,0,0,320,240);
  byId('position').textContent = '第 '+(pos+1)+' / '+run.rows.length+' 帧 · '+(row.t===null?'原始时间未记录':'渲染时间 '+row.t.toFixed(3)+' 仿真秒');
  byId('identity').textContent = run.trial_id+' ／ '+row.id+(row.last_read==null?'':'；本帧最后一次读取 '+row.last_read.toFixed(3)+' 仿真秒');
  byId('source').textContent = titles[run.group]+' · '+roles[run.role];
  byId('phase').textContent = row.phase+'（采集日志）';
  const scored = row.raw !== undefined;
  byId('method').textContent = scored?'ResNet18 → FIPER RND 观测分支 · 离线重算':'此相机无匹配检测器';
  byId('score').textContent = scored?fmt(row.raw)+' / '+(row.score==null?'等待五帧':fmt(row.score)):'无分数';
  byId('decision').textContent = run.threshold===null?'无匹配阈值 · UNKNOWN':fmt(run.threshold)+' · '+(row.alarm?'ANOMALY':'NORMAL')+'（仅历史域）';
  byId('legend').textContent = !scored?'此试次仅展示采集证据。':run.threshold===null?'实线为连续五帧分数均值。尚不能判定报警。':'实线为窗口分数，虚线为历史域阈值，橙点为离线越线。';
  lineChart();
  const past = run.events.filter(e => e.t <= row.last_read);
  const macro = past.filter(e => e.kind==='macro').at(-1);
  const cp = past.filter(e => e.kind==='checkpoint' && e.height_mm!==null).at(-1);
  byId('events').textContent = macro ? '最近的宏操作：'+operations[macro.name]+'，开始于 '+macro.t.toFixed(3)+' 仿真秒。'+(row.last_read>=macro.end?'该操作已结束，共派发 '+macro.dispatches+' 条命令。':'操作进行中。') : '该位置没有完整链宏派发记录。';
  if(cp) byId('events').textContent += ' 最近检查点 '+cp.name+'，材料高度 '+cp.height_mm.toFixed(1)+' mm。';
  const region = past.find(e => e.kind==='region');
  byId('outcome').textContent = region?'最终区域代理 '+region.inside_count+'/'+region.point_count+'，门槛 '+(100*region.minimum_ratio)+'%。局部恢复、产品质量与自主成功待判。':run.group==='full'?'五操作由脚本发起；可跳至最后一帧查看末态证据。':'本记录没有产品质量或自主成功结论。';
  byId('seek').value=pos; byId('prev').disabled=pos===0; byId('next').disabled=pos===run.rows.length-1;
  byId('jump').value=String(run.rows.findLastIndex((r,i)=>i<=pos && (i===0 || r.phase!==run.rows[i-1].phase)));
}
function go(index) {stop(); pos=Number(index); draw();}
function select() {
  stop(); journal=[]; byId('journal').value=''; run=evidenceTrials[Number(byId('trial').value)]; pos=0;
  byId('seek').max=run.rows.length-1;
  byId('jump').replaceChildren();
  run.rows.forEach((r,i)=>{if(i===0 || r.phase!==run.rows[i-1].phase) byId('jump').add(new Option(r.phase,i));});
  atlas=new Image(); const current=atlas;
  atlas.onload=()=>{if(current===atlas) draw();};
  atlas.onerror=()=>{if(current===atlas){stop();byId('message').textContent='图像文件读取失败，请检查 detection-data 目录。';}};
  byId('message').textContent=''; atlas.src='detection-data/'+run.key+'.jpg'; draw();
}
if(typeof evidenceTrials==='undefined') byId('message').textContent='未找到已导出的试次日志。';
else {
  evidenceTrials.forEach((r,i)=>byId('trial').add(new Option(titles[r.group]+' · '+(condition[r.key.slice(r.group.length+1)]||r.key),i)));
  byId('trial').value=evidenceTrials.findIndex(r=>r.key==='first-release_regrasp');
  byId('journal').onchange=e=>importJournal(e.target.files);
  byId('trial').onchange=select; byId('seek').oninput=e=>go(e.target.value); byId('jump').onchange=e=>go(e.target.value);
  byId('prev').onclick=()=>go(Math.max(0,pos-1)); byId('next').onclick=()=>go(Math.min(run.rows.length-1,pos+1));
  byId('play').onclick=()=>{if(timer!==null){stop();return;} if(pos===run.rows.length-1) go(0);
    byId('play').textContent='暂停回放'; timer=setInterval(()=>{pos++;draw();if(pos===run.rows.length-1)stop();},125);};
  select();
}
