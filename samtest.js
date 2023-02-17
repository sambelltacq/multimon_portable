console.log("asdassda");

var headers = false
var uuts = []
function table_builder(data){
    if(!headers){
        console.log('making headers')
        create_headers(data);
        headers = true
    }
    for (const idx in data) {
        add_row(data[idx])
    }
}
function add_row(row_data){
    if(uuts.includes(row_data['uut_name'])){
        console.log("ALREADY ADDED")
        update_row(row_data)
        return
    }
    table = document.getElementById('table1');
    new_row = document.createElement('tr');
    new_row.className = 'dataRow'
    new_row.id = row_data['uut_name']
    for (const key in row_data) {
        new_cell = document.createElement('td');
        new_cell.innerHTML = row_data[key]
        new_cell.id = key
        new_cell.id = key
        new_row.appendChild(new_cell);
        //console.log(`${key}: ${row_data[key]}`);
    }
    table.appendChild(new_row);
    uuts.push(row_data['uut_name'])
}
function update_row(row_data){
    uut_name = row_data['uut_name'];
    row = document.getElementById(uut_name).children;
    for (const element of row) {
        element.innerHTML = row_data[element.id]
        console.log(element);
    }
}
function insert_row(row){
    //localcompare
}
function create_headers(data){
    table = document.getElementById('table1');
    var row = document.createElement('tr');
    row.className = 'headerRow'
    for (const property in data[0]) {
        var cell = document.createElement('th');
        cell.innerHTML = property
        row.appendChild(cell);
    }
    table.appendChild(row);
    uuts.push()
}
function get_json(url, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = 'json';
    xhr.onreadystatechange = function() {
        if(xhr.readyState == 4 && xhr.status == 200) {
            callback(xhr.response)
        }

    }
    xhr.send();
};
function callback(response){
    console.log(response);
    table_builder(response)
}
setInterval(function(){
    //console.log("adasddad")
    //console.log(uuts)
    get_json('state.json', callback)
}, 1000);