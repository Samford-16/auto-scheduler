function loadWorkers(){

fetch("http://34.28.196.192:5000/workers")

.then(r=>r.json())

.then(data=>{

const table=document.getElementById("workers-table")

table.innerHTML=""

data.workers.forEach(w=>{

const row=document.createElement("tr")

row.innerHTML=`
<td>${w.name}</td>
<td>${w.max_hours}</td>
<td>${w.overtime}</td>
<td>${w.availability.join(", ")}</td>
<td><button onclick="deleteWorker(${w.id})">Delete</button></td>
`

table.appendChild(row)

})

})

}


function addWorker(){

const name=document.getElementById("name").value
const hours=document.getElementById("hours").value
const overtime=document.getElementById("overtime").value

const days=[]

document.querySelectorAll("input[type=checkbox]:checked").forEach(cb=>{
days.push(cb.value)
})

fetch("http://34.28.196.192:5000/add-worker",{

method:"POST",

headers:{
"Content-Type":"application/json"
},

body:JSON.stringify({
name:name,
max_hours:hours,
overtime:overtime,
availability:days
})

})
.then(()=>window.location.href="dashboard.html")

}


function deleteWorker(id){

fetch(`http://34.28.196.192:5000/delete-worker/${id}`,{
method:"DELETE"
})
.then(()=>loadWorkers())

}


if(document.getElementById("workers-table")){
loadWorkers()
}