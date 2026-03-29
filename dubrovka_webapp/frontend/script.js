document.addEventListener("DOMContentLoaded", () => {

const API = "https://dubrovka-webapp-production-a00c.up.railway.app";

const tg = window.Telegram.WebApp;
tg.expand();

/* элементы */
const phoneInput = document.getElementById("phone");
const nameInput = document.getElementById("name");
const guestsInput = document.getElementById("guests");
const dateInput = document.getElementById("date");
const timeSelect = document.getElementById("time");
const tableInfo = document.getElementById("tableInfo");
const bookBtn = document.getElementById("bookBtn");

let selectedTable = null;

/* описание столов */
const tables = {
"1": "Приватная зона со шторками и PlayStation\nДо 7 гостей",
"2": "Приватная зона со шторками и PlayStation\nДо 5 гостей",
"3": "Приватная зона со шторками и PlayStation\nДо 5 гостей",
"4": "Приватная зона со шторками и PlayStation\nДо 5 гостей",
"5": "Открытая зона без шторок\nДо 5 гостей",
"6": "Компактный стол для 2–3 гостей",
"VIP": "VIP комната (депозитная)\nЧерез администратора"
};

/* дата минимум сегодня */
dateInput.min = new Date().toISOString().split("T")[0];

/* выбор стола */
document.querySelectorAll(".table").forEach(el => {
    el.addEventListener("click", () => {

        document.querySelectorAll(".table").forEach(t => t.classList.remove("selected"));
        el.classList.add("selected");

        selectedTable = el.dataset.table;
        tableInfo.innerText = tables[selectedTable];

        loadTimes();
    });
});

/* генерация времени */
function generateTimes(date){
    let times = [];
    let day = new Date(date).getDay();

    let end = 23;
    if(day === 5 || day === 6) end = 24;

    for(let h = 13; h < end; h++){
        times.push(`${String(h).padStart(2,'0')}:00`);
        times.push(`${String(h).padStart(2,'0')}:30`);
    }

    return times;
}

/* загрузка занятых слотов */
async function loadTimes(){

    if(!dateInput.value || !selectedTable) return;

    try{

        let res = await fetch(`${API}/busy_times?date=${dateInput.value}&table=${selectedTable}`);
        let busy = await res.json();

        let allTimes = generateTimes(dateInput.value);

        timeSelect.innerHTML = '<option value="">Выберите время</option>';

        let now = new Date();

        allTimes.forEach(t => {

            let [h, m] = t.split(":");

            let slot = new Date(dateInput.value);
            slot.setHours(h, m);

            if(slot < now) return;

            if(!busy.includes(t)){
                let option = document.createElement("option");
                option.value = t;
                option.innerText = t;
                timeSelect.appendChild(option);
            }

        });

    }catch(e){
        console.error("Ошибка загрузки времени:", e);
    }
}

/* обновление при смене даты */
dateInput.addEventListener("change", loadTimes);

/* формат телефона */
phoneInput.addEventListener("input", () => {

    let v = phoneInput.value.replace(/\D/g,"");

    if(!v.startsWith("7")) v = "7" + v;

    v = v.slice(0,11);

    phoneInput.value = "+" + v;
});

/* кнопка брони */
bookBtn.addEventListener("click", async () => {

    console.log("КНОПКА НАЖАТА");

    if(!selectedTable){
        alert("Выберите стол");
        return;
    }

    if(selectedTable === "VIP"){
        alert("VIP бронируется через администратора");
        return;
    }

    if(!dateInput.value){
        alert("Выберите дату");
        return;
    }

    if(!timeSelect.value){
        alert("Выберите время");
        return;
    }

    let nameVal = nameInput.value.trim();
    let phoneVal = phoneInput.value;
    let guestsVal = parseInt(guestsInput.value || 0);

    if(!nameVal){
        alert("Введите имя");
        return;
    }

    if(phoneVal.length !== 12){
        alert("Введите корректный номер");
        return;
    }

    let data = {
        name: nameVal,
        phone: phoneVal,
        guests: guestsVal,
        table: selectedTable,
        date: dateInput.value,
        time: timeSelect.value,
        user_id: tg.initDataUnsafe?.user?.id || 0
    };

    try{

        let res = await fetch(API + "/booking", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data)
        });

        let result = await res.json();

        if(result.error){
            alert("❌ Стол уже занят");
            return;
        }

        tg.sendData(JSON.stringify(data));

        alert("✅ Бронь отправлена");

    }catch(e){
        console.error("Ошибка:", e);
        alert("Ошибка соединения с сервером");
    }

});

});
