const socket = io();
let labels=[],cpuHistory=[],ramHistory=[],diskHistory=[],downHistory=[],upHistory=[];
let processes=[],sortKey="cpu",sortDirection=-1;
const charts={};

function createChart(id,datasets){
 const el=document.getElementById(id);
 if(!el)return;
 charts[id]=new Chart(el,{type:"line",data:{labels:[],datasets:datasets.map(d=>({label:d.label,data:[],borderColor:d.color,backgroundColor:d.color+"22",fill:true,tension:.35,pointRadius:0,borderWidth:2}))},options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{intersect:false,mode:"index"},plugins:{legend:{labels:{color:"#9caac3"}}},scales:{x:{ticks:{color:"#71809d",maxTicksLimit:8},grid:{color:"#202b43"}},y:{beginAtZero:true,ticks:{color:"#71809d"},grid:{color:"#202b43"}}}}});
}
createChart("overviewChart",[{label:"CPU %",color:"#60a5fa"},{label:"RAM %",color:"#a78bfa"},{label:"Disk %",color:"#34d399"}]);
createChart("cpuChart",[{label:"CPU %",color:"#60a5fa"}]);
createChart("ramChart",[{label:"RAM %",color:"#a78bfa"}]);
createChart("networkChart",[{label:"Download KB/s",color:"#60a5fa"},{label:"Upload KB/s",color:"#34d399"}]);

function updateChart(id,series){
 const c=charts[id];if(!c)return;
 c.data.labels=labels.slice();
 c.data.datasets.forEach((d,i)=>d.data=series[i].slice());
 c.update("none");
}
function fmtBytes(v){if(v==null)return "--";return (v/1024/1024/1024).toFixed(2)+" GB"}
function setText(id,value){const e=document.getElementById(id);if(e)e.textContent=value}
function setBar(id,value){const e=document.getElementById(id);if(e)e.style.width=Math.max(0,Math.min(100,value))+"%"}

socket.on("metrics",m=>{
 const cpu=Number(m.cpu)||0,ram=Number(m.ram)||0,disk=Number(m.disk)||0;
 const down=Number(m.down)||0,up=Number(m.up)||0;
 labels.push(new Date().toLocaleTimeString());
 cpuHistory.push(cpu);ramHistory.push(ram);diskHistory.push(disk);
 downHistory.push(down/1024);upHistory.push(up/1024);
 if(labels.length>60){labels.shift();cpuHistory.shift();ramHistory.shift();diskHistory.shift();downHistory.shift();upHistory.shift()}
 setText("cpuValue",cpu.toFixed(1)+"%");setText("cpuDetail",cpu.toFixed(1)+"%");
 setText("ramValue",ram.toFixed(1)+"%");setText("ramDetail",ram.toFixed(1)+"%");
 setText("diskValue",disk.toFixed(1)+"%");
 setText("downValue",(down/1024).toFixed(1)+" KB/s");setText("upValue",(up/1024).toFixed(1)+" KB/s");
 setText("networkDown",(down/1024).toFixed(1)+" KB/s");setText("networkUp",(up/1024).toFixed(1)+" KB/s");
 setBar("cpuBar",cpu);setBar("ramBar",ram);setBar("diskBar",disk);
 setText("ramUsed",fmtBytes(m.ram_used));setText("ramTotal",fmtBytes(m.ram_total));setText("ramAvailable",fmtBytes(m.available));
 updateChart("overviewChart",[cpuHistory,ramHistory,diskHistory]);
 updateChart("cpuChart",[cpuHistory]);updateChart("ramChart",[ramHistory]);
 updateChart("networkChart",[downHistory,upHistory]);
 renderCores(m.cores||[]);
});

function renderCores(cores){
 const html=cores.map((v,i)=>`<div class="core"><strong>${Number(v).toFixed(0)}%</strong><span>Core ${i+1}</span></div>`).join("");
 const a=document.getElementById("coreGrid"),b=document.getElementById("cpuCoreGrid");
 if(a)a.innerHTML=html;if(b)b.innerHTML=html;
 setText("coreCount",cores.length||"--");
}

function showPage(id,button){
 document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
 document.getElementById(id)?.classList.add("active");
 document.querySelectorAll(".nav").forEach(n=>n.classList.remove("active"));
 if(button)button.classList.add("active");
 const titles={overview:"Overview",cpuPage:"CPU Monitoring",memoryPage:"Memory Monitoring",processPage:"Process Manager",networkPage:"Network Monitoring",systemPage:"System Information"};
 setText("pageTitle",titles[id]||"Dashboard");
}

async function loadProcesses(){
 try{
 const r=await fetch("/api/processes");processes=await r.json();
 setText("processCount",processes.length);renderProcesses();
 }catch(e){console.error("Process loading failed",e)}
}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function renderProcesses(){
 const q=(document.getElementById("processSearch")?.value||"").toLowerCase();
 const list=processes.filter(p=>String(p.name).toLowerCase().includes(q)||String(p.pid).includes(q));
 list.sort((a,b)=>{
 let x=a[sortKey],y=b[sortKey];
 if(sortKey==="name"){x=String(x||"").toLowerCase();y=String(y||"").toLowerCase()}
 return (x>y?1:x<y?-1:0)*sortDirection;
 });
 const body=document.getElementById("processTable");if(!body)return;
 body.innerHTML=list.map(p=>`<tr><td>${esc(p.name)}</td><td>${esc(p.pid)}</td><td>${Number(p.cpu||0).toFixed(1)}%</td><td>${Number(p.memory||0).toFixed(1)} MB</td><td>${esc(p.status||"Running")}</td><td><button class="action-btn" onclick="endProcess(${Number(p.pid)},'${esc(p.name).replace(/'/g,"\\'")}')">End Task</button></td></tr>`).join("")||'<tr><td colspan="6">No processes found</td></tr>';
}
function sortProcesses(key){if(sortKey===key)sortDirection*=-1;else{sortKey=key;sortDirection=-1}renderProcesses()}
async function endProcess(pid,name){
 if(!confirm("End process "+name+" (PID "+pid+")? Ending system processes may cause Windows instability."))return;
 try{const r=await fetch("/api/process/"+pid+"/terminate",{method:"POST"});const d=await r.json();alert(d.message||d.error||"Request completed");loadProcesses()}catch(e){alert("Unable to terminate process")}
}
async function loadSystem(){
 try{const r=await fetch("/api/system"),s=await r.json();
 setText("hostname",s.hostname);setText("os",s.os);setText("processor",s.processor);setText("sysCores",s.cpu_count);setText("uptime",s.uptime);
 }catch(e){console.error(e)}
}
loadProcesses();loadSystem();setInterval(loadProcesses,3000);setInterval(loadSystem,15000);
