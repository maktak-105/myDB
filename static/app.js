const API_BASE = window.location.origin;

// Session and History management
let sessionId = localStorage.getItem('chat_session_id') || Math.random().toString(36).substring(7);
localStorage.setItem('chat_session_id', sessionId);

let messageHistory = JSON.parse(localStorage.getItem('chat_history') || '[]');

// Configure marked
marked.setOptions({
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true
});

let currentTents = [];
let sortConfig = { key: 'id', direction: 'asc' }; // default sort

async function fetchTents() {
    const res = await fetch(`${API_BASE}/tents`);
    const data = await res.json();
    currentTents = data;
    applySort(); // Initial sort
}

async function fetchStats() {
    const res = await fetch(`${API_BASE}/tents/stats`);
    const data = await res.json();
    const statsHeader = document.getElementById('stats-header');
    statsHeader.innerHTML = `
        <span style="margin: 0 10px;">Total: <strong>${data.total_count}</strong></span>
        <span>Avg Price: <strong>${data.avg_price}</strong></span>
    `;
}

function handleSort(key) {
    if (sortConfig.key === key) {
        sortConfig.direction = sortConfig.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortConfig.key = key;
        sortConfig.direction = 'asc';
    }
    applySort();
}

function applySort() {
    const sorted = [...currentTents].sort((a, b) => {
        let valA = a[sortConfig.key];
        let valB = b[sortConfig.key];

        // Ensure numeric comparison for specific keys
        const numericKeys = ['id', 'price', 'capacity', 'weight_kg', 'size_w', 'size_d', 'size_h', 'pack_w', 'pack_d', 'pack_h'];
        if (numericKeys.includes(sortConfig.key)) {
            valA = parseFloat(valA) || 0;
            valB = parseFloat(valB) || 0;
            return sortConfig.direction === 'asc' ? valA - valB : valB - valA;
        }

        // String comparison for others
        if (valA === null || valA === undefined) valA = '';
        if (valB === null || valB === undefined) valB = '';
        valA = String(valA);
        valB = String(valB);

        if (valA < valB) return sortConfig.direction === 'asc' ? -1 : 1;
        if (valA > valB) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
    });
    renderTable(sorted);
}

