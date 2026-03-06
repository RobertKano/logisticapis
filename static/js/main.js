/**
 * LogisticAPIs: main.js
 */

// 1. Инициализация из памяти браузера (по умолчанию 'asc' для ближайших дат)
let sortDirection = localStorage.getItem('logisticSortDir') || 'asc';
let currentView = 'active';
let isTkGroupingActive = false;
let fullData = { active: [], archive: [] };

// Проверка режима (по наличию маркера админа в HTML)
const IS_ADMIN = !!document.getElementById('admin-marker');

// Установка иконки при загрузке
document.addEventListener('DOMContentLoaded', () => {
    const icon = document.getElementById('sort-icon');
    if (icon) icon.innerText = (sortDirection === 'asc') ? '🔼' : '🔽';
});

function toggleSort() {
    sortDirection = (sortDirection === 'asc') ? 'desc' : 'asc';
    localStorage.setItem('logisticSortDir', sortDirection); // Запоминаем выбор

    const icon = document.getElementById('sort-icon');
    if (icon) icon.innerText = (sortDirection === 'asc') ? '🔼' : '🔽';

    renderTable();
}

function setView(view) {
    currentView = view;
    document.getElementById('btn-active').classList.toggle('active', view === 'active');
    document.getElementById('btn-archive').classList.toggle('active', view === 'archive');
    renderTable();
}

function copyToClipboard(id, btn) {
    const combined = [...(fullData.active || []), ...(fullData.archive || [])];
    const item = combined.find(r => String(r.id) === String(id));

    if (!item) return;

    const tkName = item.tk || "ТК";
    const route = item.route || "Маршрут не указан";
    const sender = item.sender || "Отправитель не указан";
    const params = item.params || "Параметры не заданы";

    let payStatus = "";
    const pRaw = (item.payment || "").toLowerCase();
    const isPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');
    payStatus = isPaid ? "✅ Оплачено" : `⚠️ ${item.payment.toUpperCase()}`;
    const text = `${tkName} (${route})\n${sender} (${item.id})\n${params}\n${payStatus}`;

    const showSuccess = () => {
        const old = btn.innerHTML;
        btn.innerHTML = '✅';
        setTimeout(() => btn.innerHTML = old, 1500);
    };

    // Fallback для HTTP соединений
    try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed"; ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.focus(); ta.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (ok) return showSuccess();
    } catch (e) {
        console.error("Ошибка копирования", e)
    }

    // Современный метод
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(showSuccess);
    }
}

