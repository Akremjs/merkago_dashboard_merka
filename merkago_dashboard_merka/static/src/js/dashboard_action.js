/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

const PALETTE = [
    "#8B5CF6", "#3B82F6", "#14B8A6", "#F59E0B",
    "#EF4444", "#10B981", "#6366F1", "#EC4899",
    "#06B6D4", "#84CC16",
];

const KPI_TONES = ["violet", "blue", "teal", "orange"];

const CHART_TYPES = new Set([
    "bar", "hbar", "line", "pie", "doughnut", "area", "radar", "funnel",
    "scatter", "bullet", "waterfall", "polar", "flower",
]);

const DATE_FILTERS = [
    { value: "none", label: "Tous" },
    { value: "today", label: "Aujourd'hui" },
    { value: "last_7", label: "7 j" },
    { value: "last_30", label: "30 j" },
    { value: "last_90", label: "90 j" },
    { value: "this_month", label: "Ce mois" },
    { value: "last_month", label: "Mois préc." },
    { value: "this_year", label: "Cette année" },
    { value: "custom", label: "Perso" },
];

const REFRESH_OPTIONS = [
    { value: 0, label: "Off" },
    { value: 10, label: "Live" },
    { value: 30, label: "30s" },
    { value: 60, label: "1m" },
    { value: 300, label: "5m" },
];

const SWITCH_CYCLE = [
    "bar", "hbar", "line", "area", "pie", "doughnut", "radar", "funnel",
    "waterfall", "polar", "flower",
];
const THEMES = ["dark", "light", "ocean", "contrast"];
const TV_ROTATE_MS = 45000;
const RTL_LANGS = ["ar_", "he_", "fa_", "ur_", "yi_"];

/** Plugin Chart.js : affiche les valeurs sur les barres / points */
const MerkaValueLabels = {
    id: "merkaValueLabels",
    afterDatasetsDraw(chart, _args, opts) {
        if (!opts?.display) {
            return;
        }
        const { ctx } = chart;
        ctx.save();
        ctx.font = "600 10px Inter, sans-serif";
        ctx.fillStyle = opts.color || "#94A3B8";
        ctx.textAlign = "center";
        chart.data.datasets.forEach((ds, di) => {
            if (ds.stack === "wf" && ds.label === "Base") {
                return;
            }
            const meta = chart.getDatasetMeta(di);
            meta.data.forEach((el, i) => {
                const raw = ds.data[i];
                const val = typeof raw === "object" && raw !== null ? raw.y : raw;
                if (val === null || val === undefined) {
                    return;
                }
                const { x, y } = el.tooltipPosition();
                ctx.fillText(formatNumber(val), x, y - 6);
            });
        });
        ctx.restore();
    },
};

function formatNumber(value) {
    if (value === null || value === undefined || value === "—") {
        return "—";
    }
    const n = Number(value);
    if (Number.isNaN(n)) {
        return String(value);
    }
    if (Math.abs(n) >= 1_000_000) {
        return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + " M";
    }
    if (Math.abs(n) >= 1_000) {
        return (n / 1_000).toFixed(1).replace(/\.0$/, "") + " k";
    }
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(n);
}

function downloadDataUrl(dataUrl, filename) {
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = filename;
    a.click();
}

