/**
 * Dashboard JavaScript - Plataforma de Inteligência Operacional
 */

const API = '';

// === Global State ===
let globalTemporalData = [];
let globalYearFilter = 'Todos';
let evolucaoAnualChartInstance = null;

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

// === Temporal / Sazonalidade / Evolução Anual ===
async function fetchAndProcessTemporalData() {
    const res = await api('/api/analytics/temporal');
    if (!res || !res.data) return;

    globalTemporalData = res.data;

    // Extract unique years
    const years = [...new Set(globalTemporalData.map(d => d.ano))].sort((a, b) => a - b);

    // Build Year Filter UI
    const filtersContainer = document.getElementById('year-filters-container');
    let buttonsHtml = `<span class="text-sm" style="color: var(--text-muted); margin-right: 8px; font-size: 0.85rem;">Filtro Ano:</span>`;

    // Add "Todos" button
    buttonsHtml += `<button class="year-filter-btn ${globalYearFilter === 'Todos' ? 'active' : ''}" onclick="setYearFilter('Todos')">Todos</button>`;

    // Add Year buttons
    years.forEach(y => {
        buttonsHtml += `<button class="year-filter-btn ${globalYearFilter === y.toString() ? 'active' : ''}" onclick="setYearFilter('${y}')">${y}</button>`;
    });

    filtersContainer.innerHTML = buttonsHtml;

    // Render the Multi-year Line Chart (not affected by global filter, it shows all years for contrast)
    renderEvolucaoAnualChart(years);

    // Render the specific year charts based on current filter
    updateYearlyCharts();
}

function setYearFilter(yearStr) {
    globalYearFilter = yearStr;
    // Update active class on buttons
    document.querySelectorAll('.year-filter-btn').forEach(btn => {
        if (btn.textContent === yearStr) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    // Re-render dependent charts
    updateYearlyCharts();
}

function updateYearlyCharts() {
    // Filter data
    const filteredData = globalYearFilter === 'Todos'
        ? globalTemporalData
        : globalTemporalData.filter(d => d.ano.toString() === globalYearFilter);

    // 1. Re-render Análise Temporal (Bar Chart)
    // We group by month to sum up solicitacoes if 'Todos' is selected
    const monthMap = {};
    const monthNames = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

    filteredData.forEach(d => {
        const m = d.mes_numero;
        if (!monthMap[m]) monthMap[m] = { mes: d.mes, total_solicitacoes: 0, mes_numero: m };
        monthMap[m].total_solicitacoes += d.total_solicitacoes;
    });

    // Ensure all months are in order
    const temporalAggregated = Object.values(monthMap).sort((a, b) => a.mes_numero - b.mes_numero);
    renderBarChart('chart-temporal', temporalAggregated, 'mes', 'total_solicitacoes', 12);

    // 2. Re-render Análise Sazonal
    let verao = 0; // Dez a Mar
    let chuvas = 0; // Abr a Jul
    let secas = 0; // Ago a Nov

    filteredData.forEach(d => {
        const m = d.mes_numero;
        if (m >= 4 && m <= 7) chuvas += d.total_solicitacoes;
        else if (m >= 8 && m <= 11) secas += d.total_solicitacoes;
        else verao += d.total_solicitacoes;
    });

    const sazonalidadeData = [
        { periodo: "Período Chuvoso (Abr-Jul)", total: chuvas },
        { periodo: "Verão (Dez-Mar)", total: verao },
        { periodo: "Primavera/Seca (Ago-Nov)", total: secas }
    ].sort((a, b) => b.total - a.total);

    renderBarChart('chart-sazonalidade', sazonalidadeData, 'periodo', 'total');
}

function renderEvolucaoAnualChart(years) {
    // Prepare Chart.js dataset
    const datasets = [];

    // Paleta de cores Enterprise
    const colors = ['#94A3B8', '#38BDF8', '#3B82F6', '#2563EB', '#1E3A8A'];

    years.forEach((y, i) => {
        const yearData = globalTemporalData.filter(d => d.ano === y);
        const dataArr = new Array(12).fill(0);

        yearData.forEach(d => {
            if (d.mes_numero >= 1 && d.mes_numero <= 12) {
                dataArr[d.mes_numero - 1] = d.total_solicitacoes;
            }
        });

        const color = colors[i % colors.length];
        datasets.push({
            label: y.toString(),
            data: dataArr,
            borderColor: color,
            backgroundColor: color,
            fill: false,
            tension: 0.4, // Smooth curve
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 6
        });
    });

    const ctx = document.getElementById('chart-evolucao-anual').getContext('2d');

    if (evolucaoAnualChartInstance) {
        evolucaoAnualChartInstance.destroy();
    }

    evolucaoAnualChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8,
                        font: { family: "'Inter', sans-serif", size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleFont: { family: "'Inter', sans-serif" },
                    bodyFont: { family: "'Inter', sans-serif" },
                    padding: 10,
                    cornerRadius: 4
                }
            },
            scales: {
                x: {
                    grid: { display: false, drawBorder: false },
                    ticks: { font: { family: "'Inter', sans-serif", size: 11 }, color: '#64748B' }
                },
                y: {
                    grid: { color: '#F1F5F9', drawBorder: false },
                    ticks: { font: { family: "'Inter', sans-serif", size: 11 }, color: '#64748B' }
                }
            }
        }
    });
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

// === Heatmap Section ===
async function loadMapaCalorSetor() {
    const res = await api('/api/analytics/mapa-calor-setor');
    const container = document.getElementById('chart-heatmap-setores');

    if (!res || !res.data || res.data.length === 0) {
        container.innerHTML = '<div class="loading-state">Sem dados de concentração geográfica.</div>';
        return;
    }

    let html = '';

    res.data.forEach(setorData => {
        const sectorName = setorData.setor;
        const totalSector = setorData.total;
        const bairros = setorData.bairros;

        if (bairros.length === 0) return;

        // Find max value in this sector to scale the opacity
        const maxVal = Math.max(...bairros.map(b => b.total));

        html += `<div class="heatmap-sector">
            <div class="heatmap-sector-title">
                <span>${sectorName.substring(0, 30)}...</span>
                <span>${totalSector} Chamados</span>
            </div>
            <div class="heatmap-grid">`;

        bairros.forEach(b => {
            const val = b.total;
            // Calculate a scale from 1 to 5 for the heat
            const heatLevel = Math.max(1, Math.ceil((val / maxVal) * 5));
            // Calculate opacity based on heatLevel (0.2 to 1.0)
            const opacity = (0.3 + (heatLevel * 0.14)).toFixed(2);

            // Reusing the accent blue color with variable opacity
            const style = `background-color: rgba(59, 130, 246, ${opacity})`;

            html += `<div class="heatmap-cell" 
                        style="${style}" 
                        title="${b.bairro}: ${val} solicitações">
                        ${val}
                     </div>`;
        });

        html += `   </div>
                </div>`;
    });

    container.innerHTML = html;
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
    // Fetch Temporal Data once, rendering Year Filters, Multi-Year Chart, Sazonalidade and Temporal Chart
    await fetchAndProcessTemporalData();
    loadAnalytics();
    loadMapaCalorSetor();
}
loadAll();
