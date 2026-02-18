let currentView = 'active';
let fullData = { active: [], archive: [] };
let sortDirection = 'desc'; // По умолчанию новые сверху

function toggleSort(column) {
    // Переключаем направление
    sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';

    // Обновляем иконку для наглядности
    const icon = document.getElementById('sort-icon');
    icon.innerHTML = sortDirection === 'asc' ? '🔼' : '🔽';

    renderTable();
}

function setView(view) {
    currentView = view;
    document.getElementById('btn-active').classList.toggle('active', view === 'active');
    document.getElementById('btn-archive').classList.toggle('active', view === 'archive');
    renderTable();
}

function copyToClipboard(id, btn) {
    // 1. Ищем данные в обоих массивах
    const item = [...(fullData.active || []), ...(fullData.archive || [])].find(r => String(r.id) === String(id));
    if (!item) return;

    // 2. Формируем текст (твой шаблон + статус оплаты)
    const pRaw = (item.payment || "").toLowerCase();
    const isPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');
    const payStatus = isPaid ? "✅ Оплачено" : `⚠️ ${item.payment.toUpperCase()}`;

    const text = `${item.tk} (${item.route})\n${item.sender} (${item.id})\n${item.params}\n${payStatus}`;

    // Функция индикации успеха
    const showSuccess = () => {
        const oldInner = btn.innerHTML;
        btn.innerHTML = '✅';
        setTimeout(() => { btn.innerHTML = oldInner; }, 1500);
    };

    // 3. УНИВЕРСАЛЬНЫЙ МЕТОД (для локальной сети без HTTPS)
    try {
        const textArea = document.createElement("textarea");
        textArea.value = text;

        // Делаем поле максимально незаметным
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        textArea.style.top = "-9999px";
        document.body.appendChild(textArea);

        textArea.focus();
        textArea.select();

        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);

        if (successful) {
            showSuccess();
        } else {
            throw new Error('execCommand returned false');
        }
    } catch (err) {
        // Если старый метод не сработал, пробуем современный (для localhost/HTTPS)
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(showSuccess).catch(e => {
                console.error("Ошибка буфера:", e);
                alert("Ошибка копирования. Используйте HTTPS или обновите браузер.");
            });
        }
    }
}