function downloadText(text, filename, mime = "text/csv") {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

const TONE_COLORS = {
    violet: "#8B5CF6",
    blue: "#3B82F6",
    teal: "#14B8A6",
    orange: "#F59E0B",
};

export class MerkaSparkline extends Component {
    static template = "merkago_dashboard_merka.Sparkline";
    static props = {
        values: Array,
        tone: { type: String, optional: true },
    };

    setup() {
        this.sparkRef = useRef("spark");
        this.chart = null;
        useEffect(
            () => {
                this.renderSpark();
                return () => this.destroy();
            },
            () => [this.props.values, this.props.tone]
        );
        onWillUnmount(() => this.destroy());
    }

    destroy() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    renderSpark() {
        this.destroy();
        if (!this.sparkRef.el || typeof Chart === "undefined") {
            return;
        }
        const values = (this.props.values || []).map((v) => Number(v) || 0);
        if (!values.length) {
            return;
        }
        const color = TONE_COLORS[this.props.tone] || TONE_COLORS.violet;
        this.chart = new Chart(this.sparkRef.el, {
            type: "line",
            data: {
                labels: values.map((_, i) => i),
                datasets: [
                    {
                        data: values,
                        borderColor: color,
                        backgroundColor: color + "33",
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: { display: false },
                },
            },
        });
    }
}

export class MerkaLayoutPad extends Component {
    static template = "merkago_dashboard_merka.LayoutPad";
    static props = {
        widthLabel: { type: String, optional: true },
        onMove: Function,
        onResize: Function,
    };
}

export class MerkaChartCard extends Component {
    static template = "merkago_dashboard_merka.ChartCard";
    static components = { MerkaLayoutPad };
    static props = {
        item: Object,
        displayType: { type: String, optional: true },
        editMode: { type: Boolean, optional: true },
        widthLabel: { type: String, optional: true },
        onOpen: Function,
        onSwitch: Function,
        onExportPng: Function,
        onExportCsv: Function,
        onExplain: Function,
        onChat: { type: Function, optional: true },
        onDrillPoint: { type: Function, optional: true },
        onMove: Function,
        onResize: Function,
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        useEffect(
            () => {
                this.renderChart();
                return () => this.destroyChart();
            },
            () => [this.props.item.data, this.props.displayType, this.props.item.item_type]
        );
        onWillUnmount(() => this.destroyChart());
    }

    get chartType() {
        return this.props.displayType || this.props.item.item_type;
    }

    get isChart() {
        return CHART_TYPES.has(this.chartType) || CHART_TYPES.has(this.props.item.data?.type);
    }

    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    renderChart() {
        this.destroyChart();
        if (!this.canvasRef.el || !this.isChart || typeof Chart === "undefined") {
            return;
        }
        const data = this.props.item.data || {};
        let labels = (data.labels || []).map((l) =>
            Array.isArray(l) ? l[1] || String(l[0]) : l === false || l === null ? "N/A" : String(l)
        );
        let values = (data.values || []).map((v) => Number(v) || 0);
        let type = this.chartType === "area" ? "line" : this.chartType;
        if (type === "bullet") {
            type = "bar";
        }
        const isFlower = type === "flower";
        if (type === "polar" || isFlower) {
            type = "polarArea";
        }
        if (type === "funnel") {
            const paired = labels.map((l, i) => ({ l, v: values[i] })).sort((a, b) => b.v - a.v);
            labels = paired.map((p) => p.l);
            values = paired.map((p) => p.v);
            type = "hbar";
        }
        const isWaterfall = type === "waterfall";
        if (isWaterfall) {
            type = "bar";
        }
        const isHbar = type === "hbar";
        const isScatter = type === "scatter";
        const isPolar = type === "polarArea";
        const chartJsType = isHbar ? "bar" : isScatter ? "scatter" : type;
        const isPie = chartJsType === "pie" || chartJsType === "doughnut" || isPolar;
        const colors = labels.map((_, i) => PALETTE[i % PALETTE.length]);
        const showValues = data.show_values !== false;

        let chartData;
        if (isScatter) {
            chartData = {
                datasets: [
                    {
                        label: this.props.item.name,
                        data: values.map((v, i) => ({ x: i + 1, y: v })),
                        backgroundColor: "#8B5CF6",
                    },
                ],
            };
        } else if (isWaterfall) {
            // Cascade simplifiée : barres + / − colorées
            const bases = [];
            let run = 0;
            values.forEach((v) => {
                bases.push(v >= 0 ? run : run + v);
                run += v;
            });
            chartData = {
                labels,
                datasets: [
                    {
                        label: "Base",
                        data: bases,
                        backgroundColor: "transparent",
                        borderWidth: 0,
                        stack: "wf",
                    },
                    {
                        label: data.name || this.props.item.name,
                        data: values.map((v) => Math.abs(v)),
                        backgroundColor: values.map((v) => (v >= 0 ? "#34D399" : "#F87171")),
                        borderWidth: 0,
                        borderRadius: 4,
                        stack: "wf",
                    },
                ],
            };
        } else {
            chartData = {
                labels,
                datasets: [
                    {
                        label: data.name || this.props.item.name,
                        data: values,
                        backgroundColor: isPie
                            ? colors.map((c) => (isFlower ? c + "DD" : c))
                            : chartJsType === "line"
                              ? "rgba(139, 92, 246, 0.18)"
                              : colors.map((c) => c + "CC"),
                        borderColor: isPie ? (isFlower ? colors : "#fff") : chartJsType === "line" ? "#8B5CF6" : colors,
                        borderWidth: isFlower ? 3 : 2,
                        fill: this.chartType === "area",
                        tension: 0.35,
                        borderRadius: isFlower ? 40 : chartJsType === "bar" ? 8 : 0,
                        spacing: isFlower ? 6 : 0,
                        pointRadius: chartJsType === "line" ? 3 : 0,
                    },
                ],
            };
        }

        const self = this;
        this.chart = new Chart(this.canvasRef.el, {
            type: chartJsType === "radar" ? "radar" : chartJsType,
            data: chartData,
            plugins: [MerkaValueLabels],
            options: {
                indexAxis: isHbar ? "y" : "x",
                responsive: true,
                maintainAspectRatio: false,
                onClick(_evt, elements) {
                    if (!elements.length || self.props.editMode) {
                        return;
                    }
                    const idx = elements[0].index;
                    const label = labels[idx];
                    if (self.props.onDrillPoint) {
                        self.props.onDrillPoint(self.props.item.id, label, idx);
                    }
                },
                plugins: {
                    merkaValueLabels: {
                        display: showValues && !isPie && chartJsType !== "radar",
                        color: "#CBD5E1",
                    },
                    legend: {
                        display: isPie || chartJsType === "radar",
                        position: "bottom",
                        labels: { boxWidth: 10, padding: 12, color: "#94A3B8", font: { size: 11 } },
                    },
                    tooltip: {
                        backgroundColor: "#0F172A",
                        padding: 10,
                        cornerRadius: 8,
                        callbacks: {
                            label: (ctx) => {
                                if (isWaterfall && ctx.datasetIndex === 0) {
                                    return null;
                                }
                                const val = isScatter
                                    ? ctx.parsed.y
                                    : isHbar
                                      ? ctx.parsed.x
                                      : ctx.parsed.r ?? ctx.parsed.y ?? ctx.parsed;
                                return ` ${formatNumber(val)}`;
                            },
                        },
                    },
                },
                scales: isPie || chartJsType === "radar"
                    ? {}
                    : {
                          x: {
                              beginAtZero: isHbar,
                              stacked: isWaterfall,
                              grid: {
                                  color: isHbar ? "rgba(148,163,184,0.18)" : "transparent",
                                  drawBorder: false,
                              },
                              ticks: { color: "#94A3B8", font: { size: 10 } },
                              border: { display: false },
                          },
                          y: {
                              beginAtZero: !isHbar,
                              stacked: isWaterfall,
                              grid: {
                                  color: isHbar ? "transparent" : "rgba(148,163,184,0.18)",
                                  drawBorder: false,
                              },
                              ticks: { color: "#94A3B8", font: { size: 10 } },
                              border: { display: false },
                          },
                      },
            },
        });
    }

    onDrill() {
        this.props.onOpen(this.props.item.id);
    }
    onSwitch() {
        this.props.onSwitch(this.props.item.id);
    }
    onPng() {
        if (this.chart) {
            downloadDataUrl(this.chart.toBase64Image("image/png", 1), `${this.props.item.name || "chart"}.png`);
        }
        this.props.onExportPng(this.props.item.id);
    }
    onCsv() {
        this.props.onExportCsv(this.props.item.id);
    }
    onExplain() {
        this.props.onExplain(this.props.item.id);
    }
    onChat() {
        if (this.props.onChat) {
            this.props.onChat(this.props.item.id);
        }
    }
}

export class MerkaDashboardAction extends Component {
    static template = "merkago_dashboard_merka.Dashboard";
    static components = { MerkaChartCard, MerkaSparkline, MerkaLayoutPad };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        // bus_service a async:true → useService plante (methods is not iterable)
        this.busService = this.env.services.bus_service;
        this.rootRef = useRef("root");
        const params = this.props.action?.params || {};
        const ctx = this.props.action?.context || {};
        this._openedAsTv = Boolean(params.tv_mode || ctx.tv_mode);
        this._streamChannel = null;
        this.state = useState({
            name: "",
            packCode: "",
            items: [],
            tiles: [],
            charts: [],
            lists: [],
            nav: [],
            companies: [],
            companyId: false,
            isFavorite: false,
            isHome: false,
            loading: true,
            lastRefresh: null,
            dateFilter: "last_30",
            dateFrom: false,
            dateTo: false,
            showCompare: true,
            switchMap: {},
            layoutMap: {},
            theme: "dark",
            editMode: false,
            tvMode: this._openedAsTv,
            tvRotate: this._openedAsTv,
            storyMode: false,
            storyIndex: 0,
            storySlides: [],
            crossFilter: null,
            bookmarks: [],
            sidebarOpen: false,
            refreshSeconds: 0,
            dashboardId: params.dashboard_id || ctx.dashboard_id || false,
            dragItemId: null,
            rtl: false,
            streamEnabled: true,
            streamLive: false,
            aiEnabled: false,
            aiAllowUserChoice: true,
            aiMode: "local",
            aiModes: [{ value: "local", label: "Local", ready: true }],
            aiChatOpen: false,
            aiThreadId: false,
            aiMessages: [],
            aiSuggestions: [],
            aiDraft: "",
            aiBusy: false,
            aiMultiGenerate: true,
            // legacy panel fields (compat actions)
            aiPanelOpen: false,
            aiPanelTitle: "",
            aiPanelBody: "",
            aiPanelSource: "local",
            aiPanelActions: [],
        });
        this.dateFilters = DATE_FILTERS;
        this.refreshOptions = REFRESH_OPTIONS;
        this._timer = null;
        this._tvTimer = null;
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboard();
        });
        this._onKeydown = (ev) => {
            if (ev.key === "Escape" && this.state.aiChatOpen) {
                ev.preventDefault();
                this.onCloseAiChat();
                return;
            }
            if (ev.key === "Escape" && this.state.aiPanelOpen) {
                ev.preventDefault();
                this.onCloseAiPanel();
                return;
            }
            if (ev.key === "Escape" && this.state.storyMode) {
                ev.preventDefault();
                this.onToggleStory();
                return;
            }
            if (ev.key === "Escape" && this.state.tvMode) {
                ev.preventDefault();
                this.onExitTv();
                return;
            }
            if (this.state.storyMode && ev.key === "ArrowRight") {
                this.onStoryNext();
            }
            if (this.state.storyMode && ev.key === "ArrowLeft") {
                this.onStoryPrev();
            }
        };
        this._streamSubscribed = false;
        this._onStreamRefresh = (payload) => {
            const did = payload?.dashboard_id;
            if (did && did === this.state.dashboardId) {
                this.state.streamLive = true;
                this.loadDashboard(true);
            }
        };
        onMounted(() => {
            this._armRefresh();
            this._armTvRotate();
            this._armStream();
            window.addEventListener("keydown", this._onKeydown);
        });
        this._storyTimer = null;
        onWillUnmount(() => {
            this._clearRefresh();
            this._clearTvRotate();
            this._clearStoryRotate();
            this._clearStream();
            window.removeEventListener("keydown", this._onKeydown);
        });
    }

    get formatNumber() {
        return formatNumber;
    }

    get shellClass() {
        return {
            [`theme-${this.state.theme}`]: true,
            "is-tv": this.state.tvMode,
            "is-edit": this.state.editMode,
            "has-sidebar": !this.state.tvMode,
            "sidebar-open": this.state.sidebarOpen,
            "is-rtl": this.state.rtl,
            "is-stream": this.state.streamLive,
        };
    }

    get aiModeLabel() {
        const modes = this.state.aiModes || [];
        const hit = modes.find((m) => m.value === this.state.aiMode);
        if (hit) {
            return hit.label;
        }
        return this.state.aiMode || "Local";
    }

    _armStream() {
        if (!this.state.streamEnabled || !this.state.dashboardId || !this.busService) {
            return;
        }
        const channel = `merka.dashboard.${this.state.dashboardId}`;
        if (this._streamChannel && this._streamChannel !== channel) {
            try {
                this.busService.deleteChannel(this._streamChannel);
            } catch (_e) {
                /* ignore */
            }
        }
        this._streamChannel = channel;
        this.busService.addChannel(channel);
        if (!this._streamSubscribed) {
            this.busService.subscribe("merka_dashboard_refresh", this._onStreamRefresh);
            this._streamSubscribed = true;
        }
    }

    _clearStream() {
        if (this._streamChannel && this.busService) {
            try {
                this.busService.deleteChannel(this._streamChannel);
            } catch (_e) {
                /* ignore */
            }
        }
        this._streamChannel = null;
    }

    get sortedItems() {
        return [...(this.state.items || [])].sort((a, b) => {
            const la = this._layoutOf(a.id, a);
            const lb = this._layoutOf(b.id, b);
            if (la.layout_y !== lb.layout_y) {
                return la.layout_y - lb.layout_y;
            }
            if (la.layout_x !== lb.layout_x) {
                return la.layout_x - lb.layout_x;
            }
            return (la.sequence || 0) - (lb.sequence || 0);
        });
    }

    kpiTone(index) {
        return KPI_TONES[index % KPI_TONES.length];
    }

    kpiToneClass(index) {
        return `tone-${this.kpiTone(index)}`;
    }

    isTile(item) {
        return item.item_type === "tile" || item.data?.type === "tile";
    }

    isChart(item) {
        return CHART_TYPES.has(item.item_type);
    }

    isPivot(item) {
        return item.item_type === "pivot" || item.data?.type === "pivot";
    }

    pivotRows(item) {
        const data = item.data || {};
        const rows = data.rows || [];
        const matrix = data.matrix || [];
        const intensities = data.intensities || [];
        const totals = data.row_totals || [];
        return rows.map((label, i) => ({
            label,
            cells: (matrix[i] || []).map((value, j) => ({
                value,
                intensity: (intensities[i] || [])[j] || 0,
                colLabel: (data.cols || [])[j],
            })),
            total: totals[i] || 0,
        }));
    }

    pivotHeatStyle(intensity) {
        const i = Math.max(0, Math.min(1, Number(intensity) || 0));
        return `background: rgba(139, 92, 246, ${0.08 + i * 0.55})`;
    }

    onToggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
    }

    onCloseSidebar() {
        this.state.sidebarOpen = false;
    }

    displayType(item) {
        return this.state.switchMap[item.id] || item.item_type;
    }

    _defaultW(item) {
        if (item.item_type === "tile") {
            return 3;
        }
        if (item.item_type === "pivot") {
            return 12;
        }
        if (item.item_type === "list") {
            return 6;
        }
        return 6;
    }

    _layoutOf(itemId, item = null) {
        const cur = this.state.layoutMap[itemId] || {};
        const src = item || this.state.items.find((i) => i.id === itemId) || {};
        const w = Math.min(12, Math.max(2, cur.layout_w || src.layout_w || this._defaultW(src)));
        return {
            layout_x: Math.max(0, Math.min(11, cur.layout_x ?? src.layout_x ?? 0)),
            layout_y: Math.max(0, cur.layout_y ?? src.layout_y ?? 0),
            layout_w: w,
            layout_h: cur.layout_h || src.layout_h || 2,
            sequence: cur.sequence ?? src.sequence ?? 10,
        };
    }

    widthLabel(item) {
        return `${this._layoutOf(item.id, item).layout_w}/12`;
    }

    cellStyle(item) {
        const L = this._layoutOf(item.id, item);
        const colStart = L.layout_x + 1;
        const colEnd = Math.min(13, colStart + L.layout_w);
        return `grid-column: ${colStart} / ${colEnd}; grid-row: ${L.layout_y + 1};`;
    }

    cellClass(item) {
        return {
            "is-tile": this.isTile(item),
            "is-chart": this.isChart(item),
            "is-list": item.item_type === "list",
            "is-pivot": this.isPivot(item),
            "is-editing": this.state.editMode,
        };
    }

    onKpiClick(item) {
        if (this.state.editMode) {
            return;
        }
        this.onOpenRecords(item.id);
    }

    /** Place les widgets sans chevauchement (lignes de 12 colonnes). */
    _autoPackLayouts(items) {
        const layoutMap = {};
        let x = 0;
        let y = 0;
        const sorted = [...items].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
        sorted.forEach((item, i) => {
            let w = Math.min(12, Math.max(2, item.layout_w || this._defaultW(item)));
            if (x + w > 12) {
                y += 1;
                x = 0;
            }
            layoutMap[item.id] = {
                layout_x: x,
                layout_y: y,
                layout_w: w,
                layout_h: item.layout_h || 2,
                sequence: (i + 1) * 10,
            };
            x += w;
            if (x >= 12) {
                x = 0;
                y += 1;
            }
        });
        return layoutMap;
    }

    trendClass(item) {
        const t = item.data?.trend;
        if (t === null || t === undefined) {
            return "is-flat";
        }
        return t > 0 ? "is-up" : t < 0 ? "is-down" : "is-flat";
    }

    trendIcon(item) {
        const t = item.data?.trend;
        if (t > 0) {
            return "fa fa-arrow-up";
        }
        if (t < 0) {
            return "fa fa-arrow-down";
        }
        return "fa fa-minus";
    }

    trendLabel(item) {
        const t = item.data?.trend;
        if (t === null || t === undefined) {
            return "—";
        }
        return `${t > 0 ? "+" : ""}${t.toFixed(1)} %`;
    }

    progressPct(item) {
        if (item.data?.progress_pct !== null && item.data?.progress_pct !== undefined) {
            return Math.min(100, Math.round(Number(item.data.progress_pct)));
        }
        const target = Number(item.data?.target || 0);
        const value = Number(item.data?.value || 0);
        if (!target) {
            return 0;
        }
        return Math.min(100, Math.round((value / target) * 100));
    }

    progressTone(item) {
        const pct = this.progressPct(item);
        if (pct >= 100) {
            return "is-ok";
        }
        if (pct >= 70) {
            return "is-warn";
        }
        return "is-low";
    }

    previousLabel(item) {
        if (!this.state.showCompare || item.data?.previous === null || item.data?.previous === undefined) {
            return "";
        }
        return `vs préc. ${formatNumber(item.data.previous)}`;
    }

    _clearRefresh() {
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
    }

    _armRefresh() {
        this._clearRefresh();
        if (this.state.refreshSeconds > 0) {
            this._timer = setInterval(() => this.loadDashboard(true), this.state.refreshSeconds * 1000);
        }
    }

    _clearTvRotate() {
        if (this._tvTimer) {
            clearInterval(this._tvTimer);
            this._tvTimer = null;
        }
    }

    _armTvRotate() {
        this._clearTvRotate();
        if (this.state.tvMode && this.state.tvRotate && this.state.nav?.length > 1) {
            this._tvTimer = setInterval(() => this._rotateNav(), TV_ROTATE_MS);
        }
    }

    async _rotateNav() {
        const nav = this.state.nav || [];
        if (nav.length < 2) {
            return;
        }
        const idx = nav.findIndex((n) => n.active);
        const next = nav[(idx + 1) % nav.length];
        if (next) {
            await this.onSelectNav(next);
        }
    }

    async _ensureDashboardId() {
        const params = this.props.action?.params || {};
        const ctx = this.props.action?.context || {};
        let id =
            this.state.dashboardId ||
            params.dashboard_id ||
            ctx.dashboard_id ||
            false;
        if (!id) {
            try {
                id = await this.orm.call("merka.dashboard", "resolve_default_dashboard_id", []);
            } catch (_e) {
                id = false;
            }
        }
        if (id) {
            this.state.dashboardId = id;
        }
        return id;
    }

    async loadDashboard(silent = false) {
        if (!silent) {
            this.state.loading = true;
        }
        const dashboardId = await this._ensureDashboardId();
        if (!dashboardId) {
            this.state.loading = false;
            this.state.items = [];
            this.state.name = "Aucun tableau";
            return;
        }
        try {
            let globalFilter = this.state.dateFilter;
            let dateFrom = null;
            let dateTo = null;
            if (globalFilter === "none") {
                globalFilter = null;
            } else if (globalFilter === "custom") {
                dateFrom = this.state.dateFrom || null;
                dateTo = this.state.dateTo || null;
            }
            const payload = await this.orm.call(
                "merka.dashboard",
                "get_dashboard_payload",
                [
                    dashboardId,
                    globalFilter,
                    dateFrom,
                    dateTo,
                    this.state.companyId || null,
                    this.state.crossFilter || null,
                ]
            );
            this.state.name = payload.name;
            this.state.packCode = payload.pack_code || "";
            this.state.theme = payload.theme || this.state.theme || "dark";
            this.state.nav = payload.nav || [];
            this.state.companies = payload.companies || [];
            this.state.companyId = payload.company_id || this.state.companyId;
            this.state.isFavorite = !!payload.is_favorite;
            this.state.isHome = !!payload.is_home;
            this.state.storySlides = payload.story_slides || [];
            this.state.bookmarks = payload.bookmarks || [];
            this.state.rtl = !!payload.rtl;
            this.state.streamEnabled = payload.stream_enabled !== false;
            this.state.aiEnabled = !!payload.ai_enabled;
            this.state.aiMultiGenerate = payload.ai_multi_generate !== false;
            if (!silent && payload.refresh_seconds && !this.state.refreshSeconds) {
                this.state.refreshSeconds = payload.refresh_seconds;
                this._armRefresh();
            }
            if (this.state.dashboardId) {
                this._armStream();
            }
            this.state.items = payload.items || [];
            const items = payload.items || [];
            // Tous à (0,0) = pas encore placés → auto-pack
            const allAtOrigin =
                items.length > 0 &&
                items.every((i) => !(i.layout_x || 0) && !(i.layout_y || 0));
            let layoutMap = {};
            if (allAtOrigin && !Object.keys(this.state.layoutMap || {}).length) {
                layoutMap = this._autoPackLayouts(items);
            } else {
                for (const item of items) {
                    layoutMap[item.id] = this.state.layoutMap[item.id] || {
                        layout_w: item.layout_w || this._defaultW(item),
                        layout_h: item.layout_h || 2,
                        layout_x: item.layout_x || 0,
                        layout_y: item.layout_y || 0,
                        sequence: item.sequence,
                    };
                }
                // Si toujours tous à l'origine côté map, pack
                if (
                    items.length > 1 &&
                    Object.values(layoutMap).every((L) => !(L.layout_x || 0) && !(L.layout_y || 0))
                ) {
                    layoutMap = this._autoPackLayouts(items);
                }
            }
            this.state.layoutMap = layoutMap;
            this.state.tiles = items.filter((i) => i.item_type === "tile" || i.data?.type === "tile");
            this.state.charts = items.filter((i) => CHART_TYPES.has(i.item_type));
            this.state.lists = items.filter((i) => i.item_type === "list");
            this.state.lastRefresh = new Date().toLocaleTimeString("fr-FR");
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async onSelectNav(entry) {
        if (!entry) {
            return;
        }
        this.state.sidebarOpen = false;
        if (entry.id && entry.id === this.state.dashboardId) {
            return;
        }
        this.state.loading = true;
        this.state.layoutMap = {};
        this.state.switchMap = {};
        this.state.crossFilter = null;
        try {
            let dashId = entry.id;
            if (!dashId && entry.pack_code) {
                dashId = await this.orm.call("merka.dashboard", "ensure_pack_dashboard_id", [
                    entry.pack_code,
                ]);
            }
            if (!dashId) {
                this.notification.add("Dashboard introuvable", { type: "warning" });
                this.state.loading = false;
                return;
            }
            this.state.dashboardId = dashId;
            await this.loadDashboard();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
            this.state.loading = false;
        }
    }

    async onOpenAll() {
        await this._safeDoAction("merkago_dashboard_merka.action_merka_reports_hub");
    }

    async onOpenSettings() {
        await this._safeDoAction("merkago_dashboard_merka.action_merka_dashboard_config");
    }

    async _safeDoAction(action) {
        if (!action) {
            this.notification.add("Action indisponible", { type: "warning" });
            return;
        }
        try {
            // act_window renvoyée par RPC : garantir views pour Odoo 17
            if (typeof action === "object" && action.type === "ir.actions.act_window") {
                if (!action.views) {
                    const modes = (action.view_mode || "list,form").split(",");
                    action.views = modes.map((m) => [false, m === "tree" ? "list" : m.trim()]);
                }
                if (!action.target) {
                    action.target = "current";
                }
            }
            await this.action.doAction(action);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
    }

    async onDateFilter(value) {
        this.state.dateFilter = value;
        if (value !== "custom") {
            await this.loadDashboard();
        }
    }

    onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value || false;
    }

    onDateToChange(ev) {
        this.state.dateTo = ev.target.value || false;
    }

    async onApplyCustomDates() {
        await this.loadDashboard();
    }

    onSetRefresh(seconds) {
        this.state.refreshSeconds = seconds;
        this._armRefresh();
        this.notification.add(
            seconds ? `Refresh auto ${seconds}s` : "Refresh auto désactivé",
            { type: "info" }
        );
    }

    async onRefresh() {
        await this.loadDashboard();
        this.notification.add("Tableau actualisé", { type: "success" });
    }

    async onReloadHome() {
        this.state.dashboardId = false;
        this.state.layoutMap = {};
        await this.loadDashboard();
        if (this.state.dashboardId) {
            this.notification.add("Dashboard chargé", { type: "success" });
        } else {
            this.notification.add("Aucun dashboard disponible — ouvrez Dashboard Merka", {
                type: "warning",
            });
        }
    }

    onToggleEdit() {
        const next = !this.state.editMode;
        if (next) {
            // S'assurer que chaque widget a une position utilisable
            const map = { ...this.state.layoutMap };
            let needsPack = false;
            for (const item of this.state.items) {
                if (!map[item.id]) {
                    needsPack = true;
                    break;
                }
            }
            if (needsPack) {
                this.state.layoutMap = this._autoPackLayouts(this.state.items);
            }
        }
        this.state.editMode = next;
    }

    onAutoPack() {
        this.state.layoutMap = this._autoPackLayouts(this.state.items);
        this.notification.add("Grille réorganisée — pensez à Enregistrer", { type: "info" });
    }

    onCycleTheme() {
        const idx = THEMES.indexOf(this.state.theme);
        this.state.theme = THEMES[(idx + 1) % THEMES.length];
    }

    onToggleTv() {
        if (this.state.tvMode) {
            this.onExitTv();
            return;
        }
        this.state.tvMode = true;
        if (!this.state.refreshSeconds) {
            this.state.refreshSeconds = 60;
            this._armRefresh();
        }
        this.state.tvRotate = true;
        this._armTvRotate();
        this.notification.add("Mode TV — bouton rouge en haut à droite pour quitter (ou Échap)", {
            type: "info",
        });
    }

    async onExitTv() {
        this.state.tvMode = false;
        this.state.tvRotate = false;
        this.state.storyMode = false;
        this._clearTvRotate();
        this._clearStoryRotate();
        // Ouvert via « Mode TV » plein écran → revenir au dashboard normal
        if (this._openedAsTv && this.state.dashboardId) {
            this._openedAsTv = false;
            try {
                await this.action.doAction({
                    type: "ir.actions.client",
                    tag: "merka_dashboard_action",
                    name: this.state.name || "Dashboard Merka",
                    target: "current",
                    params: { dashboard_id: this.state.dashboardId, tv_mode: false },
                    context: { dashboard_id: this.state.dashboardId, tv_mode: false },
                });
            } catch (_e) {
                this.notification.add("Mode TV quitté", { type: "success" });
            }
            return;
        }
        this.notification.add("Mode TV quitté", { type: "success" });
    }

    onToggleCompare() {
        this.state.showCompare = !this.state.showCompare;
    }

    async onToggleFavorite() {
        await this.orm.call("merka.dashboard", "action_toggle_favorite", [[this.state.dashboardId]]);
        this.state.isFavorite = !this.state.isFavorite;
        this.notification.add(
            this.state.isFavorite ? "Ajouté aux favoris" : "Retiré des favoris",
            { type: "success" }
        );
    }

    async onSetHome() {
        await this.orm.call("merka.dashboard", "action_set_as_home", [[this.state.dashboardId]]);
        this.state.isHome = true;
        this.state.isFavorite = true;
        this.notification.add("Défini comme accueil Merka", { type: "success" });
    }

    async onCompanyChange(ev) {
        const id = Number(ev.target.value) || false;
        this.state.companyId = id;
        await this.loadDashboard();
    }

    onDragStart(ev, item) {
        if (!this.state.editMode) {
            return;
        }
        this.state.dragItemId = item.id;
        ev.dataTransfer.effectAllowed = "move";
        try {
            ev.dataTransfer.setData("text/plain", String(item.id));
        } catch (_e) {
            /* ignore */
        }
    }

    onDragOver(ev) {
        if (!this.state.editMode || !this.state.dragItemId) {
            return;
        }
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
    }

    onDrop(ev, targetItem) {
        if (!this.state.editMode) {
            return;
        }
        ev.preventDefault();
        const fromId = this.state.dragItemId || Number(ev.dataTransfer.getData("text/plain"));
        const toId = targetItem?.id;
        this.state.dragItemId = null;
        if (!fromId || !toId || fromId === toId) {
            return;
        }
        const A = { ...this._layoutOf(fromId) };
        const B = { ...this._layoutOf(toId) };
        this.state.layoutMap = {
            ...this.state.layoutMap,
            [fromId]: { ...A, layout_x: B.layout_x, layout_y: B.layout_y },
            [toId]: { ...B, layout_x: A.layout_x, layout_y: A.layout_y },
        };
    }

    async onDrillPoint(itemId, label, idx) {
        const item = this.state.items.find((i) => i.id === itemId);
        // Filtre croisé : recliquer la même valeur = clear
        if (
            this.state.crossFilter &&
            this.state.crossFilter.source_item_id === itemId &&
            this.state.crossFilter.label === label
        ) {
            await this.onClearCrossFilter();
            return;
        }
        const field = item?.groupby || item?.data?.cross_field || false;
        const model = item?.model_name || item?.data?.cross_model || false;
        let value = label;
        if (item?.data?.raw_keys && item.data.raw_keys[idx] !== undefined) {
            const raw = item.data.raw_keys[idx];
            value = Array.isArray(raw) ? raw[0] : raw;
        }
        if (field && model) {
            this.state.crossFilter = {
                source_item_id: itemId,
                field,
                label,
                value,
                model,
            };
            this.notification.add(`Filtre : ${label} — recliquez pour retirer`, { type: "info" });
            await this.loadDashboard();
            return;
        }
        // Fallback : ouvrir les enregistrements
        let globalFilter = this.state.dateFilter;
        let dateFrom = null;
        let dateTo = null;
        if (globalFilter === "none") {
            globalFilter = null;
        } else if (globalFilter === "custom") {
            dateFrom = this.state.dateFrom || null;
            dateTo = this.state.dateTo || null;
        }
        try {
            const action = await this.orm.call("merka.dashboard.item", "action_drill_groupby", [
                itemId,
                label,
                globalFilter,
                dateFrom,
                dateTo,
            ]);
            await this._safeDoAction(action);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        }
    }

    async onClearCrossFilter() {
        this.state.crossFilter = null;
        await this.loadDashboard();
        this.notification.add("Filtre croisé retiré", { type: "success" });
    }

    onToggleStory() {
        if (!this.state.storySlides?.length) {
            this.notification.add("Aucune tuile pour le story mode", { type: "warning" });
            return;
        }
        this.state.storyMode = !this.state.storyMode;
        this.state.storyIndex = 0;
        if (this.state.storyMode) {
            this.state.tvMode = true;
            this.state.tvRotate = false;
            this._clearTvRotate();
            this._armStoryRotate();
        } else {
            this._clearStoryRotate();
            if (!this._openedAsTv) {
                this.state.tvMode = false;
            }
        }
    }

    _clearStoryRotate() {
        if (this._storyTimer) {
            clearInterval(this._storyTimer);
            this._storyTimer = null;
        }
    }

    _armStoryRotate() {
        this._clearStoryRotate();
        if (this.state.storyMode && this.state.storySlides?.length > 1) {
            this._storyTimer = setInterval(() => this.onStoryNext(), 8000);
        }
    }

    onStoryNext() {
        const n = this.state.storySlides?.length || 0;
        if (!n) {
            return;
        }
        this.state.storyIndex = (this.state.storyIndex + 1) % n;
    }

    onStoryPrev() {
        const n = this.state.storySlides?.length || 0;
        if (!n) {
            return;
        }
        this.state.storyIndex = (this.state.storyIndex - 1 + n) % n;
    }

    storySlide() {
        return (this.state.storySlides || [])[this.state.storyIndex] || null;
    }

    storyTrendLabel(slide) {
        if (!slide || slide.trend === null || slide.trend === undefined) {
            return "—";
        }
        const t = Number(slide.trend);
        if (Number.isNaN(t)) {
            return "—";
        }
        return `${t > 0 ? "+" : ""}${t.toFixed(1)}`;
    }

    storyProgressLabel() {
        const total = (this.state.storySlides || []).length;
        return `${this.state.storyIndex + 1} / ${total}`;
    }

    async onOpenKpiWizard() {
        await this._safeDoAction({
            type: "ir.actions.act_window",
            name: "Nouveau KPI",
            res_model: "merka.dashboard.kpi.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: { default_dashboard_id: this.state.dashboardId },
        });
    }

    async onPivotCellClick(item, rowLabel, colLabel) {
        if (this.state.editMode || !item) {
            return;
        }
        const data = item.data || {};
        const field = data.row_field;
        const value = (data.row_raws || {})[rowLabel];
        if (!field) {
            return;
        }
        if (
            this.state.crossFilter &&
            this.state.crossFilter.source_item_id === item.id &&
            this.state.crossFilter.label === rowLabel
        ) {
            await this.onClearCrossFilter();
            return;
        }
        this.state.crossFilter = {
            source_item_id: item.id,
            field,
            label: `${rowLabel}${colLabel ? " / " + colLabel : ""}`,
            value: value !== undefined ? value : rowLabel,
            model: data.cross_model || item.model_name,
        };
        this.notification.add(`Filtre pivot : ${rowLabel}`, { type: "info" });
        await this.loadDashboard();
    }

    async onSaveBookmark() {
        const name = window.prompt("Nom du signet ?", `Vue ${this.state.dateFilter || ""}`.trim());
        if (!name) {
            return;
        }
        await this.orm.call("merka.dashboard.bookmark", "save_bookmark", [
            name,
            this.state.dashboardId,
            this.state.dateFilter,
            this.state.dateFrom || null,
            this.state.dateTo || null,
            this.state.companyId || null,
            this.state.crossFilter || null,
        ]);
        this.notification.add("Signet enregistré", { type: "success" });
        await this.loadDashboard(true);
    }

    async onApplyBookmark(bm) {
        if (!bm) {
            return;
        }
        this.state.dateFilter = bm.date_filter || "last_30";
        this.state.dateFrom = bm.date_from || false;
        this.state.dateTo = bm.date_to || false;
        this.state.crossFilter = bm.cross_filter || null;
        if (bm.company_id) {
            this.state.companyId = bm.company_id;
        }
        if (bm.dashboard_id && bm.dashboard_id !== this.state.dashboardId) {
            this.state.dashboardId = bm.dashboard_id;
            this.state.layoutMap = {};
        }
        await this.loadDashboard();
        this.notification.add(`Signet « ${bm.name} » appliqué`, { type: "success" });
    }

    async onDeleteBookmark(bm) {
        if (!bm?.id) {
            return;
        }
        await this.orm.call("merka.dashboard.bookmark", "action_delete_bookmark", [[bm.id]]);
        this.state.bookmarks = (this.state.bookmarks || []).filter((b) => b.id !== bm.id);
        this.notification.add("Signet supprimé", { type: "info" });
    }

    anomalyLabel(item) {
        return item?.data?.anomaly?.label || "";
    }

    async onOpenListRecord(itemId, resId) {
        try {
            const action = await this.orm.call("merka.dashboard.item", "action_open_record", [
                itemId,
                resId,
            ]);
            await this._safeDoAction(action);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        }
    }

    async onExportExcel() {
        let globalFilter = this.state.dateFilter;
        let dateFrom = null;
        let dateTo = null;
        if (globalFilter === "none") {
            globalFilter = null;
        } else if (globalFilter === "custom") {
            dateFrom = this.state.dateFrom || null;
            dateTo = this.state.dateTo || null;
        }
        const result = await this.orm.call("merka.dashboard", "export_dashboard_excel", [
            this.state.dashboardId,
            globalFilter,
            dateFrom,
            dateTo,
        ]);
        downloadText(result.content, result.filename || "merka.xls", result.mimetype || "application/vnd.ms-excel");
        this.notification.add("Excel téléchargé", { type: "success" });
    }

    onSwitchLayout(itemId) {
        const item = this.state.items.find((i) => i.id === itemId);
        if (!item || !CHART_TYPES.has(item.item_type)) {
            return;
        }
        const current = this.state.switchMap[itemId] || item.item_type;
        const idx = SWITCH_CYCLE.indexOf(current);
        const next = SWITCH_CYCLE[(idx + 1) % SWITCH_CYCLE.length];
        this.state.switchMap = { ...this.state.switchMap, [itemId]: next };
    }

    onMoveWidget(itemId, dir) {
        const item = this.state.items.find((i) => i.id === itemId);
        if (!item) {
            return;
        }
        const cur = { ...this._layoutOf(itemId, item) };
        if (dir === "left") {
            cur.layout_x = Math.max(0, cur.layout_x - 1);
        } else if (dir === "right") {
            cur.layout_x = Math.min(12 - cur.layout_w, cur.layout_x + 1);
        } else if (dir === "up") {
            cur.layout_y = Math.max(0, cur.layout_y - 1);
        } else if (dir === "down") {
            cur.layout_y = cur.layout_y + 1;
        }
        this.state.layoutMap = {
            ...this.state.layoutMap,
            [itemId]: cur,
        };
    }

    onResizeItem(itemId, dir) {
        const item = this.state.items.find((i) => i.id === itemId);
        const cur = { ...this._layoutOf(itemId, item) };
        let w = cur.layout_w + dir;
        w = Math.min(12, Math.max(2, w));
        cur.layout_w = w;
        if (cur.layout_x + w > 12) {
            cur.layout_x = Math.max(0, 12 - w);
        }
        this.state.layoutMap = {
            ...this.state.layoutMap,
            [itemId]: cur,
        };
    }

    async onSaveLayout() {
        const layouts = Object.entries(this.state.layoutMap).map(([id, row]) => ({
            id: Number(id),
            layout_x: row.layout_x || 0,
            layout_y: row.layout_y || 0,
            layout_w: row.layout_w || 3,
            layout_h: row.layout_h || 2,
            sequence: row.sequence || 10,
        }));
        await this.orm.call("merka.dashboard", "save_layout", [this.state.dashboardId, layouts]);
        this.notification.add("Layout enregistré", { type: "success" });
        this.state.editMode = false;
        // garder layoutMap (déjà sauvé) — recharge pour sync serveur
        const kept = { ...this.state.layoutMap };
        await this.loadDashboard();
        this.state.layoutMap = { ...kept, ...this.state.layoutMap };
    }

    async onOpenRecords(itemId) {
        try {
            const action = await this.orm.call("merka.dashboard.item", "action_open_records", [itemId]);
            await this._safeDoAction(action);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        }
    }

    async onExportCsv(itemId) {
        let globalFilter = this.state.dateFilter;
        let dateFrom = null;
        let dateTo = null;
        if (globalFilter === "none") {
            globalFilter = null;
        } else if (globalFilter === "custom") {
            dateFrom = this.state.dateFrom || null;
            dateTo = this.state.dateTo || null;
        }
        const result = await this.orm.call("merka.dashboard", "export_item_csv", [
            this.state.dashboardId,
            itemId,
            globalFilter,
            dateFrom,
            dateTo,
        ]);
        downloadText(result.content, result.filename || "export.csv");
        this.notification.add("CSV téléchargé", { type: "success" });
    }

    onExportPng(itemId) {
        // PNG déjà généré côté MerkaChartCard via Chart.js ; notification ici
        this.notification.add(itemId ? "PNG téléchargé" : "PNG", { type: "success" });
    }

    onExportPdf() {
        document.body.classList.add("merka-printing");
        window.print();
        setTimeout(() => document.body.classList.remove("merka-printing"), 600);
    }

    aiMessageLines(msg) {
        const body = (msg && msg.body) || "";
        return body.split("\n");
    }

    _applyAiModePayload(res) {
        if (!res) {
            return;
        }
        if (res.ai_enabled !== undefined) {
            this.state.aiEnabled = !!res.ai_enabled;
        }
        if (res.ai_allow_user_choice !== undefined) {
            this.state.aiAllowUserChoice = !!res.ai_allow_user_choice;
        }
        if (res.ai_mode) {
            this.state.aiMode = res.ai_mode;
        }
        if (Array.isArray(res.ai_modes) && res.ai_modes.length) {
            this.state.aiModes = res.ai_modes;
        }
    }

    _scrollAiChat() {
        requestAnimationFrame(() => {
            const el = this.rootRef?.el?.querySelector?.(".merka-ai-chat-messages");
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        });
    }

    async onAiModeChange(ev) {
        const mode = ev.target.value;
        if (!mode || mode === this.state.aiMode || this.state.aiBusy) {
            return;
        }
        this.state.aiBusy = true;
        try {
            const res = await this.orm.call("merka.dashboard", "action_ai_set_mode", [
                this.state.dashboardId,
                mode,
            ]);
            this._applyAiModePayload(res);
            if (!res?.ok) {
                this.notification.add(res?.error || "Mode IA impossible", { type: "warning" });
                return;
            }
            this.notification.add(`Mode IA : ${this.aiModeLabel}`, { type: "info" });
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.aiBusy = false;
        }
    }

    async onOpenAiChat() {
        this.state.aiChatOpen = true;
        this.state.aiBusy = true;
        try {
            const res = await this.orm.call("merka.dashboard", "action_ai_chat_open", [
                this.state.dashboardId,
            ]);
            this.state.aiThreadId = res.thread_id;
            this.state.aiMessages = res.messages || [];
            this.state.aiSuggestions = res.suggestions || [];
            this._applyAiModePayload(res);
            this._scrollAiChat();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        } finally {
            this.state.aiBusy = false;
        }
    }

    onCloseAiChat() {
        this.state.aiChatOpen = false;
    }

    onCloseAiPanel() {
        this.state.aiPanelOpen = false;
    }

    onAiDraftInput(ev) {
        this.state.aiDraft = ev.target.value || "";
    }

    onAiDraftKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.onAiChatSend();
        }
    }

    onAiSuggestion(text) {
        this.state.aiDraft = text || "";
        this.onAiChatSend();
    }

    async onAiChatSend() {
        const text = (this.state.aiDraft || "").trim();
        if (!text || this.state.aiBusy) {
            return;
        }
        this.state.aiDraft = "";
        this.state.aiBusy = true;
        // Optimistic user bubble
        this.state.aiMessages = [
            ...this.state.aiMessages,
            { id: `tmp-u-${Date.now()}`, role: "user", body: text, actions: [] },
        ];
        this._scrollAiChat();
        try {
            const res = await this.orm.call("merka.dashboard", "action_ai_chat", [
                this.state.dashboardId,
                text,
                this.state.aiThreadId || false,
            ]);
            if (!res?.ok) {
                this.notification.add(res?.error || "Chat impossible", { type: "warning" });
                return;
            }
            this.state.aiThreadId = res.thread_id;
            if (res.assistant_message) {
                this.state.aiMessages = [...this.state.aiMessages, res.assistant_message];
            }
            if (res.suggestions) {
                this.state.aiSuggestions = res.suggestions;
            }
            this._applyAiModePayload(res);
            await this._applyAiSideEffects(res.side_effects || {});
            this._scrollAiChat();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.aiBusy = false;
        }
    }

    async _applyAiSideEffects(side) {
        if (!side) {
            return;
        }
        if (side.date_filter) {
            this.state.dateFilter = side.date_filter;
            await this.loadDashboard();
        }
        if (side.reload) {
            await this.loadDashboard();
        }
        if (side.open_item_id) {
            const action = await this.orm.call("merka.dashboard", "action_ai_open_item", [
                this.state.dashboardId,
                side.open_item_id,
            ]);
            await this._safeDoAction(action);
        }
    }

    async onAiChatClear() {
        this.state.aiBusy = true;
        try {
            const res = await this.orm.call("merka.dashboard", "action_ai_chat_clear", [
                this.state.dashboardId,
            ]);
            this.state.aiThreadId = res.thread_id;
            this.state.aiMessages = res.messages || [];
            this.state.aiSuggestions = res.suggestions || [];
            this._applyAiModePayload(res);
            this._scrollAiChat();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        } finally {
            this.state.aiBusy = false;
        }
    }

    async onExplain(itemId) {
        // Ouvre le chat et demande l'explication du KPI
        const item = (this.state.items || []).find((i) => i.id === itemId);
        const name = item?.name || String(itemId);
        await this.onOpenAiChat();
        this.state.aiDraft = `explique ${name}`;
        await this.onAiChatSend();
    }

    /** Toolbar IA → discussion */
    onAiGenerate() {
        this.onOpenAiChat();
    }

    async onAiPanelAction(act) {
        if (!act || this.state.aiBusy) {
            return;
        }
        if (act.type === "chat_preset" && act.text) {
            this.state.aiDraft = act.text;
            await this.onAiChatSend();
            return;
        }
        this.state.aiBusy = true;
        try {
            if (act.type === "filter" && act.date_filter) {
                this.state.dateFilter = act.date_filter;
                await this.loadDashboard();
                this.notification.add(`Filtre : ${act.date_filter}`, { type: "info" });
            } else if (act.type === "backfill") {
                const res = await this.orm.call("merka.dashboard", "action_ai_backfill_history", [
                    this.state.dashboardId,
                    14,
                ]);
                this.notification.add(
                    `Historique : +${res.created || 0} / ${res.days || 14}j`,
                    { type: "success" }
                );
                await this.loadDashboard();
                this.state.aiDraft = "Briefing";
                await this.onAiChatSend();
            } else if (act.type === "open_item" && act.item_id) {
                const action = await this.orm.call("merka.dashboard", "action_ai_open_item", [
                    this.state.dashboardId,
                    act.item_id,
                ]);
                await this._safeDoAction(action);
            } else if (act.type === "create_alert" && act.item_id) {
                const res = await this.orm.call("merka.dashboard", "action_ai_create_alert", [
                    this.state.dashboardId,
                    act.item_id,
                ]);
                if (res?.ok) {
                    this.notification.add(
                        `Alerte créée : ${res.name} (${res.operator} ${res.threshold})`,
                        { type: "success" }
                    );
                } else {
                    this.notification.add(res?.error || "Alerte impossible", { type: "warning" });
                }
            } else if (act.type === "open_records" && act.item_id) {
                await this.onOpenRecords(act.item_id);
            }
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        } finally {
            this.state.aiBusy = false;
        }
    }

    onToggleRtl() {
        this.state.rtl = !this.state.rtl;
    }

    async onOpenChat(itemId) {
        try {
            const action = await this.orm.call("merka.dashboard.item", "action_open_chat", [
                itemId,
            ]);
            await this._safeDoAction(action);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        }
    }

    async onQuickChat(itemId) {
        const body = window.prompt("Commentaire Discuss sur cet indicateur :");
        if (!body || !body.trim()) {
            return;
        }
        try {
            await this.orm.call("merka.dashboard.item", "action_post_chat_message", [
                itemId,
                body.trim(),
            ]);
            this.notification.add("Message publié", { type: "success" });
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "warning" });
        }
    }

    listColumns(item) {
        const records = item.data?.records || [];
        if (!records.length) {
            return [];
        }
        return Object.keys(records[0])
            .filter((k) => !["id", "display_name"].includes(k))
            .slice(0, 5);
    }

    cellValue(rec, col) {
        const v = rec[col];
        if (Array.isArray(v)) {
            return v[1] || v[0];
        }
        return v === false || v === null ? "" : v;
    }

    gaugeStyle(item) {
        const pct = this.progressPct(item);
        return `stroke-dasharray: ${pct} ${100 - pct}`;
    }
}

registry.category("actions").add("merka_dashboard_action", MerkaDashboardAction);
