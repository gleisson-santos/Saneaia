/**
 * Dashboard JavaScript - Plataforma de Inteligência Operacional
 */

const API = '';

// === Navigation ===
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
        e.preventDefault();
        const section = item.dataset.section;
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
        document.getElementById('section-' + section).classList.add('active');
        document.getElementById('page-title').textContent = item.querySelector('.nav-label').textContent;
        if (section === 'analytics') loadAnalytics();
        if (section === 'ml') loadMLMetrics();
    });
});

// Mobile toggle
document.getElementById('menu-toggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
});

// Clock
function updateClock() {
    const now = new Date();
    document.getElementById('topbar-time').textContent = now.toLocaleString('pt-BR');
}
setInterval(updateClock, 1000);
updateClock();

// === API Helpers ===
async function api(path, opts = {}) {
    try {
        const res = await fetch(API + path, {
            headers: { 'Content-Type': 'application/json' },
            ...opts
        });
        return await res.json();
    } catch (e) {
        console.error('API Error:', path, e);
        return null;
    }
}

// === Health Check ===
async function checkHealth() {
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    const data = await api('/health');
    if (data && data.status === 'healthy') {
        dot.className = 'status-dot online';
        txt.textContent = 'Sistema Online';
    } else {
        dot.className = 'status-dot offline';
        txt.textContent = 'Sistema Offline';
    }
}

// === KPIs ===
async function loadKPIs() {
    const res = await api('/api/analytics/kpis');
    if (!res || !res.data) return;
    const d = res.data;
    animateValue('kpi-total', d.total_solicitacoes || 0);
    animateValue('kpi-resolved', d.total_resolvidas || 0);
    animateValue('kpi-open', d.total_abertas || 0);
    document.getElementById('kpi-time').textContent = d.tempo_medio_resolucao_horas != null ? d.tempo_medio_resolucao_horas.toFixed(1) : '--';
    animateValue('kpi-neighborhoods', d.total_bairros || 0);
    animateValue('kpi-clients', d.total_clientes || 0);
}

