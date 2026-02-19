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

    const pRaw = (item.payment || "").toLowerCase();
    const isPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');
    const payStatus = isPaid ? "✅ Оплачено" : `⚠️ ${item.payment.toUpperCase()}`;
    const text = `${item.tk} (${item.route})\n${item.sender} (${item.id})\n${item.params}\n${payStatus}`;

    const showSuccess = () => {
        const oldInner = btn.innerHTML;
        btn.innerHTML = '✅';
        setTimeout(() => { btn.innerHTML = oldInner; }, 1500);
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
    } catch (e) {}

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

    // 1. Сортировка по дате (используем глобальный sortDirection)
    list.sort((a, b) => {
        const dateA = new Date(a.arrival || (a.archived_at ? a.archived_at.split('.').reverse().join('-') : '2099-12-31'));
        const dateB = new Date(b.arrival || (b.archived_at ? b.archived_at.split('.').reverse().join('-') : '2099-12-31'));
        return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
    });

    const shortenMyName = (name) => {
        if (!name) return '—';
        const upper = name.toUpperCase();
        if (upper.includes("ЮЖНЫЙ ФОРПОСТ") || upper.includes("ТАРИМАГ")) {
            return '<b style="color: #4f46e5;">МЫ</b>';
        }
        return name;
    };

    list.forEach(r => {
        const tr = document.createElement('tr');
        const rawStatus = (r.status || '').toLowerCase();
        let displayStatus = r.status;
        let statusClass = "text-dark";

        // --- ЛОГИКА ПАМЯТОК И УДАЛЕНИЯ ---
        let priorityIcon = "";
        let deleteBtn = "";
        if (r.is_manual) {
            tr.classList.add('memo-row');
            // Кнопка удаления (только если на странице есть форма админа)
            if (document.getElementById('m_id')) {
                deleteBtn = `<span class="ms-2" onclick="deleteManualCargo('${r.id}')" style="cursor:pointer; opacity:0.6;" title="Удалить памятку">🗑️</span>`;
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
        let pStyle = isActuallyPaid ? "text-success fw-bold" : "badge bg-danger text-white px-2 py-1 shadow-sm";
        let pDisplay = isActuallyPaid ? "✅ Оплачено" : "⚠️ " + r.payment;

        let tkStyle = "background: #f1f5f9; color: #475569;";
        if(r.tk.includes('ПЭК')) tkStyle = "background: #fef9c3; color: #854d0e; border: 1px solid #fde047;";
        if(r.tk.includes('Деловые')) tkStyle = "background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe;";

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

        if (weight / places > 35 || weight > 150) {
            heavyIcon = `<span class="heavy-badge" title="Тяжелый: ${weight}кг">🏋️</span>`;
        }
        if (volume > 1.5) {
            oversizeIcon = `<span class="oversize-badge" title="Габаритный: ${volume}м3">📦⚠️</span>`;
        }

        const rawDate = r.arrival ? r.arrival.split('T')[0] : (r.archived_at ? r.archived_at.split('.').reverse().join('-') : '0000-00-00');
        tr.setAttribute('data-sender', (r.sender || "").toLowerCase());
        tr.setAttribute('data-receiver', (r.recipient || "").toLowerCase());

        tr.innerHTML = `
            <td data-label="ТК"><span class="badge-tk" style="${tkStyle}">${r.tk}</span></td>
            <td data-label="№ Накладной">
                <code>${r.id}</code> ${priorityIcon}${payerIcon}${deleteBtn}
                <span class="copy-btn" onclick="copyToClipboard('${r.id}', this)" title="Копировать">📋</span>
            </td>
            <td data-label="Отправитель">${shortenMyName(r.sender)}</td>
            <td data-label="Получатель">${shortenMyName(r.recipient)}</td>
            <td data-label="Маршрут">${r.route}</td>
            <td data-label="Груз"><small>${r.params}</small> ${heavyIcon}${oversizeIcon}</td>
            <td data-label="Статус" class="fw-bold ${statusClass}">${displayStatus}</td>
            <td data-label="Прибытие" data-date="${rawDate}">
                <strong>${r.arrival ? r.arrival.split('T')[0] : (r.archived_at || '—')}</strong>
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
    const dateFilter = document.getElementById('dateFilter');
    if (!searchInput) return;

    const textFilter = searchInput.value.toLowerCase();
    const dFilter = dateFilter ? dateFilter.value : "";

    document.querySelectorAll('#report-table-body tr').forEach(row => {
        // Умный поиск: текст строки + скрытые оригинальные имена
        const searchPool = row.textContent.toLowerCase() + " " +
                           (row.getAttribute('data-sender') || "") + " " +
                           (row.getAttribute('data-receiver') || "");

        const dateCell = row.querySelector('[data-date]');
        const rowDate = dateCell ? dateCell.getAttribute('data-date') : '';

        const matchesText = searchPool.includes(textFilter);
        const matchesDate = !dFilter || rowDate.includes(dFilter);

        row.style.display = (matchesText && matchesDate) ? '' : 'none';
    });
}

// --- АДМИН-ФУНКЦИИ (Работают только в DEV режиме) ---

async function saveManualCargo() {
    const mId = document.getElementById('m_id');
    if (!mId) return; // Защита: если нет формы, функция не работает

    const data = {
        id: mId.value || "MEMO-" + Date.now().toString().slice(-4),
        sender: document.getElementById('m_sender').value || "ЛИЧНАЯ ЗАМЕТКА",
        recipient: "ЮЖНЫЙ ФОРПОСТ",
        route: document.getElementById('m_route').value || "Н/Д",
        priority: document.getElementById('m_priority').value,
        status: document.getElementById('m_status').value || "Ожидает обработки",
        params: "Ручной ввод 📝",
        arrival: new Date().toISOString().split('T')[0],
        payment: "Не требуется",
        payer_type: "recipient"
    };

    try {
        const response = await fetch('/admin/add-manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            // Очистка формы
            ['m_id', 'm_sender', 'm_route', 'm_status'].forEach(id => {
                document.getElementById(id).value = '';
            });
            loadReportData();
        }
    } catch (error) {
        console.error("Ошибка сохранения памятки:", error);
    }
}

async function deleteManualCargo(id) {
    if (!confirm("Удалить эту памятку?")) return;

    try {
        const response = await fetch(`/admin/delete-manual/${id}`, {
            method: 'DELETE'
        });
        if (response.ok) loadReportData();
    } catch (err) {
        console.error("Ошибка удаления:", err);
    }
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
