//all of this is bad

console.log('script loaded')
var active = {};
var modal = null;


const url_base = new URL(window.location.pathname, window.location.origin).href;

var topography = {};
var columns = [];
var special_keys = {
    'delay': custom_delay,
    'uut_name': custom_host_link,
    'tty': custom_host_link,
    'ip': custom_host_link,
    'cstate': custom_state_colors,
    'tstate': custom_state_colors,
    'firmware': custom_firmware_title,
    'temp': custom_temp_colors,
};

function main(){
    get_metadata()
}
function get_metadata(){
    let url = new URL(`${url_base}meta.json`);
    send_request(url, 'GET', (status, data) => {
        data = JSON.parse(data)
        topography = data.topography
        columns = data.table_keys
        make_header()
        loop()
    });
}
function make_header(){
    var table_header = document.querySelector('#tableHeader');
    let new_header = document.createElement("tr");


    for (let i = 0; i < 2; i++) {
        new_head = document.createElement("th");
        new_head.style.visibility = 'hidden';
        new_header.appendChild(new_head);
    }
    for (const value of columns) {
        let new_cell = document.createElement("th");
        new_cell.className = value
        new_cell.innerText = value
        new_header.appendChild(new_cell);
    }
    table_header.appendChild(new_header);
}

function loop(){
    if(document.visibilityState != "hidden"){
        get_json();
    }
    setTimeout(loop, 1000);
}
function get_json(){
    let url = new URL(`${url_base}state.json`);
    send_request(url, 'GET', process_json);
}

function send_request(url, method, callback, payload = null){
    var xhr = new XMLHttpRequest();
    xhr.open(method, url.href, true);
    xhr.onreadystatechange = function() {
        if(xhr.readyState == 4) {
            callback(xhr.status, xhr.response);
        }
    }
    if(payload){
        xhr.setRequestHeader('Content-Type', 'application/json');
    }
    xhr.send(payload);
}

function process_json(status, data){
    if(status != 200){
        return
    }
    console.log('processing json')
    rows = JSON.parse(data);
    if(Object.keys(active).length > Object.keys(rows).length){
        let dead_uuts = Object.keys(active).filter(x => Object.keys(rows).indexOf(x) === -1);
        for (const uut of dead_uuts) {
            active[uut].elem.remove()
            delete active[uut];
        }
    }
    total = 0
    for (const [uut_name, value] of Object.entries(rows)) {
        if( active[uut_name] === undefined ){
            active[uut_name] = new row(uut_name);
        }
        active[uut_name].update(value);
        total++
    }
    console.log(total)
    document.querySelector('#total_span').innerText = total;

}
class row {
    constructor(uut_name) {
        this.name = uut_name
        this.state = {}
        var overlay_button = document.querySelector('#overlay_button');
        overlay_button.addEventListener("click", handle_modal);
        overlay_button.dataset.target = 'overlay'
        var container = document.querySelector('#table');//amke tbody
        var tbody = container.querySelector('tbody');//amke tbody
        var rows = document.querySelectorAll(".table_row");
        let new_tr = document.createElement("tr");
        this.elem = new_tr

        this.create_service(new_tr);

        new_tr.className = 'table_row';
        new_tr.dataset.uut_name = uut_name

        for (let column of columns) {
            //var value = data[column]
            let new_td = document.createElement("td");
            new_td.className = column;
            this.state[column] = {};
            this.state[column].value = null;
            this.state[column].elem = new_td;
            this.state[column].func = (value, item, key, row, data) => {
                return value;
            };
            if(special_keys[column] != undefined){
                this.state[column].func = special_keys[column]
            }
            new_td.innerText = ' ';
            new_tr.appendChild(new_td);
        }
        this.elem = new_tr;
        for (const row of rows) {
            if(uut_name.localeCompare(row.dataset.uut_name) < 0){
                row.parentNode.insertBefore(new_tr, row);
                return;
            }
        }
        tbody.appendChild(new_tr);
    }
    update(data){
        for (var [key, item] of Object.entries(this.state)) {
            if(data[key] !== undefined){
                let value = data[key];
                if(item.value != value){
                    item.value = value;
                    item.elem.innerText = item.func(value, item.elem, key, this, data);
                }
            }
        }
    }
    create_service(row){
        let arr = [['post_add', 'claim'], ['electrical_services', 'pdu']]

        var new_cell = document.createElement("td");
        //new_cell.innerText = 'A';
        new_cell.className = 'row_button icon-claim'
        new_cell.dataset.name = this.name;
        new_cell.dataset.target = 'claim';
        new_cell.addEventListener("click", handle_modal);
        this.elem.appendChild(new_cell);
        var new_cell = document.createElement("td");
        //new_cell.innerText = 'E';
        new_cell.className = 'row_button icon-pdu'
        //new_cell.className = 'row_button icon icon-lightbulb_outline'
        new_cell.dataset.name = this.name;
        new_cell.dataset.target = 'pdu';
        new_cell.addEventListener("click", handle_modal);
        this.elem.appendChild(new_cell);
    }
}
function handle_modal(){
    console.log()
    overlay_button = document.querySelector('#overlay_button');
    overlay = document.querySelector('#overlay');
    if(this.dataset.target == 'overlay'){
        overlay.style.display = 'None';
        return
    }
    uut_name = this.dataset.name;
    overlay.style.display = 'block';
    if(modal == null){
        console.log('making a modal')
        modal = new Modal()
    }
    modal.init(uut_name)
    modal.elem.id = this.dataset.target
    modal.node.response.innerText = '...'
}


