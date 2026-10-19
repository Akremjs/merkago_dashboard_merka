# -*- coding: utf-8 -*-
{
    'name': 'Merka BI — Analytics for Odoo',
    'version': '20.0.2.7.0',
    'category': 'Productivity/Dashboard',
    'summary': 'BI self-service: KPI, charts, pivot, multi-engine AI chat, TV, alerts, formulas',
    'description': """
Merka BI (Merkago Dashboard Merka)
=================================
Produit BI self-service pour Odoo :
- 17+ visualisations (tuiles, flower, polar, pivot heatmap, waterfall…)
- Filtres croisés, bookmarks, themes, refresh Live, layout drag & drop
- Formules KPI, SQL, alertes, PDF/Excel, mode TV / Story
- Chat IA multi-moteur (Local / OpenAI / Azure / Custom), choix utilisateur, insights, streaming, RTL
""",
    'author': 'AKREM.KHELIFI',
    'website': 'https://www.merkago.net',
    'support': 'akremkhelifi07@gmail.com',
    'license': 'OPL-1',
    'price': 260.0,
    'currency': 'USD',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        'security/merka_dashboard_security.xml',
        'security/ir.model.access.csv',
        'data/merka_dashboard_config_data.xml',
        'data/merka_dashboard_kpi_data.xml',
        'data/ir_cron_data.xml',
        'views/merka_dashboard_views.xml',
        'views/merka_dashboard_item_views.xml',
        'views/merka_dashboard_kpi_views.xml',
        'views/merka_dashboard_config_views.xml',
        'views/merka_dashboard_alert_views.xml',
        'views/merka_dashboard_pack_actions.xml',
        'wizards/dashboard_setup_wizard_views.xml',
        'wizards/dashboard_export_wizard_views.xml',
        'wizards/dashboard_import_wizard_views.xml',
        'wizards/dashboard_report_wizard_views.xml',
        'wizards/dashboard_kpi_wizard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'merkago_dashboard_merka/static/src/scss/dashboard.scss',
            'merkago_dashboard_merka/static/src/js/dashboard_action.js',
            'merkago_dashboard_merka/static/src/js/reports_action.js',
            'merkago_dashboard_merka/static/src/xml/dashboard_templates.xml',
            'merkago_dashboard_merka/static/src/xml/reports_templates.xml',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
    'post_init_hook': 'hooks.post_init_hook',
}