function renderTable(tents) {
    // Update header icons for all 14 columns
    const headers = {
        'id': 'col-id', 'name': 'col-name', 'brand': 'col-brand', 
        'price': 'col-price', 'capacity': 'col-capacity', 
        'weight_kg': 'col-weight_kg', 'size_w': 'col-size_w',
        'size_d': 'col-size_d', 'size_h': 'col-size_h',
        'pack_w': 'col-pack_w', 'pack_d': 'col-pack_d',
        'pack_h': 'col-pack_h', 'material': 'col-material', 
        'purchase_date': 'col-purchase_date'
    };
    
    Object.keys(headers).forEach(key => {
        const th = document.getElementById(headers[key]);
        if (!th) return;
        const baseName = th.getAttribute('data-base-name') || th.innerText.replace(/[▲▼]/g, '').trim();
        th.setAttribute('data-base-name', baseName);
        if (sortConfig.key === key) {
            th.innerHTML = `${baseName} ${sortConfig.direction === 'asc' ? '▲' : '▼'}`;
            th.style.color = 'var(--primary-color)';
        } else {
            th.innerHTML = baseName;
            th.style.color = 'inherit';
        }
    });

    const tbody = document.querySelector('#data-table tbody');
    tbody.innerHTML = '';
    
    // Debug to confirm total count and presence of ID 1
    console.log(`Rendering ${tents.length} tents. First ID: ${tents.length > 0 ? tents[0].id : 'none'}`);
    
    tents.forEach(tent => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${tent.id}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'name', this.innerText)">${tent.name}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'brand', this.innerText)">${tent.brand || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'price', this.innerText)">${(tent.price || 0).toLocaleString()}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'capacity', this.innerText)">${tent.capacity || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'weight_kg', this.innerText)">${tent.weight_kg || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'size_w', this.innerText)">${tent.size_w || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'size_d', this.innerText)">${tent.size_d || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'size_h', this.innerText)">${tent.size_h || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'pack_w', this.innerText)">${tent.pack_w || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'pack_d', this.innerText)">${tent.pack_d || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'pack_h', this.innerText)">${tent.pack_h || ''}</td>
            <td contenteditable="true" class="editable" onblur="updateField(${tent.id}, 'material', this.innerText)">${tent.material || ''}</td>
            <td>${tent.purchase_date || '-'}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function updateField(id, field, value) {
    // Strip commas for numeric fields before sending to API
    const cleanValue = value.toString().replace(/,/g, '');
    const payload = {};
    const numericFields = ['price', 'capacity', 'weight_kg', 'size_w', 'size_d', 'size_h', 'pack_w', 'pack_d', 'pack_h'];
    
    if (numericFields.includes(field)) {
        payload[field] = parseFloat(cleanValue) || 0;
    } else {
        payload[field] = value;
    }

    const res = await fetch(`${API_BASE}/tents/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        console.log(`Updated tent ${id} field ${field}`);
        fetchStats();
    } else {
        alert('Failed to update field');
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('send-btn');
    const msg = input.value.trim();
    if (!msg) return;

    appendMessage('user', msg);
    input.value = '';
    
    // UI state
    btn.disabled = true;
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing';
    typingDiv.style.display = 'block';
    typingDiv.innerText = 'AIが考え中...';
    document.getElementById('chat-messages').appendChild(typingDiv);
    document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;

    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: msg,
                session_id: sessionId
            })
        });
        const data = await res.json();
        
        // Remove typing indicator
        typingDiv.remove();
        
        appendMessage('ai', data.response);
        
        // Refresh data after AI action
        fetchTents();
        fetchStats();
    } catch (e) {
        typingDiv.remove();
        appendMessage('ai', 'エラーが発生しました。再度お試しください。');
    } finally {
        btn.disabled = false;
    }
}

function appendMessage(sender, text) {
    const container = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}-message`;
    
    if (sender === 'ai') {
        // Look for chart data block: ```chart ... ```
        const chartRegex = /```chart\s+([\s\S]*?)```/g;
        let processedText = text;
        const chartsToRender = [];

        processedText = text.replace(chartRegex, (match, jsonStr) => {
            const chartId = `chart-${Math.random().toString(36).substring(7)}`;
            chartsToRender.push({ id: chartId, json: jsonStr.trim() });
            return `<div class="chart-wrapper"><canvas id="${chartId}"></canvas></div>`;
        });

        msgDiv.innerHTML = marked.parse(processedText);
        container.appendChild(msgDiv);

        // Render charts after adding to DOM
        chartsToRender.forEach(chartObj => {
            try {
                const config = JSON.parse(chartObj.json);
                const ctx = document.getElementById(chartObj.id).getContext('2d');
                new Chart(ctx, config);
            } catch (e) {
                console.error('Failed to render chart:', e);
                document.getElementById(chartObj.id).parentElement.innerText = 'グラフの描画に失敗しました。';
            }
        });
    } else {
        msgDiv.innerText = text;
        container.appendChild(msgDiv);
    }
    
    container.scrollTop = container.scrollHeight;

    // Save to history
    messageHistory.push({ sender, text });
    localStorage.setItem('chat_history', JSON.stringify(messageHistory));
}

function loadHistory() {
    const container = document.getElementById('chat-messages');
    // Clear initial message if we have history
    if (messageHistory.length > 0) {
        container.innerHTML = '';
        messageHistory.forEach(msg => {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${msg.sender}-message`;
            if (msg.sender === 'ai') {
                msgDiv.innerHTML = marked.parse(msg.text);
            } else {
                msgDiv.innerText = msg.text;
            }
            container.appendChild(msgDiv);
        });
        container.scrollTop = container.scrollHeight;
    }
}

document.getElementById('send-btn').addEventListener('click', sendMessage);
document.getElementById('chat-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Initial load
fetchTents();
fetchStats();
loadHistory();
