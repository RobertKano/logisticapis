/**
 * LogisticAPIs: main.js
 */

// 1. Инициализация из памяти браузера (по умолчанию 'asc' для ближайших дат)
let sortDirection = localStorage.getItem('logisticSortDir') || 'asc';
let currentView = 'active';
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
    if (item.is_manual) {
        payStatus = `📝 СТАТУС: ${item.status || 'Заметка'}`;
    } else {
        const pRaw = (item.payment || "").toLowerCase();
        const isPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');
        payStatus = isPaid ? "✅ Оплачено" : `⚠️ ${item.payment.toUpperCase()}`;
    }
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
    let list = [...(fullData[currentView] || [])];
    tbody.innerHTML = '';

    list.sort((a, b) => {
        // Упрощенный парсер: превращает любую строку даты в объект Date
        const toDate = (val) => {
            if (!val) return new Date(1970, 0, 1); // Если даты нет - в самый низ

            // Если дата пришла в старом формате 25.02.2026 (с точками)
            if (typeof val === 'string' && val.includes('.')) {
                const [d, m, y] = val.split('.');
                return new Date(y, m - 1, d);
            }

            // Если дата в новом формате 2026-02-25 или ISO
            return new Date(val);
        };

        const dateA = toDate(a.arrival || a.archived_at);
        const dateB = toDate(b.arrival || b.archived_at);

        // Стандартное сравнение: asc (старые -> новые), desc (новые -> старые)
        return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
    });


    const shortenMyName = (name) => {
        if (!name) return '—';
        const upper = name.toUpperCase();
        if (upper.includes("ЮЖНЫЙ ФОРПОСТ")) {
            return '<b style="color: #4f46e5;">МЫ</b>';
        }
        return name;
    };

    list.forEach(r => {
        const tr = document.createElement('tr');
        const rawStatus = (r.status || '').toLowerCase();
        let displayStatus = r.status || (currentView === 'archive' ? 'Завершен' : '—');
        let statusClass = "text-dark";

        // --- ЛОГИКА ПАМЯТОК И УПРАВЛЕНИЯ ---
        let priorityIcon = "";
        let deleteBtn = "";

        if (r.is_manual) {
            tr.classList.add('memo-row');
            if (document.getElementById('m_id')) {
                deleteBtn = `
                    <span class="ms-2" onclick="editManualCargo('${r.id}')" style="cursor:pointer; color:#6366f1;" title="Редактировать">✏️</span>
                    <span class="ms-1" onclick="deleteManualCargo('${r.id}')" style="cursor:pointer; opacity:0.6;" title="Удалить памятку">🗑️</span>
                `;
            }
            if (r.priority === 'high') {
                tr.classList.add('memo-high');
                priorityIcon = "🚨 ";
            } else if (r.priority === 'medium') {
                tr.classList.add('memo-medium');
                priorityIcon = "⚠️ ";
            } else {
                priorityIcon = "📌 ";
            }
        }

        // --- МАППИНГ СТАТУСОВ ---
        if (rawStatus.includes('прибыл') || rawStatus.includes('готов') || rawStatus.includes('хранение')) {
            displayStatus = "✅ Прибыл в ТК";
            statusClass = "text-success";
            tr.classList.add('row-arrived');
        } else if (rawStatus.includes('пути') || rawStatus.includes('транзит') || rawStatus.includes('принят')){
            displayStatus = "🚚 В пути";
            statusClass = "text-primary";
        } else if (rawStatus.includes('оставк') || rawStatus.includes('до адреса')){
            displayStatus = "🚚 Доставка ТК ➡️ СКЛАД";
            statusClass = "text-success";
            tr.classList.add('row-arrived');
        }

        const pRaw = (r.payment || "").toLowerCase();
        const isActuallyPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');
        // --- ЛОГИКА ОПЛАТЫ (Спокойная для памяток) ---
        let pStyle = "";
        let pDisplay = "";

        if (r.is_manual) {
            // Для ручных памяток делаем серый неброский текст
            pStyle = "text-muted small italic";
            pDisplay = "уточнить";
        } else {
            // Для официальных грузов ТК оставляем твою боевую логику
            const pRaw = (r.payment || "").toLowerCase();
            const isActuallyPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');

            pStyle = isActuallyPaid ? "text-success fw-bold" : "badge bg-danger text-white px-2 py-1 shadow-sm";
            pDisplay = isActuallyPaid ? "✅ Оплачено" : "⚠️ " + (r.payment || "уточнить");
        }

        // --- ИСПРАВЛЕНИЕ: БЕЗОПАСНЫЙ ТК И СТИЛЬ ---
        const tkName = r.tk || (r.is_manual ? "📝 ПАМЯТКА" : "—");
        let tkStyle = "background: #f1f5f9; color: #475569;";
        if(r.tk) {
            if(r.tk.includes('ПЭК')) tkStyle = "background: #fef9c3; color: #854d0e; border: 1px solid #fde047;";
            if(r.tk.includes('Деловые')) tkStyle = "background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe;";
        }

        let payerIcon = r.payer_type === 'recipient' ? '<span class="ms-1" title="Платим мы">⬇️</span>' :
                        r.payer_type === 'sender' ? '<span class="ms-1" title="Платит отправитель">⬆️</span>' :
                        '<span class="ms-1" title="Третье лицо">👤</span>';

        // --- ГАБАРИТЫ ---
        let heavyIcon = '', oversizeIcon = '';
        const paramsStr = r.params || "";
        const weightMatch = paramsStr.match(/([\d.]+)\s*кг/);
        const volumeMatch = paramsStr.match(/([\d.]+)\s*м3/);
        const placesMatch = paramsStr.match(/(\d+)\s*м/);

        const weight = weightMatch ? parseFloat(weightMatch[1]) : 0;
        const volume = volumeMatch ? parseFloat(volumeMatch[1]) : 0;
        const places = placesMatch ? parseInt(placesMatch[1]) : 1;

        const kettlebellSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" style="fill: #000000; vertical-align: middle;"><path d="M16.2 10.7L16.8 8.3C16.9 8 17.3 6.6 16.5 5.4C15.9 4.5 14.7 4 13 4H11C9.3 4 8.1 4.5 7.5 5.4C6.7 6.6 7.1 7.9 7.2 8.3L7.8 10.7C6.7 11.8 6 13.3 6 15C6 17.1 7.1 18.9 8.7 20H15.3C16.9 18.9 18 17.1 18 15C18 13.3 17.3 11.8 16.2 10.7M9.6 9.5L9.1 7.8V7.7C9.1 7.7 8.9 7 9.2 6.6C9.4 6.2 10 6 11 6H13C13.9 6 14.6 6.2 14.9 6.5C15.2 6.9 15 7.6 15 7.6L14.5 9.5C13.7 9.2 12.9 9 12 9C11.1 9 10.3 9.2 9.6 9.5Z" /></svg>`;

        if (weight / places > 35 || weight > 150) {
            heavyIcon = `<span class="heavy-badge" title="Тяжелый: ${weight}кг">${kettlebellSvg}</span>`;
        }
        if (volume > 1.5) {
            oversizeIcon = `<span class="oversize-badge" title="Габаритный: ${volume}м3">${kettlebellSvg}</span>`;
        }

        // --- ИСПРАВЛЕНИЕ ДАТЫ ---
        const rawDate = r.arrival ? r.arrival.split('T')[0] : (r.archived_at ? (r.archived_at.includes('.') ? r.archived_at.split('.').reverse().join('-') : r.archived_at) : '0000-00-00');
        const displayDate = r.arrival ? r.arrival.split('T')[0] : (r.archived_at || '—');

        tr.setAttribute('data-sender', (r.sender || "").toLowerCase());
        tr.setAttribute('data-receiver', (r.recipient || "").toLowerCase());

        tr.innerHTML = `
            <td data-label="ТК"><span class="badge-tk" style="${tkStyle}">${tkName}</span></td>
            <td data-label="№ Накладной">
                <code>${String(r.id || '').split('_')[0]}</code> ${priorityIcon}${payerIcon}${deleteBtn}
                <span class="copy-btn" onclick="copyToClipboard('${r.id}', this)" title="Копировать">📋</span>
            </td>
            <td data-label="Отправитель">${shortenMyName(r.sender)}</td>
            <td data-label="Получатель">${shortenMyName(r.recipient)}</td>
            <td data-label="Маршрут">${r.route || '—'}</td>
            <td data-label="Груз"><small>${r.params || '—'}</small> ${heavyIcon}${oversizeIcon}</td>
            <td data-label="Статус" class="fw-bold ${statusClass}">${displayStatus}</td>
            <td data-label="Прибытие" data-date="${rawDate}">
                <strong>${displayDate}</strong>
            </td>
            <td data-label="Оплата"><span class="${pStyle}">${pDisplay}</span></td>
        `;
        tbody.appendChild(tr);
    });

    filterTable();
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