function renderTable() {
    const tbody = document.getElementById('report-table-body');
    if (!tbody) return;

    // Проверка наличия данных
    if (!fullData) return;
    let list = [...(fullData[currentView] || [])];
    tbody.innerHTML = '';

    list.sort((a, b) => {
        // --- 1. ЕСЛИ ВКЛЮЧЕН ТРИГГЕР: Сначала сортируем по ТК (Алфавит) ---
        if (isTkGroupingActive) {
            const tkA = (a.tk || "").toUpperCase();
            const tkB = (b.tk || "").toUpperCase();
            if (tkA < tkB) return -1;
            if (tkA > tkB) return 1;
        }

        // --- 2. ВСЕГДА: Сортировка по дате (Твоя базовая логика) ---
        const toDate = (val) => {
            if (!val) return new Date(1970, 0, 1);
            if (typeof val === 'string' && val.includes('.')) {
                const [d, m, y] = val.split('.');
                return new Date(y, m - 1, d);
            }
            return new Date(val);
        };
        const dateA = toDate(a.arrival || a.archived_at);
        const dateB = toDate(b.arrival || b.archived_at);

        return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
    });



    // 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
    const shortenMyName = (name) => {
        if (!name) return '—';
        const upper = name.toUpperCase();
        if (upper.includes("ЮЖНЫЙ ФОРПОСТ")) {
            return '<b style="color: #4f46e5;">МЫ</b>';
        }
        return name;
    };

    let totalSum = 0;

    // 3. ОТРИСОВКА СТРОК
    list.forEach(r => {
        const tr = document.createElement('tr');
        const rawStatus = (r.status || '').toLowerCase();
        let displayStatus = r.status || (currentView === 'archive' ? 'Завершен' : '—');
        let statusClass = "text-dark";

        // Суммируем стоимость для счетчика
        totalSum += parseFloat(r.total_price || 0);

        // --- МАППИНГ СТАТУСОВ (С ЗАЩИТОЙ ПРОГНОЗА БСД) ---
                // --- МАППИНГ СТАТУСОВ (БЕЗ ДУБЛЕЙ ИКОНОК) ---
        const isWaiting = rawStatus.includes('прогноз') || rawStatus.includes('подготовка') || rawStatus.includes('ожидает') || rawStatus.includes('отправка');

        let icon = "";

        // if (isWaiting) {
        //     icon = "🚚 ";
        //     displayStatus = r.status; // ПОДГОТОВКА К ОТПРАВКЕ...
        //     statusClass = "text-primary";
        //     tr.classList.remove('row-arrived');
        // }
        // else if (rawStatus.includes('прибыл') || rawStatus.includes('готов') || rawStatus.includes('хранение')) {
        //     icon = "✅ ";
        //     displayStatus = "Прибыл в ТК";
        //     statusClass = "text-success";
        //     tr.classList.add('row-arrived');
        // }
        // else if (rawStatus.includes('пути') || rawStatus.includes('транзит') || rawStatus.includes('принят')){
        //     icon = "🚚 ";
        //     displayStatus = "В пути";
        //     statusClass = "text-primary";
        // }
        // else if (rawStatus.includes('оставк') || rawStatus.includes('до адреса')){
        //     icon = "🚚 ";
        //     displayStatus = "Доставка ТК ➡️ СКЛАД";
        //     statusClass = "text-success";
        //     tr.classList.add('row-arrived');
        // }ПРИБЫЛ В ГОРОД НАЗНАЧЕНИЯ
        // 1. САМЫЙ ВЫСОКИЙ ПРИОРИТЕТ - ДОСТАВКА (чтобы не перекрывалось "прибытием")
        if (rawStatus.includes('оставк') || rawStatus.includes('до адреса') || rawStatus.includes('прибыл в город назначения'))  {
            icon = "🚚 ";
            displayStatus = "Доставка ТК ➡️ СКЛАД";
            statusClass = "text-success";
            tr.classList.add('row-arrived');
        }
        // 2. ПОДГОТОВКА (isWaiting)
        else if (isWaiting) {
            icon = "🚚 ";
            displayStatus = r.status;
            statusClass = "text-primary";
            tr.classList.remove('row-arrived');
        }
        // 3. ПРИБЫЛ (Самовывоз)
        else if (rawStatus.includes('прибыл') || rawStatus.includes('готов') || rawStatus.includes('хранение')) {
            icon = "✅ ";
            displayStatus = "Прибыл в ТК";
            statusClass = "text-success";
            tr.classList.add('row-arrived');
        }
        // 4. В ПУТИ
        else if (rawStatus.includes('пути') || rawStatus.includes('транзит') || rawStatus.includes('принят')) {
            icon = "🚚 ";
            displayStatus = "В пути";
            statusClass = "text-primary";
        }

        // Собираем итоговую строку статуса с ОДНОЙ иконкой
        const finalStatusHtml = `<span class="${statusClass}">${icon}${displayStatus}</span>`;


        // --- ЛОГИКА ОПЛАТЫ ---
        const pRaw = (r.payment || "").toLowerCase();
        const isActuallyPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');

        let pStyle = isActuallyPaid ? "text-success fw-bold" : "badge bg-danger text-white px-2 py-1 shadow-sm";
        let pDisplay = isActuallyPaid ? "✅ Оплачено" : "⚠️ " + (r.payment || "уточнить");

        // --- ТК И СТИЛИ ---
        const tkName = r.tk || "—";
        const upperTK = tkName.toUpperCase();
        let tkColorClass = "tk-manual";

        if (upperTK.includes('ПЭК')) tkColorClass = "tk-pecom";
        else if (upperTK.includes('ДЕЛОВЫЕ')) tkColorClass = "tk-dellin";
        else if (upperTK.includes('БАЙКАЛ')) tkColorClass = "tk-baikal";
        else if (upperTK.includes('БСД') || upperTK.includes('ВИТЕКА')) tkColorClass = "tk-bsd";

        let payerIcon = r.payer_type === 'recipient' ? '<span class="ms-1" title="Платим мы">⬇️</span>' :
                        r.payer_type === 'sender' ? '<span class="ms-1" title="Платит отправитель">⬆️</span>' :
                        '<span class="ms-1" title="Третье лицо">👤</span>';

        // --- ГАБАРИТЫ ---
        let heavyIcon = '', oversizeIcon = '';
        const paramsStr = r.params || "";
        const weightMatch = paramsStr.match(/([\d.]+)\s*кг/i);
        const volumeMatch = paramsStr.match(/([\d.]+)\s*м3/i);
        const placesMatch = paramsStr.match(/(\d+)\s*м/i);

        const weight = weightMatch ? parseFloat(weightMatch[1]) : 0;
        const volume = volumeMatch ? parseFloat(volumeMatch[1]) : 0;
        const places = placesMatch ? parseInt(placesMatch[1]) : 1;

        const kettlebellSvg = `<svg xmlns="http://www.w3.org" viewBox="0 0 24 24" width="20" height="20" style="fill: #000000; vertical-align: middle;"><path d="M16.2 10.7L16.8 8.3C16.9 8 17.3 6.6 16.5 5.4C15.9 4.5 14.7 4 13 4H11C9.3 4 8.1 4.5 7.5 5.4C6.7 6.6 7.1 7.9 7.2 8.3L7.8 10.7C6.7 11.8 6 13.3 6 15C6 17.1 7.1 18.9 8.7 20H15.3C16.9 18.9 18 17.1 18 15C18 13.3 17.3 11.8 16.2 10.7M9.6 9.5L9.1 7.8V7.7C9.1 7.7 8.9 7 9.2 6.6C9.4 6.2 10 6 11 6H13C13.9 6 14.6 6.2 14.9 6.5C15.2 6.9 15 7.6 15 7.6L14.5 9.5C13.7 9.2 12.9 9 12 9C11.1 9 10.3 9.2 9.6 9.5Z" /></svg>`;

        if (weight / places > 35 || weight > 150) {
            heavyIcon = `<span class="heavy-badge" title="Тяжелый: ${weight}кг">${kettlebellSvg}</span>`;
        }
        if (volume > 1.5) {
            oversizeIcon = `<span class="oversize-badge" title="Габаритный: ${volume}м3">${kettlebellSvg}</span>`;
        }

        // --- ДАТЫ ---
        const rawDate = r.arrival ? r.arrival.split('T')[0] : (r.archived_at ? (r.archived_at.includes('.') ? r.archived_at.split('.').reverse().join('-') : r.archived_at) : '0000-00-00');
        const displayDate = r.arrival ? r.arrival.split('T')[0] : (r.archived_at || '—');

        tr.setAttribute('data-sender', (r.sender || "").toLowerCase());
        tr.setAttribute('data-receiver', (r.recipient || "").toLowerCase());

        tr.innerHTML = `
            <td data-label="ТК"><span class="badge-tk ${tkColorClass}">${tkName}</span></td>
            <td data-label="№ Накладной">
                <code>${String(r.id || '').split('_')[0]}</code> ${payerIcon}
                <span class="copy-btn" onclick="copyToClipboard('${r.id}', this)" title="Копировать">📋</span>
            </td>
            <td data-label="Отправитель">${shortenMyName(r.sender)}</td>
            <td data-label="Получатель">${shortenMyName(r.recipient)}</td>
            <td data-label="Маршрут">${r.route || '—'}</td>
            <td data-label="Груз"><small>${r.params || '—'}</small> ${heavyIcon}${oversizeIcon}</td>
            <td data-label="Статус" class="fw-bold">${finalStatusHtml}</td>
            <td data-label="Прибытие" data-date="${rawDate}">
                <strong>${displayDate}</strong>
            </td>
            <td data-label="Оплата">
                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                    <span class="${pStyle}">${pDisplay}</span>

                    <!-- Выводим сумму только если она больше 0 -->
                    ${r.total_price > 0 ? `
                        <span style="font-size: 0.72rem; color: #6c757d; font-weight: 600; margin-top: 2px;">
                            ${parseFloat(r.total_price).toLocaleString('ru-RU')} ₽
                        </span>
                    ` : ''}
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // 4. ОБНОВЛЕНИЕ ИТОГОВОЙ СУММЫ (если элемент есть)
    const sumDisplay = document.getElementById('total-sum-value');
    if (sumDisplay) {
        sumDisplay.innerText = totalSum.toLocaleString('ru-RU') + ' ₽';
    }

    // Запуск фильтрации
    if (typeof filterTable === 'function') filterTable();
}



/**
 * Загрузка данных отчета и обновление статистики плиток
 */
function loadReportData() {
    const btn = document.getElementById('refresh-btn');
    const statusInd = document.getElementById('api-status');

    // Включаем индикацию загрузки (синий пульс)
    if (btn) btn.disabled = true;
    if (statusInd) statusInd.classList.add('loading');

    fetch('/api/latest')
        .then(res => {
            if (!res.ok) throw new Error('Ошибка сети или файл не найден');
            return res.json();
        })
        .then(data => {
            // Сохраняем полученные данные в глобальную переменную
            fullData = data;

            if (document.getElementById('count-active')) {
                document.getElementById('count-active').textContent = (data.active || []).length;
            }
            if (document.getElementById('count-archive')) {
                document.getElementById('count-archive').textContent = (data.archive || []).length;
            }

            // 1. Обновляем время синхронизации
            const timeEl = document.getElementById('update-time');
            if (timeEl) timeEl.textContent = data.metadata?.created_at || "Н/Д";

            // 2. Считаем статистику для плиток (с защитой от пустых данных)
            const activeList = data.active || [];

            // Плитка "ВСЕГО АКТИВНЫХ"
            const totalEl = document.getElementById('stat-total');
            if (totalEl) totalEl.textContent = activeList.length;

            // Плитка "ГОТОВО К ЗАБОРУ" (Прибыл, Готов, Хранение, Склад)
            const readyEl = document.getElementById('stat-ready');
            if (readyEl) {
                readyEl.textContent = activeList.filter(r => {
                    const s = (r.status || "").toLowerCase();
                    return ["прибыл", "готов", "хранение", "склад"].some(word => s.includes(word));
                }).length;
            }

            // Плитка "В ПУТИ" (Пути, Транзит, Принят)
            const transitEl = document.getElementById('stat-transit');
            if (transitEl) {
                transitEl.textContent = activeList.filter(r => {
                    const s = (r.status || "").toLowerCase();
                    return ["пути", "транзит", "принят"].some(word => s.includes(word));
                }).length;
            }

            // Плитка "ОЖИДАЮТ ОПЛАТЫ" (К ОПЛАТЕ, ДОЛГ)
            const debtEl = document.getElementById('stat-debt');
            if (debtEl) {
                debtEl.textContent = activeList.filter(r => {
                    const p = (r.payment || "").toLowerCase();
                    return p.includes("к оплате") || p.includes("долг");
                }).length;
            }

            // 3. Запускаем отрисовку таблицы
            renderTable();
        })
        .catch(err => {
            console.error("Ошибка загрузки данных:", err);
            // Если данных нет, обнуляем счетчики
            ['stat-total', 'stat-ready', 'stat-transit', 'stat-debt'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.textContent = "0";
            });
        })
        .finally(() => {
            // Выключаем индикацию загрузки
            if (btn) btn.disabled = false;
            if (statusInd) statusInd.classList.remove('loading');
        });
}


const searchInput = document.getElementById('searchInput');
const clearBtn = document.getElementById('clearSearch');

if(searchInput) {
    searchInput.addEventListener('input', function() {
        if(clearBtn) clearBtn.style.display = this.value.length > 0 ? 'block' : 'none';
        filterTable();
    });
}

if(clearBtn) {
    clearBtn.addEventListener('click', function() {
        searchInput.value = '';
        this.style.display = 'none';
        searchInput.focus();
        filterTable();
    });
}


// --- ФУНКЦИИ ФИЛЬТРАЦИИ И ПОИСКА ---

function filterByStat(type, element) {
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearch');
    if (!searchInput) return;

    // Сбрасываем стили со всех карточек
    document.querySelectorAll('.stat-card').forEach(card => {
        card.classList.remove('active-filter');
        card.style.borderColor = "";
    });

    let filterValue = "";
    if (type === 'ready') filterValue = "Прибыл";
    if (type === 'transit') filterValue = "В пути";
    if (type === 'debt') filterValue = "К ОПЛАТЕ";

    searchInput.value = filterValue;

    // Подсветка активной карточки цветом её цифр
    if (type !== 'total' && filterValue !== "") {
        element.classList.add('active-filter');
        const valueColor = window.getComputedStyle(element.querySelector('.stat-value')).color;
        element.style.borderColor = valueColor;
    }

    if (clearBtn) clearBtn.style.display = filterValue.length > 0 ? 'block' : 'none';
    filterTable();
}

function filterTable() {
    const searchInput = document.getElementById('searchInput');
    const dateInput = document.getElementById('dateFilter');

    // 1. Базовая проверка на существование элементов
    if (!searchInput || !dateInput) return;

    const textFilter = searchInput.value.toLowerCase();
    const dateValue = dateInput.value; // Используем одно имя для значения даты

    // 2. Сброс быстрых кнопок (7д/30д), если пользователь выбрал конкретную дату в календаре
    if (dateValue) {
        window.quickRange = 'all';
        document.querySelectorAll('.btn-quick').forEach(btn => btn.classList.remove('active'));
    }

    // 3. Настройки для диапазона (неделя/месяц)
    const now = new Date();
    const cutoff = new Date();
    if (window.quickRange === 'week') cutoff.setDate(now.getDate() - 7);
    if (window.quickRange === 'month') cutoff.setMonth(now.getMonth() - 1);

    // 4. Основной цикл фильтрации строк
    document.querySelectorAll('#report-table-body tr').forEach(row => {
        // Поиск по тексту (ТК, номер, отправитель)
        const searchPool = row.textContent.toLowerCase() + " " +
                           (row.getAttribute('data-sender') || "") + " " +
                           (row.getAttribute('data-receiver') || "");

        // Получаем дату строки из атрибута
        const rowDateStr = row.querySelector('[data-date]')?.getAttribute('data-date');
        const rowDate = new Date(rowDateStr);

        let matchesDate = true;

        if (dateValue) {
            // Фильтр по конкретному дню из календаря
            matchesDate = rowDateStr === dateValue;
        } else if (window.quickRange === 'week' || window.quickRange === 'month') {
            // Фильтр по диапазону (7д или 30д)
            matchesDate = rowDate >= cutoff && rowDate <= now;
        }

        const matchesText = searchPool.includes(textFilter);

        // Показываем строку, только если совпал и ТЕКСТ, и ДАТА
        row.style.display = (matchesText && matchesDate) ? '' : 'none';
    });
}


function quickDateFilter(range) {
    const dateInput = document.getElementById('dateFilter');
    if (dateInput) dateInput.value = ''; // Сбрасываем календарь

    // 1. Логика переключения состояния (триггер)
    // Если нажали ту же кнопку — сбрасываем в 'all', если другую — ставим новый range
    window.quickRange = (window.quickRange === range) ? 'all' : range;

    // 2. Управление подсветкой кнопок
    const buttons = document.querySelectorAll('.btn-quick');
    buttons.forEach(btn => {
        // Убираем активный класс у всех кнопок в начале
        btn.classList.remove('active');

        // Если фильтр НЕ сброшен, ищем кнопку, на которую нажали, и зажигаем её
        if (window.quickRange !== 'all') {
            // Проверяем, содержит ли текст кнопки цифру (7 или 30)
            if (btn.innerText.includes(range === 'week' ? '7' : '30')) {
                btn.classList.add('active');
            }
        }
    });

    // 3. Запускаем фильтрацию таблицы
    filterTable();
}
window.onbeforeprint = () => {
    const printBody = document.getElementById('print-table-body');
    const printDate = document.getElementById('print-date');
    if (printDate) printDate.innerText = new Date().toLocaleString();

    printBody.innerHTML = '';
    const visibleRows = document.querySelectorAll('#report-table-body tr:not([style*="display: none"])');

    // 1. Отрисовка реальных данных
    visibleRows.forEach(row => {
        const tk = row.cells[0]?.innerText || "—";
        const sender = row.cells[2]?.innerText || "—";
        const params = row.cells[5]?.innerText || "—";

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="border: 1px solid #000; padding: 8px 4px; width: 12%; font-size: 8pt; text-align: center;">${tk}</td>
            <td style="border: 1px solid #000; padding: 8px 6px; width: 35%; font-weight: bold; font-size: 10pt;">${sender}</td>
            <td style="border: 1px solid #000; padding: 8px 4px; width: 20%; font-size: 11pt; font-weight: bold; text-align: center;">${params}</td>
            <td style="border: 1px solid #000; padding: 8px 4px; width: 8%;"></td>
            <td style="border: 1px solid #000; padding: 8px 4px; width: 25%;"></td>
        `;
        printBody.appendChild(tr);
    });

    // 2. ДОБАВЛЯЕМ ПУСТЫЕ СТРОКИ ДЛЯ СКЛАДА (5 штук)
    for (let i = 0; i < 5; i++) {
        const emptyTr = document.createElement('tr');
        emptyTr.className = 'empty-print-row'; // Подхватит 50px из твоего CSS
        emptyTr.innerHTML = `
            <td style="border: 1px solid #000; height: 50px;"></td>
            <td style="border: 1px solid #000;"></td>
            <td style="border: 1px solid #000;"></td>
            <td style="border: 1px solid #000;"></td>
            <td style="border: 1px solid #000;"></td>
        `;
        printBody.appendChild(emptyTr);
    }
};


