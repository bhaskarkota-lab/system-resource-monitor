function renderProcesses(){
let q=document.getElementById("search").value.toLowerCase();
let sort=document.getElementById("sort").value;
let rows=processData.filter(p=>(p.name||"").toLowerCase().includes(q));
rows.sort((a,b)=>sort==="name"?a.name.localeCompare(b.name):b[sort]-a[sort]);
document.getElementById("processes").innerHTML=rows.map(p=>`
<tr>
<td>${p.name}</td>
<td>${p.pid}</td>
<td>${p.cpu.toFixed(1)}%</td>
<td>${(p.memory/1024/1024).toFixed(1)} MB</td>
<td><button onclick="endProcess(${p.pid},'${p.name}')">End Task</button></td>
</tr>`).join("");
}
async function loadProcesses(){
processData=await fetch("/api/processes").then(r=>r.json());
renderProcesses();
}
async function endProcess(pid,name){
if(!confirm("Terminate "+name+" (PID "+pid+")?"))return;
let r=await fetch("/api/process/"+pid+"/terminate",{method:"POST"});
let d=await r.json();
if(d.success){alert("Process terminated");loadProcesses()}
else alert("Could not terminate: "+d.error);
}
document.getElementById("search").oninput=renderProcesses;
document.getElementById("sort").onchange=renderProcesses;
loadProcesses();
setInterval(loadProcesses,3000);