// --- АДМИН-ФУНКЦИИ (Универсальные: Создание + Редактирование + Удаление) ---

// 1. Функция ПОДГОТОВКИ к редактированию (заполняет форму данными из таблицы)
function editManualCargo(id) {
    // Ищем данные этой памятки в текущем списке активных грузов
    const item = (fullData.active || []).find(r => String(r.id) === String(id));
    if (!item) return;

    // 1. РАЗБОР МАРШРУТА (МСК ➡️ АСТРА)
    const routeParts = (item.route || "").split(' ➡️ ');
    const routeFrom = routeParts[0] || "";
    const routeTo = routeParts[1] || "";

    // 2. РАЗБОР ПАРАМЕТРОВ (3м | 10кг | 0.1м3)
    const p = item.params || "";
    const p_m = (p.match(/(\d+)м/) || ['', ''])[1];
    const p_w = (p.match(/([\d.]+)кг/) || ['', ''])[1];
    const p_v = (p.match(/([\d.]+)м3/) || ['', ''])[1];

    // 3. Заполняем все поля формы админки
    const fields = {
        'm_edit_id': item.id,
        'm_id': item.id,
        'm_sender': item.sender,
        // Поля маршрута
        'm_route_from': routeFrom,
        'm_route_to': routeTo,
        // Поля параметров
        'm_p_m': p_m,
        'm_p_w': p_w,
        'm_p_v': p_v,
        // Статус и приоритет
        'm_status': item.status,
        'm_priority': item.priority || 'low'
    };

    for (const [id, value] of Object.entries(fields)) {
        const el = document.getElementById(id);
        if (el) el.value = value;
    }

    // 4. Визуально меняем кнопку "OK" на "Обновить"
    const btn = document.getElementById('m_btn_save');
    if (btn) {
        btn.textContent = "Обновить";
        btn.classList.remove('btn-indigo');
        btn.style.backgroundColor = "#f59e0b"; // Оранжевый цвет для режима правки
        btn.style.color = "#000";
    }

    // Скроллим вверх к форме
    window.scrollTo({ top: 0, behavior: 'smooth' });
}


