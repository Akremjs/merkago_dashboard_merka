/** Merka BI — build Odoo 19.0 */
/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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

function formatDate(iso) {
    if (!iso) {
        return "";
    }
    try {
        return new Date(iso).toLocaleString("fr-FR");
    } catch {
        return String(iso);
    }
}

export class MerkaReportsAction extends Component {
    static template = "merkago_dashboard_merka.ReportsHub";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            cards: [],
            recentExports: [],
            schedules: [],
            packFilter: false,
            generatedAt: null,
        });
        onWillStart(() => this.loadHub());
    }

    get formatNumber() {
        return formatNumber;
    }

    get formatDate() {
        return formatDate;
    }

    get packFilters() {
        const set = new Set((this.state.cards || []).map((c) => c.pack_code).filter(Boolean));
        return [...set].sort();
    }

    get filteredCards() {
        if (!this.state.packFilter) {
            return this.state.cards;
        }
        return this.state.cards.filter((c) => c.pack_code === this.state.packFilter);
    }

    async loadHub() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call("merka.dashboard", "get_reports_hub_payload", []);
            this.state.cards = payload.cards || [];
            this.state.recentExports = payload.recent_exports || [];
            this.state.schedules = payload.schedules || [];
            this.state.generatedAt = payload.generated_at
                ? formatDate(payload.generated_at)
                : null;
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    onFilterPack(pack) {
        this.state.packFilter = pack || false;
    }

    async onRefresh() {
        await this.loadHub();
        this.notification.add("Rapports actualisés", { type: "success" });
    }

    onOpenDash(id) {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "merka_dashboard_action",
            name: "Dashboard Merka",
            target: "current",
            params: { dashboard_id: id },
            context: { dashboard_id: id },
        });
    }

    async onDownloadHtml(id) {
        try {
            const res = await this.orm.call("merka.dashboard", "action_download_report", [id, "last_30"]);
            if (res?.url) {
                window.location = res.url;
                this.notification.add("Rapport HTML téléchargé", { type: "success" });
                await this.loadHub();
            }
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
    }

    async onDownloadCsv(id) {
        try {
            const res = await this.orm.call("merka.dashboard", "action_export_report_csv", [id, "last_30"]);
            if (res?.content) {
                const blob = new Blob([res.content], { type: "text/csv" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = res.filename || "rapport.csv";
                a.click();
                URL.revokeObjectURL(url);
            } else if (res?.url) {
                window.location = res.url;
            }
            this.notification.add("CSV téléchargé", { type: "success" });
            await this.loadHub();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
    }

    onWizard(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Générer un rapport",
            res_model: "merka.dashboard.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { default_dashboard_id: id },
        });
    }

    onOpenDashboards() {
        this.action.doAction("merkago_dashboard_merka.action_merka_dashboard");
    }

    onOpenExports() {
        this.action.doAction("merkago_dashboard_merka.action_merka_dashboard_export");
    }

    onOpenSchedules() {
        this.action.doAction("merkago_dashboard_merka.action_merka_dashboard_schedule");
    }

    async onBackSales() {
        const id = await this.orm.call("merka.dashboard", "ensure_pack_dashboard_id", ["sales"]);
        this.onOpenDash(id);
    }
}

registry.category("actions").add("merka_reports_action", MerkaReportsAction);