function animateValue(id, end) {
    const el = document.getElementById(id);
    const dur = 800;
    const start = 0;
    const startTime = performance.now();
    function tick(now) {
        const p = Math.min((now - startTime) / dur, 1);
        el.textContent = Math.floor(p * end).toLocaleString('pt-BR');
        if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

// === Bar Charts ===
function renderBarChart(containerId, data, labelKey, valueKey, maxItems = 10) {
    const container = document.getElementById(containerId);
    if (!data || !data.length) { container.innerHTML = '<div class="loading-state">Sem dados</div>'; return; }
    const items = data.slice(0, maxItems);
    const maxVal = Math.max(...items.map(d => d[valueKey] || 0));
    let html = '<div class="bar-chart">';
    items.forEach(d => {
        const pct = maxVal > 0 ? ((d[valueKey] || 0) / maxVal * 100) : 0;
        const label = (d[labelKey] || '').substring(0, 25);
        html += `<div class="bar-item">
            <span class="bar-label" title="${d[labelKey]}">${label}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${pct}%">
                <span class="bar-value">${(d[valueKey] || 0).toLocaleString('pt-BR')}</span>
            </div></div></div>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

// === Load Dashboard Charts ===
async function loadBairros() {
    const res = await api('/api/analytics/por-bairro?limit=10');
    if (res) renderBarChart('chart-bairros', res.data, 'bairro', 'total_solicitacoes');
}

async function loadTemporal() {
    const res = await api('/api/analytics/temporal');
    if (res) renderBarChart('chart-temporal', res.data, 'mes', 'total_solicitacoes');
}

// === Solicitações Table ===
async function loadSolicitacoes() {
    const res = await api('/api/solicitacoes?limit=20');
    if (!res || !res.data) return;
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = res.data.map(d => {
        const sit = d.situacao || 'Desconhecida';
        let badge = 'badge-info';
        if (sit.toLowerCase().includes('conclu')) badge = 'badge-success';
        else if (sit.toLowerCase().includes('aberta')) badge = 'badge-danger';
        const enc = d.data_encerramento ? new Date(d.data_encerramento).toLocaleDateString('pt-BR') : '--';
        return `<tr>
            <td>${d.ss || ''}</td>
            <td>${(d.tipo || '').substring(0, 35)}</td>
            <td>${(d.bairro || '').substring(0, 25)}</td>
            <td><span class="badge ${badge}">${sit.substring(0, 20)}</span></td>
            <td>${enc}</td></tr>`;
    }).join('');
}

// === Analytics Section ===
async function loadAnalytics() {
    const [tipos, setores, reinc] = await Promise.all([
        api('/api/analytics/por-tipo'),
        api('/api/analytics/por-setor'),
        api('/api/analytics/reincidencia?min_solicitacoes=3')
    ]);
    if (tipos) renderBarChart('chart-tipos', tipos.data, 'tipo', 'total');
    if (setores) renderBarChart('chart-setores', setores.data, 'setor', 'total');
    if (reinc && reinc.data) {
        let html = '<table class="data-table"><thead><tr><th>Matrícula</th><th>Solicitações</th><th>Bairros</th></tr></thead><tbody>';
        reinc.data.slice(0, 15).forEach(d => {
            html += `<tr><td>${d.matricula}</td><td>${d.total_chamados || 0}</td><td>${d.bairro || '--'}</td></tr>`;
        });
        html += '</tbody></table>';
        document.getElementById('table-reincidencia').innerHTML = html;
    }
}

// === Chat ===
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');

function addMessage(text, isUser = false) {
    const div = document.createElement('div');
    div.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

    // Check if marked.js is loaded, otherwise fallback to simple replace
    const parsedText = (typeof marked !== 'undefined' && !isUser)
        ? marked.parse(text)
        : text.replace(/\n/g, '<br>');

    div.innerHTML = `<div class="message-avatar">${isUser ? '<i data-lucide="user"></i>' : '<i data-lucide="bot"></i>'}</div>
        <div class="message-content">${parsedText}</div>`;
    chatMessages.appendChild(div);
    if (typeof lucide !== 'undefined') lucide.createIcons();
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addTyping() {
    const div = document.createElement('div');
    div.className = 'message bot-message';
    div.id = 'typing-msg';
    div.innerHTML = '<div class="message-avatar"><i data-lucide="bot"></i></div><div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
    chatMessages.appendChild(div);
    if (typeof lucide !== 'undefined') lucide.createIcons();
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTyping() {
    const t = document.getElementById('typing-msg');
    if (t) t.remove();
}

async function sendChat() {
    const q = chatInput.value.trim();
    if (!q) return;
    addMessage(q, true);
    chatInput.value = '';
    addTyping();
    const res = await api('/api/agent/chat', {
        method: 'POST',
        body: JSON.stringify({ query: q })
    });
    removeTyping();
    addMessage(res && res.response ? res.response : 'Erro ao obter resposta do agente.');
}

document.getElementById('btn-send').addEventListener('click', sendChat);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

// === Insights ===
document.getElementById('btn-generate-insights').addEventListener('click', async () => {
    const grid = document.getElementById('insights-grid');
    grid.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><br>Analisando dados com IA... Isso pode levar alguns segundos.</div>';
    const res = await api('/api/agent/analyze', { method: 'POST' });
    if (res && res.insights) {
        grid.innerHTML = `<div class="insight-card">${res.insights.replace(/\n/g, '<br>')}</div>`;
    } else {
        grid.innerHTML = '<div class="loading-state">Erro ao gerar insights.</div>';
    }
});

// === NLP ===
document.getElementById('btn-nlp-analysis').addEventListener('click', async () => {
    const container = document.getElementById('nlp-results');
    container.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><br>Analisando observações...</div>';
    const res = await api('/api/agent/nlp-summary');
    if (res && res.data) {
        const d = res.data;
        container.innerHTML = `
            <div class="nlp-card"><div class="nlp-value">${d.total_analisadas || 0}</div><div class="nlp-label">Analisadas</div></div>
            <div class="nlp-card"><div class="nlp-value">${d.percentual_negativo || 0}%</div><div class="nlp-label">Sentimento Negativo</div></div>
            <div class="nlp-card"><div class="nlp-value">${d.taxa_urgencia || 0}%</div><div class="nlp-label">Taxa Urgência</div></div>
            <div class="nlp-card"><div class="nlp-value">${d.total_urgentes || 0}</div><div class="nlp-label">Urgentes</div></div>
            <div class="nlp-card"><div class="nlp-value">${Object.keys(d.topicos_frequentes || {}).length}</div><div class="nlp-label">Tópicos Detectados</div></div>
            <div class="nlp-card"><div class="nlp-value">${d.percentual_positivo || 0}%</div><div class="nlp-label">Sentimento Positivo</div></div>`;
    }
});

// === ML ===
async function loadMLMetrics() {
    const res = await api('/api/ml/model-metrics');
    const container = document.getElementById('ml-status');
    if (res && res.data && res.data.length) {
        const m = res.data[0];
        container.innerHTML = `
            <div class="metric-row"><span class="metric-label">Versão</span><span class="metric-value">${m.modelo_versao}</span></div>
            <div class="metric-row"><span class="metric-label">Accuracy</span><span class="metric-value">${(m.accuracy * 100).toFixed(1)}%</span></div>
            <div class="metric-row"><span class="metric-label">F1 Score</span><span class="metric-value">${(m.f1_score * 100).toFixed(1)}%</span></div>
            <div class="metric-row"><span class="metric-label">Precision</span><span class="metric-value">${(m.precision_score * 100).toFixed(1)}%</span></div>
            <div class="metric-row"><span class="metric-label">Recall</span><span class="metric-value">${(m.recall_score * 100).toFixed(1)}%</span></div>
            <div class="metric-row"><span class="metric-label">Amostras</span><span class="metric-value">${m.total_samples}</span></div>`;
    } else {
        container.innerHTML = '<div class="loading-state">Nenhum modelo treinado ainda.</div>';
    }
}

document.getElementById('btn-predict').addEventListener('click', async () => {
    const el = document.getElementById('ml-result');
    el.textContent = '🔮 Executando predições...';
    const res = await api('/api/ml/predict', { method: 'POST' });
    el.textContent = res ? `✅ ${res.total_predicted || 0} predições realizadas, ${res.total_saved || 0} salvas.` : '❌ Erro nas predições.';
});

document.getElementById('btn-retrain').addEventListener('click', async () => {
    const el = document.getElementById('ml-result');
    el.textContent = '⚙️ Re-treinando modelo... Aguarde.';
    const res = await api('/api/ml/retrain', { method: 'POST', body: JSON.stringify({ version: 'v1.0', model_type: 'random_forest' }) });
    if (res && res.metrics) {
        el.textContent = `✅ Modelo re-treinado!\nAccuracy: ${(res.metrics.accuracy * 100).toFixed(1)}%\nF1: ${(res.metrics.f1_score * 100).toFixed(1)}%`;
        loadMLMetrics();
    } else {
        el.textContent = '❌ Erro no re-treinamento.';
    }
});

// Refresh
document.getElementById('btn-refresh').addEventListener('click', () => loadAll());

// === Init ===
async function loadAll() {
    await checkHealth();
    loadKPIs();
    loadBairros();
    loadTemporal();
    loadSolicitacoes();
}
loadAll();