class Modal{

    constructor() {
        this.values = {}
        this.elem = document.querySelector('.modal_box');
        this.node = {}
        this.node.uut_name = this.elem.querySelector('.modal_title');
        this.node.user = this.elem.querySelector('#claim-input-user');
        this.node.test = this.elem.querySelector('#claim-input-test');
        this.node.pdu = this.elem.querySelector('#claim-input-pdu');
        this.node.pdu_num = this.elem.querySelector('#claim-input-pdu_num');
        this.node.update = this.elem.querySelector('#claim-button-update');
        this.node.erase = this.elem.querySelector('#claim-button-erase');
        this.node.on = this.elem.querySelector('#claim-button-on');
        this.node.off = this.elem.querySelector('#claim-button-off');
        this.node.response = this.elem.querySelector('#claim-response');

        console.log(this.node.update)
        this.node.update.addEventListener('click', this.update_claim)
        this.node.erase.addEventListener('click', this.delete_claim)
        this.node.off.addEventListener('click', this.turn_off)
        this.node.on.addEventListener('click', this.turn_on)
    }
    init(uut_name){
        this.node.uut_name.innerText = uut_name;
        this.node.user.value = active[uut_name].state.user.value
        this.node.test.value = active[uut_name].state.test.value
        this.add_selects(uut_name);
    }
    add_selects(uut_name){
        console.log('add_selects')
        var location = topography[active[uut_name].state.tty.value]
        console.log(location)

        let curr_pdu = active[uut_name].state.pdu.value ? active[uut_name].state.pdu.value.split('::') : [null,null]

        this.node.pdu.innerHTML = '';
        this.node.pdu.appendChild(document.createElement("option"))
        this.node.pdu_num.innerHTML = '';
        this.node.pdu_num.appendChild(document.createElement("option"))

        if(location != undefined && location.pdu != undefined){
            for(let pdu_name of location.pdu){
                let elem = document.createElement("option")
                if(pdu_name == curr_pdu[0]){
                    elem.selected = true;
                }
                elem.value = pdu_name
                elem.innerText = pdu_name
                this.node.pdu.appendChild(elem)
            }

            for(let pdu_num = 1; pdu_num <= location.pdu_num; pdu_num++){
                let elem = document.createElement("option")
                if(pdu_num == curr_pdu[1]){
                    elem.selected = true;
                }
                elem.value = pdu_num
                elem.innerText = pdu_num
                this.node.pdu_num.appendChild(elem)
            }
        }
    }
    get_payload(){
        let payload = {};
        payload.action = 'claim';
        payload.uut = this.node.uut_name.innerText;
        payload.user = this.node.user.value;
        payload.test = this.node.test.value;
        payload.pdu = `${this.node.pdu.value}::${this.node.pdu_num.value}`
        return payload;
    }
    update_claim(){
        let payload = {
            'action'    : 'claim',
            'uut'       : modal.node.uut_name.innerText,
            'user'      : modal.node.user.value,
            'test'      : modal.node.test.value,
            'pdu'       : modal.node.pdu.value,
            'pdu_num'   : modal.node.pdu_num.value
        };
        modal.handle_endpoint(payload)
    }
    delete_claim(){
        let payload = {
            'action'    : 'erase',
            'uut'       : modal.node.uut_name.innerText,
        };
        modal.handle_endpoint(payload)
    }
    turn_off(){
        let payload = {
            'action' : 'off',
            'target' : modal.node.uut_name.innerText
        }
        confirm(`Confirm ${payload.target} shutdown`)
        modal.handle_endpoint(payload)
    }
    turn_on(){
        let payload = {
            'action' : 'on',
            'target' : modal.node.uut_name.innerText
        }
        modal.handle_endpoint(payload)
    }

    handle_endpoint(payload){
        let url = new URL(`${url_base}endpoint`);
        send_request(url, 'POST', function (code, response){
            response = JSON.parse(response)
            //claim_reponse.innerHTML = response;
            console.log(code)
            console.log(response)
            modal.node.response.innerText = response.status
        }, JSON.stringify(payload));
    }
}

function custom_delay(value, elem, key, row, data){
    if(value > 0){
        elem.className = `${key} TIMEOUT`
    } else{
        elem.className = `${key}`
        row.elem.classList.remove('OFFLINE')//fix
    }
    if(value == 'OFF'){
        row.elem.classList.add('OFFLINE')
        console.log('eeeeeeeeeeeee')
    }
    console.log(value)
    return value;
}

function custom_host_link(value, elem, key, row, data){
    if(elem.listener == undefined){
        let url = `http://${value}`
        if(key == 'tty'){
            url = `http://${value}/consoles`
        }
        elem.classList.add('link')
        elem.addEventListener('click', (event) =>{
            window.open(url);
        })
        elem.listener = true
    }
    return value
}
function custom_state_colors(value, elem, key, row, data){
    console.log('custom_state_colors');
    console.log(key)
    elem.className = `${key} ${value}`;
    return value
}
function custom_firmware_title(value, elem, key, row, data){
    elem.title = value;
    return value
}
function custom_temp_colors(value, elem, key, row, data){
    if(value > 50){
        elem.className = `${key} HOT`;
    } else if(value > 40){
        elem.className = `${key} WARM`;
    } else{
        elem.className = key;
    }
    return value
}

main()