fetch("http://34.28.196.192:5000/workers")
.then(response => response.json())
.then(data => {

    const table = document.getElementById("workers-table")

    data.workers.forEach(worker => {

        const row = document.createElement("tr")

        row.innerHTML = `
            <td>${worker[1]}</td>
            <td>${worker[2]}</td>
            <td>${worker[3]}</td>
        `

        table.appendChild(row)

    })

})