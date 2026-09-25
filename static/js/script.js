/**
 * ============================================================
 * Nexus Core — Main JavaScript
 * Predictive Maintenance Digital Twin
 * Theme-aware · Auto-refresh · Charts
 * ============================================================
 */

const CONFIG = {
    refreshInterval: 5000,
    apiBase: '/api'
};

/* ============================================================
   THEME HELPERS
   ============================================================ */

function getThemeColors() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    if (isDark) {
        return {
            text: 'rgba(255, 255, 255, 0.6)',
            textStrong: '#ffffff',
            textMuted: 'rgba(255, 255, 255, 0.35)',
            grid: 'rgba(255, 255, 255, 0.06)',
            border: 'rgba(255, 255, 255, 0.08)',
            tooltipBg: 'rgba(15, 21, 36, 0.96)',
            tooltipBorder: 'rgba(255, 255, 255, 0.1)',
            tooltipText: '#f9fafb',
            tooltipBody: '#94a3b8',
            cpu: '#a78bfa',
            cpuFill: 'rgba(167, 139, 250, 0.15)',
            ram: '#34d399',
            ramFill: 'rgba(52, 211, 153, 0.15)',
            disk: '#fbbf24',
            diskFill: 'rgba(251, 191, 36, 0.15)'
        };
    } else {
        return {
            text: 'rgba(15, 23, 42, 0.6)',
            textStrong: '#0f172a',
            textMuted: 'rgba(15, 23, 42, 0.4)',
            grid: 'rgba(15, 23, 42, 0.08)',
            border: 'rgba(15, 23, 42, 0.1)',
            tooltipBg: 'rgba(255, 255, 255, 0.98)',
            tooltipBorder: 'rgba(15, 23, 42, 0.1)',
            tooltipText: '#0f172a',
            tooltipBody: '#475467',
            cpu: '#7c3aed',
            cpuFill: 'rgba(124, 58, 237, 0.12)',
            ram: '#059669',
            ramFill: 'rgba(5, 150, 105, 0.12)',
            disk: '#d97706',
            diskFill: 'rgba(217, 119, 6, 0.12)'
        };
    }
}

/* ============================================================
   DASHBOARD FUNCTIONS
   ============================================================ */

function loadDashboard() {
    $.ajax({
        url: CONFIG.apiBase + '/computers',
        method: 'GET',
        dataType: 'json',
        success: function (response) {
            if (response && response.success) {
                updateStats(response.computers || []);
                renderComputers(response.computers || []);
                updateLastUpdate();
            }
        },
        error: function () {
            console.error('Error loading dashboard');
        }
    });
}

function updateStats(computers) {
    var total = computers.length;
    var online = 0, warning = 0, critical = 0, offline = 0;

    computers.forEach(function (comp) {
        var s = String(comp.status || 'offline').toLowerCase();
        switch (s) {
            case 'online': online++; break;
            case 'warning': warning++; break;
            case 'critical': critical++; break;
            case 'offline': offline++; break;
            default: offline++;
        }
    });

    // Only update elements that exist
    if ($('#total-computers').length) $('#total-computers').text(total);
    if ($('#online-computers').length) $('#online-computers').text(online);
    if ($('#warning-computers').length) $('#warning-computers').text(warning);
    if ($('#critical-computers').length) $('#critical-computers').text(critical);
    if ($('#offline-computers').length) $('#offline-computers').text(offline);

    // Additional dashboard KPIs (new dashboard compatibility)
    if ($('#alert-count').length) $('#alert-count').text(warning + critical);
    if ($('#systems-count').length) $('#systems-count').text(total);
}