function toggleTkGrouping() {
    isTkGroupingActive = !isTkGroupingActive;

    const btn = document.getElementById('group-tk-btn');
    const icon = document.getElementById('group-tk-icon');

    if (isTkGroupingActive) {
        // Активный режим (Синий текст, иконка списка с точками)
        btn.style.color = "#4f46e5";
        btn.style.backgroundColor = "#eef2ff";
        icon.innerText = "☷";
        btn.innerHTML = `<span id="group-tk-icon" class="me-1">☷</span> ГРУППА: ВКЛ`;
    } else {
        // Обычный режим (Серый текст, иконка плоского списка)
        btn.style.color = "#64748b";
        btn.style.backgroundColor = "transparent";
        icon.innerText = "☰";
        btn.innerHTML = `<span id="group-tk-icon" class="me-1">☰</span> ГРУППА`;
    }

    renderTable(); // Перерисовываем
}

// --- ЗАПУСК И СЛУШАТЕЛИ ---

document.addEventListener('DOMContentLoaded', () => {
    const dF = document.getElementById('dateFilter');
    const sI = document.getElementById('searchInput');

    if (dF) dF.addEventListener('change', filterTable);
    if (sI) sI.addEventListener('keyup', filterTable);

    loadReportData();
    setInterval(loadReportData, 60000); // Обновление каждую минуту
});