// 2. Универсальная функция СОХРАНЕНИЯ (сама понимает: добавить или обновить)
async function saveManualCargo() {
    const editId = document.getElementById('m_edit_id').value;

    // Если есть editId — идем на роут обновления, если нет — на создание
    const url = editId ? '/admin/update-manual' : '/admin/add-manual';
    // Если мы редактируем, ищем старый объект, чтобы забрать его дату
    const oldItem = editId ? (fullData.active || []).find(r => String(r.id) === String(editId)) : null;
    const m = document.getElementById('m_p_m').value || "1";
    const w = (document.getElementById('m_p_w').value || "0").replace(',', '.');
    const v = (document.getElementById('m_p_v').value || "0").replace(',', '.');
    const finalParams = `${m}м | ${w}кг | ${v}м3`;
    const from = document.getElementById('m_route_from').value || "—";
    const to = document.getElementById('m_route_to').value || "—";
    const finalRoute = `${from.toUpperCase()} ➡️ ${to.toUpperCase()}`;

    const data = {
        id: document.getElementById('m_id').value || "MEMO-" + Date.now().toString().slice(-4),
        sender: document.getElementById('m_sender').value || "ЛИЧНАЯ ЗАМЕТКА",
        recipient: "ЮЖНЫЙ ФОРПОСТ",
        route: finalRoute,
        params: finalParams,
        status: document.getElementById('m_status').value,
        priority: document.getElementById('m_priority').value,
        is_manual: true,
        // ВАЖНО: Если редактируем - оставляем старую дату, если новая - ставим сегодня
        arrival: oldItem ? oldItem.arrival : new Date().toISOString().split('T')[0]
    };

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            // Сбрасываем форму в исходное состояние
            document.getElementById('m_edit_id').value = '';
            const btn = document.getElementById('m_btn_save');
            if (btn) {
                btn.textContent = "OK";
                btn.style.backgroundColor = ""; // Возвращаем исходный цвет из CSS
                btn.style.color = "";
                btn.classList.add('btn-indigo');
            }

            // Очищаем поля ввода
            ['m_id', 'm_sender', 'm_route', 'm_params'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });

            loadReportData(); // Обновляем таблицу, чтобы увидеть изменения
        } else {
            alert("Ошибка сохранения: проверьте server.py");
        }
    } catch (error) {
        console.error("Ошибка API:", error);
    }
}

// 3. Функция УДАЛЕНИЯ
async function deleteManualCargo(id) {
    if (!confirm("Удалить эту памятку навсегда?")) return;

    try {
        const response = await fetch(`/admin/delete-manual/${id}`, {
            method: 'DELETE'
        });
        if (response.ok) loadReportData();
    } catch (err) {
        console.error("Ошибка удаления:", err);
    }
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



// --- ЗАПУСК И СЛУШАТЕЛИ ---

document.addEventListener('DOMContentLoaded', () => {
    const dF = document.getElementById('dateFilter');
    const sI = document.getElementById('searchInput');

    if (dF) dF.addEventListener('change', filterTable);
    if (sI) sI.addEventListener('keyup', filterTable);

    loadReportData();
    setInterval(loadReportData, 60000); // Обновление каждую минуту
});