function renderComputers(computers) {
    var grid = $('#computers-grid');
    if (!grid.length) return; // no grid on this page

    grid.empty();

    if (computers.length === 0) {
        grid.html(
            '<div class="col-12 text-center py-5">' +
                '<i class="fas fa-desktop fa-3x text-muted mb-3"></i>' +
                '<h5 class="text-muted">No computers registered yet</h5>' +
                '<p class="text-muted small">Run the Nexus Core agent to start monitoring.</p>' +
            '</div>'
        );
        return;
    }

    computers.forEach(function (comp) {
        var statusClass = (comp.status || 'offline').toLowerCase();
        var statusIcon = getStatusIcon(statusClass);

        var card =
            '<div class="col-xl-3 col-lg-4 col-md-6 col-sm-12 mb-4">' +
                '<div class="card computer-card status-' + statusClass + ' h-100">' +
                    '<div class="card-body">' +
                        '<div class="d-flex justify-content-between align-items-start">' +
                            '<h5 class="card-title mb-2">' +
                                '<i class="fas fa-desktop me-2"></i>' +
                                escapeHtml(comp.computer_name || 'Unknown') +
                            '</h5>' +
                            '<span class="status-badge ' + statusClass + '">' +
                                '<i class="fas ' + statusIcon + ' me-1"></i>' +
                                statusClass.charAt(0).toUpperCase() + statusClass.slice(1) +
                            '</span>' +
                        '</div>' +
                        '<div class="mt-3">' +
                            renderMetricBar('CPU', comp.cpu_usage, 'cpu') +
                            renderMetricBar('RAM', comp.ram_usage, 'ram') +
                            renderMetricBar('Disk', comp.disk_usage, 'disk') +
                            '<div class="mt-3 d-flex justify-content-between align-items-center">' +
                                '<small class="text-muted">' +
                                    '<i class="far fa-clock me-1"></i>' +
                                    formatTimestamp(comp.last_update) +
                                '</small>' +
                                '<a href="/computer/' + comp.id + '" class="btn btn-sm btn-outline-primary">' +
                                    '<i class="fas fa-chart-line me-1"></i>Details' +
                                '</a>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>';

        grid.append(card);
    });
}

function renderMetricBar(label, value, type) {
    var v = Number(value || 0);
    var vSafe = Math.max(0, Math.min(100, v));
    var color = getProgressColor(v, type);

    return (
        '<div class="mb-2">' +
            '<div class="d-flex justify-content-between">' +
                '<span class="metric-label">' + label + '</span>' +
                '<span class="metric-value">' + v.toFixed(1) + '%</span>' +
            '</div>' +
            '<div class="progress">' +
                '<div class="progress-bar bg-' + color + '" role="progressbar" style="width: ' + vSafe + '%"></div>' +
            '</div>' +
        '</div>'
    );
}

function updateLastUpdate() {
    if (!$('#last-update').length) return;
    var now = new Date();
    var time = String(now.getHours()).padStart(2, '0') + ':' +
               String(now.getMinutes()).padStart(2, '0') + ':' +
               String(now.getSeconds()).padStart(2, '0');
    $('#last-update').html('<i class="far fa-clock me-1"></i>Updated: ' + time);
}

/* ============================================================
   COMPUTER DETAILS
   ============================================================ */

function loadComputerDetails(computerId) {
    $.ajax({
        url: CONFIG.apiBase + '/computer/' + computerId,
        method: 'GET',
        dataType: 'json',
        success: function (response) {
            if (response && response.success) {
                updateComputerDetails(response.computer);
                updatePredictions(response.predictions);
                updateHistoryTable(response.history);
                updateCharts(response.history);
            }
        },
        error: function () {
            console.error('Error loading computer details');
        }
    });
}

function updateComputerDetails(computer) {
    if (!computer) return;

    setText('#detail-computer-name', computer.computer_name);
    setText('#detail-ip', computer.ip_address);
    setText('#detail-os', computer.operating_system || 'Unknown');
    setText('#detail-uptime', computer.uptime || '0 minutes');
    setText('#detail-last-update', formatTimestamp(computer.last_update));
    setText('#detail-cpu', (computer.cpu_usage || 0) + '%');
    setText('#detail-ram', (computer.ram_usage || 0) + '%');
    setText('#detail-disk', (computer.disk_usage || 0) + '%');

    var status = (computer.status || 'offline').toLowerCase();
    var statusColor = getStatusColor(status);

    setText('#detail-status', status);
    if ($('#detail-status').length) {
        $('#detail-status').attr('class', 'badge bg-' + statusColor);
    }
}

function setText(selector, value) {
    if ($(selector).length) {
        $(selector).text(value);
    }
}

