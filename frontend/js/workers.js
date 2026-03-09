console.log("workers.js loaded");

function loadWorkers(){

fetch("http://localhost:5000/workers")
.then(response => response.json())
.then(data => {

const table = document.getElementById("workers-table")

table.innerHTML = ""

data.workers.forEach(worker => {

const row = document.createElement("tr")

row.innerHTML = `
<td>${worker[1]}</td>
<td>${worker[2]}</td>
<td>${worker[3]}</td>
<td><button onclick="deleteWorker(${worker[0]})">Delete</button></td>
`

table.appendChild(row)

})

})

}

loadWorkers()