function renderTable() {
    const tbody = document.getElementById('report-table-body');
    let list = [...(fullData[currentView] || [])];
    tbody.innerHTML = '';

    list.sort((a, b) => {
        const dateA = new Date(a.arrival || (a.archived_at ? a.archived_at.split('.').reverse().join('-') : 0));
        const dateB = new Date(b.arrival || (b.archived_at ? b.archived_at.split('.').reverse().join('-') : 0));
        return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
    });

    // Вспомогательная функция для сокращения имен ваших юрлиц
    const shortenMyName = (name) => {
        if (!name) return '—';
        const upperName = name.toUpperCase();
        // Добавь сюда другие свои ИНН или названия, если появятся
        if (upperName.includes("ЮЖНЫЙ ФОРПОСТ") || upperName.includes("ТАРИМАГ")) {
            return '<b style="color: #4f46e5;">МЫ</b>';
        }
        return name;
    };

    list.forEach(r => {
        const rawStatus = (r.status || '').toLowerCase();
        let displayStatus = r.status;
        let statusClass = "text-dark";

        if (rawStatus.includes('прибыл') || rawStatus.includes('готов') || rawStatus.includes('хранение')) {
            displayStatus = "✅ Прибыл в ТК";
            statusClass = "text-success";
        } else if (rawStatus.includes('пути') || rawStatus.includes('транзит') || rawStatus.includes('принят')){
            displayStatus = "🚚 В пути";
            statusClass = "text-primary";
        } else if (rawStatus.includes('оставк') || rawStatus.includes('до адреса')){
            displayStatus = "🚚 Доставка ТК ➡️ СКЛАД";
            statusClass = "text-success";
        }

        const pRaw = (r.payment || "").toLowerCase();
        const isActuallyPaid = pRaw.startsWith('оплаче') && !pRaw.includes('к ');
        let pStyle = isActuallyPaid ? "text-success fw-bold" : "badge bg-danger text-white px-2 py-1 shadow-sm";
        let pDisplay = isActuallyPaid ? "✅ Оплачено" : "⚠️ " + r.payment;

        let tkStyle = "background: #f1f5f9; color: #475569;";
        if(r.tk.includes('ПЭК')) tkStyle = "background: #fef9c3; color: #854d0e; border: 1px solid #fde047;";
        if(r.tk.includes('Деловые')) tkStyle = "background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe;";

        let payerIcon = r.payer_type === 'recipient' ? '<span class="ms-1" title="Платит получатель">⬇️</span>' :
                        r.payer_type === 'sender' ? '<span class="ms-1" title="Платит отправитель">⬆️</span>' :
                        '<span class="ms-1" title="Платит третье лицо">👤</span>';

        const rawDate = r.arrival ? r.arrival.split('T')[0] : (r.archived_at ? r.archived_at.split('.').reverse().join('-') : '0000-00-00');

        const tr = document.createElement('tr');
        tr.setAttribute('data-sender', (r.sender || "").toLowerCase());
        tr.setAttribute('data-receiver', (r.recipient || "").toLowerCase());
        if (displayStatus.includes('СКЛАД') || displayStatus.includes('ТК')) tr.classList.add('row-arrived');

                // --- ЛОГИКА ОПРЕДЕЛЕНИЯ ТЯЖЕЛОГО/ГАБАРИТНОГО ГРУЗА ---
        let heavyIcon = '';
        let oversizeIcon = '';

        // Вытаскиваем числа из строки типа "1м | 50.0кг | 0.2м3"
        const params = r.params || "";
        const weightMatch = params.match(/([\d.]+)\s*кг/);
        const volumeMatch = params.match(/([\d.]+)\s*м3/);
        const placesMatch = params.match(/(\d+)\s*м/);

        const weight = weightMatch ? parseFloat(weightMatch[1]) : 0;
        const volume = volumeMatch ? parseFloat(volumeMatch[1]) : 0;
        const places = placesMatch ? parseInt(placesMatch[1]) : 1;

        // ЛИМИТЫ (можно подстроить под минивэн)
        const MAX_WEIGHT_PER_PLACE = 50; // кг на одно место (если больше - одному тяжело)
        const MAX_TOTAL_VOLUME = 3.5;    // м3 (предел вместимости багажника)
        const MAX_TOTAL_WEIGHT = 600;    // кг (общий лимит на ход)

        // Проверка на тяжелое место (средний вес одного места)
        if (weight / places > MAX_WEIGHT_PER_PLACE || weight > MAX_TOTAL_WEIGHT) {
            heavyIcon = `<span class="heavy-badge" title="Тяжелый груз: ${weight}кг (около ${Math.round(weight/places)}кг/место)">🏋️</span>`;
        }

        // Проверка на габарит
        if (volume > MAX_TOTAL_VOLUME) {
            oversizeIcon = `<span class="oversize-badge" title="Габаритный груз: ${volume}м3 (может не влезть!)">📦⚠️</span>`;
        }

        tr.innerHTML = `
            <td data-label="ТК"><span class="badge-tk" style="${tkStyle}">${r.tk}</span></td>
            <td data-label="№ Накладной">
                <code>${r.id}</code> ${payerIcon}
                <span class="copy-btn" onclick="copyToClipboard('${r.id}', this)" title="Копировать данные">📋</span>
            </td>
            <td data-label="Отправитель">${shortenMyName(r.sender)}</td>
            <td data-label="Получатель">${shortenMyName(r.recipient)}</td>
            <td data-label="Маршрут">${r.route}</td>


            <td data-label="Груз">
                <small>${r.params}</small>
                ${heavyIcon} ${oversizeIcon}
            </td>

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


function loadReportData() {
    const btn = document.getElementById('refresh-btn');
    const statusInd = document.getElementById('api-status');
    btn.disabled = true; statusInd.classList.add('loading');

    fetch('/api/latest')
        .then(r => r.json())
        .then(data => {
            fullData = data;
            document.getElementById('update-time').textContent = data.metadata.created_at;
            document.getElementById('stat-total').textContent = data.active.length;
            document.getElementById('stat-ready').textContent = data.active.filter(r =>
                ["прибыл", "готов", "хранение"].some(w => r.status.toLowerCase().includes(w))
            ).length;
            // document.getElementById('stat-transit').textContent = data.active.filter(r =>
            //     r.status.toLowerCase().includes('пути')
            // ).length;
            document.getElementById('stat-transit').textContent = data.active.filter(r => {
                const status = r.status.toLowerCase();
                // Проверяем, есть ли в статусе хотя бы одна из этих фраз
                return ['пути', 'принят к перевозке', 'в дороге'].some(word => status.includes(word));
            }).length;
            document.getElementById('stat-debt').textContent = data.active.filter(r => {
                const paymentLower = r.payment.toLowerCase();
                const isPaid = paymentLower.startsWith('оплаче') || !paymentLower.includes('не');
                return !isPaid; // Считаем те, что НЕ оплачены
            }).length;
            renderTable();
        })
        .finally(() => {
            btn.disabled = false; statusInd.classList.remove('loading');
        });
}


const searchInput = document.getElementById('searchInput');
const clearBtn = document.getElementById('clearSearch');

// Следим за вводом текста
searchInput.addEventListener('input', function() {
    // Показываем крестик, если поле не пустое
    clearBtn.style.display = this.value.length > 0 ? 'block' : 'none';
    filterTable(); // Твоя существующая функция фильтрации
});

// Логика клика по крестику
clearBtn.addEventListener('click', function() {
    searchInput.value = '';        // Очищаем поле
    this.style.display = 'none';   // Прячем крестик
    searchInput.focus();           // Возвращаем фокус в поле
    filterTable();                 // Показываем все строки
});

function filterByStat(type, element) {
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearch');

    // Сбрасываем стили со всех карточек
    document.querySelectorAll('.stat-card').forEach(card => {
        card.classList.remove('active-filter');
        card.style.borderColor = ""; // Сброс цвета рамки
    });

    let filterValue = "";
    if (type === 'ready') filterValue = "Прибыл";
    if (type === 'transit') filterValue = "В пути";
    if (type === 'debt') filterValue = "К ОПЛАТЕ";

    searchInput.value = filterValue;

    // Если это не общий сброс, красим рамку в цвет цифр внутри плитки
    if (type !== 'total' && filterValue !== "") {
        element.classList.add('active-filter');
        // Берем цвет у элемента с цифрой (например, .stat-value)
        const valueColor = window.getComputedStyle(element.querySelector('.stat-value')).color;
        element.style.borderColor = valueColor;
    }

    if (clearBtn) clearBtn.style.display = filterValue.length > 0 ? 'block' : 'none';
    filterTable();
}




function filterTable() {
    const textFilter = document.getElementById('searchInput').value.toLowerCase();
    const dateFilter = document.getElementById('dateFilter').value;

    document.querySelectorAll('#report-table-body tr').forEach(row => {
        // 1. Берем видимый текст (ТК, номер, статус)
        const visibleText = row.textContent.toLowerCase();

        // 2. Берем ОРИГИНАЛЬНЫЕ имена из атрибутов
        const originalSender = row.getAttribute('data-sender') || "";
        const originalReceiver = row.getAttribute('data-receiver') || "";

        // 3. Совмещаем всё для поиска
        const searchPool = visibleText + " " + originalSender + " " + originalReceiver;

        const dateCell = row.querySelector('[data-date]');
        const rowDate = dateCell ? dateCell.getAttribute('data-date') : '';

        let matchesText = searchPool.includes(textFilter);
        let matchesDate = !dateFilter || rowDate.includes(dateFilter);

        row.style.display = (matchesText && matchesDate) ? '' : 'none';
    });
}


document.getElementById('dateFilter').addEventListener('change', filterTable);
document.getElementById('searchInput').addEventListener('keyup', filterTable);
loadReportData();
setInterval(loadReportData, 60000);