function updatePredictions(predictions) {
    var container = $('#predictions-list');
    if (!container.length) return;

    container.empty();

    if (!predictions || predictions.length === 0) {
        container.html(
            '<div class="text-center text-success py-3">' +
                '<i class="fas fa-check-circle fa-2x mb-2"></i>' +
                '<p class="mb-0">All systems normal</p>' +
            '</div>'
        );
        return;
    }

    predictions.forEach(function (pred) {
        var text = String(pred);
        var alertClass = 'info';
        var icon = 'info-circle';

        if (text.indexOf('Critical') !== -1 || text.indexOf('High') !== -1 || text.indexOf('Full') !== -1) {
            alertClass = 'danger';
            icon = 'exclamation-circle';
        } else if (text.indexOf('Warning') !== -1) {
            alertClass = 'warning';
            icon = 'exclamation-triangle';
        }

        container.append(
            '<div class="prediction-item ' + alertClass + '">' +
                '<i class="fas fa-' + icon + ' me-2"></i>' +
                escapeHtml(text) +
            '</div>'
        );
    });
}

function updateHistoryTable(history) {
    var tbody = $('#history-body');
    if (!tbody.length) return;

    tbody.empty();

    if (!history || history.length === 0) {
        tbody.html(
            '<tr>' +
                '<td colspan="5" class="text-center text-muted">' +
                    '<i class="fas fa-inbox me-2"></i>No history data available' +
                '</td>' +
            '</tr>'
        );
        return;
    }

    var reversed = history.slice().reverse();
    reversed.slice(0, 100).forEach(function (record, index) {
        tbody.append(
            '<tr>' +
                '<td>' + (index + 1) + '</td>' +
                '<td>' + (Number(record.cpu) || 0).toFixed(1) + '</td>' +
                '<td>' + (Number(record.ram) || 0).toFixed(1) + '</td>' +
                '<td>' + (Number(record.disk) || 0).toFixed(1) + '</td>' +
                '<td>' + escapeHtml(formatTimestamp(record.timestamp)) + '</td>' +
            '</tr>'
        );
    });
}

/* ============================================================
   CHARTS (Theme-Aware)
   ============================================================ */

var cpuChart = null, ramChart = null, diskChart = null;

function updateCharts(history) {
    if (!history || history.length === 0) {
        createEmptyCharts();
        return;
    }

    var labels = history.map(function (h) { return formatTime(h.timestamp); });
    var cpuData = history.map(function (h) { return Number(h.cpu) || 0; });
    var ramData = history.map(function (h) { return Number(h.ram) || 0; });
    var diskData = history.map(function (h) { return Number(h.disk) || 0; });

    createChart('cpuChart', 'CPU Usage %', labels, cpuData, 'cpu');
    createChart('ramChart', 'RAM Usage %', labels, ramData, 'ram');
    createChart('diskChart', 'Disk Usage %', labels, diskData, 'disk');
}

function createChart(canvasId, label, labels, data, typeKey) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return;

    var colors = getThemeColors();
    var color = colors[typeKey];
    var fillColor = colors[typeKey + 'Fill'];

    // Destroy existing
    if (canvasId === 'cpuChart' && cpuChart) { cpuChart.destroy(); cpuChart = null; }
    if (canvasId === 'ramChart' && ramChart) { ramChart.destroy(); ramChart = null; }
    if (canvasId === 'diskChart' && diskChart) { diskChart.destroy(); diskChart = null; }

    var newChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                borderColor: color,
                backgroundColor: fillColor,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 4,
                pointBackgroundColor: color,
                pointBorderColor: color
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: colors.tooltipBg,
                    borderColor: colors.tooltipBorder,
                    borderWidth: 1,
                    titleColor: colors.tooltipText,
                    bodyColor: colors.tooltipBody,
                    titleFont: { size: 11, weight: '600' },
                    bodyFont: { size: 11 },
                    padding: 10,
                    cornerRadius: 6,
                    displayColors: false,
                    callbacks: {
                        label: function (ctx) {
                            return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(1) + '%';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: colors.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: colors.text,
                        font: { size: 10 },
                        stepSize: 25,
                        callback: function (v) { return v + '%'; }
                    },
                    border: { display: false }
                },
                x: {
                    grid: {
                        color: colors.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: colors.textMuted,
                        font: { size: 9 },
                        maxTicksLimit: 8,
                        maxRotation: 0
                    },
                    border: { display: false }
                }
            }
        }
    });

    if (canvasId === 'cpuChart') cpuChart = newChart;
    else if (canvasId === 'ramChart') ramChart = newChart;
    else if (canvasId === 'diskChart') diskChart = newChart;
}

function createEmptyCharts() {
    var emptyData = [0, 0];
    var emptyLabels = ['No Data', 'No Data'];
    createChart('cpuChart', 'CPU Usage %', emptyLabels, emptyData, 'cpu');
    createChart('ramChart', 'RAM Usage %', emptyLabels, emptyData, 'ram');
    createChart('diskChart', 'Disk Usage %', emptyLabels, emptyData, 'disk');
}

/**
 * Refresh chart colors on theme change
 * Called when theme is switched.
 */
function refreshChartTheme() {
    [cpuChart, ramChart, diskChart].forEach(function (chart) {
        if (!chart) return;
        var colors = getThemeColors();

        chart.options.scales.y.grid.color = colors.grid;
        chart.options.scales.y.ticks.color = colors.text;
        chart.options.scales.x.grid.color = colors.grid;
        chart.options.scales.x.ticks.color = colors.textMuted;

        chart.options.plugins.tooltip.backgroundColor = colors.tooltipBg;
        chart.options.plugins.tooltip.borderColor = colors.tooltipBorder;
        chart.options.plugins.tooltip.titleColor = colors.tooltipText;
        chart.options.plugins.tooltip.bodyColor = colors.tooltipBody;

        chart.update('none');
    });
}

/* ============================================================
   UTILITY FUNCTIONS
   ============================================================ */

function getStatusColor(status) {
    var colors = {
        'online': 'success',
        'warning': 'warning',
        'critical': 'danger',
        'offline': 'secondary'
    };
    return colors[status] || 'secondary';
}

function getStatusIcon(status) {
    var icons = {
        'online': 'fa-wifi',
        'warning': 'fa-exclamation-triangle',
        'critical': 'fa-exclamation-circle',
        'offline': 'fa-power-off'
    };
    return icons[status] || 'fa-question-circle';
}

function getProgressColor(value, type) {
    var v = Number(value || 0);
    if (!v) return 'secondary';

    var warningThreshold, criticalThreshold;
    switch (type) {
        case 'cpu': warningThreshold = 70; criticalThreshold = 90; break;
        case 'ram': warningThreshold = 80; criticalThreshold = 90; break;
        case 'disk': warningThreshold = 85; criticalThreshold = 95; break;
        default: warningThreshold = 70; criticalThreshold = 90;
    }

    if (v >= criticalThreshold) return 'danger';
    if (v >= warningThreshold) return 'warning';
    return 'success';
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    try {
        var date = new Date(timestamp);
        if (isNaN(date.getTime())) return String(timestamp);
        var now = new Date();
        var diff = Math.floor((now - date) / 1000);
        if (diff < 60) return 'Just now';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    } catch (e) {
        return String(timestamp);
    }
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    try {
        var date = new Date(timestamp);
        if (isNaN(date.getTime())) return '';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return '';
    }
}

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/* ============================================================
   PAGE INITIALIZATION
   ============================================================ */

function initPage() {
    var path = window.location.pathname;

    if (path === '/') {
        // Dashboard
        loadDashboard();
        setInterval(loadDashboard, CONFIG.refreshInterval);
    } else if (path.indexOf('/computer/') === 0) {
        // Computer details
        var computerId = path.split('/')[2];
        if (computerId) {
            loadComputerDetails(computerId);
            setInterval(function () {
                loadComputerDetails(computerId);
            }, CONFIG.refreshInterval);
        }
    }
}

function initSidebar() {
    $('#menu-toggle').on('click', function (e) {
        e.preventDefault();
        $('#wrapper').toggleClass('toggled');
    });
}

/**
 * Listen for theme changes and refresh charts
 */
function initThemeListener() {
    window.addEventListener('themechange', function () {
        // Small delay to let CSS variables apply first
        setTimeout(refreshChartTheme, 50);
    });

    // Fallback: watch for data-theme attribute changes
    var lastTheme = document.documentElement.getAttribute('data-theme');
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.attributeName === 'data-theme') {
                var newTheme = document.documentElement.getAttribute('data-theme');
                if (newTheme !== lastTheme) {
                    lastTheme = newTheme;
                    setTimeout(refreshChartTheme, 50);
                }
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true });
}

/* ============================================================
   BOOT
   ============================================================ */

$(document).ready(function () {
    initSidebar();
    initThemeListener();
    initPage();
    console.log('%c Nexus Core ', 'background: linear-gradient(135deg, #7c3aed, #ec4899); color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;', 'Theme-aware dashboard initialized');
});