# -*- coding: utf-8 -*-
import base64
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)



class MerkaDashboard(models.Model):
    _name = 'merka.dashboard'
    _description = 'Merkago Dashboard'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=False,
        index=True,
        help='Vide = visible dans toutes les sociétés.',
    )
    menu_id = fields.Many2one('ir.ui.menu', string='Menu', copy=False, ondelete='set null')
    menu_action_id = fields.Many2one(
        'ir.actions.server',
        string='Action menu',
        copy=False,
        ondelete='set null',
    )
    item_ids = fields.One2many('merka.dashboard.item', 'dashboard_id', string='Éléments')
    item_count = fields.Integer(compute='_compute_item_count')
    alert_ids = fields.One2many('merka.dashboard.alert', 'dashboard_id', string='Alertes')
    schedule_ids = fields.One2many('merka.dashboard.schedule', 'dashboard_id', string='Envois planifiés')
    group_ids = fields.Many2many(
        'res.groups',
        'merka_dashboard_group_rel',
        'dashboard_id',
        'group_id',
        string='Groupes autorisés',
        help='Si vide : accessible aux groupes User et Administrator.',
    )
    user_ids = fields.Many2many(
        'res.users',
        'merka_dashboard_user_rel',
        'dashboard_id',
        'user_id',
        string='Utilisateurs restreints',
        help='Utilisé pour le groupe Restricted.',
    )
    pack_code = fields.Selection(
        [
            ('custom', 'Personnalisé'),
            ('direction', 'Direction'),
            ('sales', 'Ventes'),
            ('crm', 'CRM'),
            ('purchase', 'Achats'),
            ('accounting', 'Comptabilité'),
            ('inventory', 'Inventaire'),
            ('pos', 'POS'),
            ('website', 'Site web'),
            ('hr', 'RH'),
            ('project', 'Projets'),
            ('manufacturing', 'Fabrication'),
            ('helpdesk', 'Helpdesk'),
        ],
        default='custom',
        required=True,
    )
    is_favorite = fields.Boolean(string='Favori', default=False)
    color = fields.Integer(string='Couleur')
    theme_override = fields.Selection(
        [
            ('auto', 'Selon config'),
            ('dark', 'Sombre'),
            ('light', 'Clair'),
            ('ocean', 'Océan'),
            ('contrast', 'Contraste'),
        ],
        string='Thème',
        default='auto',
    )

    @api.depends('item_ids')
    def _compute_item_count(self):
        for dashboard in self:
            dashboard.item_count = len(dashboard.item_ids)

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'merka_dashboard_action',
            'name': self.name,
            'target': 'current',
            'params': {'dashboard_id': self.id, 'tv_mode': False},
            'context': {'dashboard_id': self.id},
        }

    @api.model
    def action_open_setup_wizard(self):
        """Création via assistant (depuis Tous les tableaux)."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Créer un tableau',
            'res_model': 'merka.dashboard.setup.wizard',
            'view_mode': 'form',
            'target': 'new',
            'views': [(False, 'form')],
        }

    def _remove_backend_menu(self):
        """Supprime les sous-menus Odoo des dashboards (nav = sidebar OWL)."""
        for dash in self:
            menu = dash.menu_id
            action = dash.menu_action_id
            dash.with_context(merka_skip_menu_sync=True).write({
                'menu_id': False,
                'menu_action_id': False,
            })
            if menu:
                menu.unlink()
            if action:
                action.unlink()

    def _sync_backend_menu(self):
        """Ancien sync désactivé : on nettoie plutôt les menus dynamiques."""
        self._remove_backend_menu()

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    def unlink(self):
        self._remove_backend_menu()
        return super().unlink()

    @api.model
    def sync_all_menus(self):
        """Supprime tous les sous-menus dashboard (garde le menu app + utilitaires)."""
        self.search([])._remove_backend_menu()
        return True

    @api.model
    def _pack_titles(self):
        return {
            'direction': 'Dashboard Direction',
            'sales': 'Dashboard Ventes',
            'crm': 'Dashboard CRM',
            'purchase': 'Dashboard Achats',
            'accounting': 'Dashboard Comptabilité',
            'inventory': 'Dashboard Inventaire',
            'pos': 'Dashboard POS',
            'website': 'Dashboard Site web',
            'hr': 'Dashboard RH',
            'project': 'Dashboard Projets',
            'manufacturing': 'Dashboard Fabrication',
            'helpdesk': 'Dashboard Helpdesk',
        }

    @api.model
    def _pack_module_map(self):
        """Pack Merka → modules Odoo qui l'activent (au moins un installé)."""
        return {
            # Direction : toujours disponible (consolide les packs installés)
            'direction': ['base'],
            'sales': ['sale_management', 'sale'],
            'crm': ['crm'],
            'purchase': ['purchase', 'purchase_stock'],
            'accounting': ['account', 'account_accountant'],
            'inventory': ['stock'],
            'pos': ['point_of_sale'],
            'hr': ['hr'],
            'website': ['website', 'website_sale'],
            'project': ['project'],
            'manufacturing': ['mrp'],
            'helpdesk': ['helpdesk'],
        }

    @api.model
    def _pack_model_hints(self):
        """Modèle métier attendu pour confirmer que le pack a des données utilisables."""
        return {
            'direction': 'res.users',
            'sales': 'sale.order',
            'crm': 'crm.lead',
            'purchase': 'purchase.order',
            'accounting': 'account.move',
            'inventory': 'stock.quant',
            'pos': 'pos.order',
            'hr': 'hr.employee',
            'website': 'website',
            'project': 'project.project',
            'manufacturing': 'mrp.production',
            'helpdesk': 'helpdesk.ticket',
        }

    @api.model
    def _sidebar_pack_defs(self):
        """Entrées sidebar type Power BI (libellés courts + icônes)."""
        return [
            {'code': 'direction', 'label': 'Direction', 'icon': 'fa-briefcase'},
            {'code': 'sales', 'label': 'Ventes', 'icon': 'fa-shopping-cart'},
            {'code': 'crm', 'label': 'CRM', 'icon': 'fa-handshake-o'},
            {'code': 'inventory', 'label': 'Stock', 'icon': 'fa-cubes'},
            {'code': 'purchase', 'label': 'Achats', 'icon': 'fa-truck'},
            {'code': 'accounting', 'label': 'Comptabilité', 'icon': 'fa-calculator'},
            {'code': 'pos', 'label': 'POS', 'icon': 'fa-desktop'},
            {'code': 'hr', 'label': 'Employés', 'icon': 'fa-users'},
            {'code': 'website', 'label': 'Site web', 'icon': 'fa-globe'},
            {'code': 'project', 'label': 'Projets', 'icon': 'fa-tasks'},
            {'code': 'manufacturing', 'label': 'Fabrication', 'icon': 'fa-cogs'},
            {'code': 'helpdesk', 'label': 'Helpdesk', 'icon': 'fa-life-ring'},
        ]

    @api.model
    def _installed_module_names(self):
        return set(
            self.env['ir.module.module'].sudo().search([
                ('state', '=', 'installed'),
            ]).mapped('name')
        )

    @api.model
    def detect_available_packs(self, only_modules=None):
        """
        Détecte les packs Merka disponibles selon les apps Odoo installées.
        :param only_modules: si fourni, ne considère que les packs liés à ces modules
        :return: [{'code', 'label', 'modules', 'model'}]
        """
        installed = self._installed_module_names()
        if only_modules:
            only = set(only_modules)
            # Ne traiter que si au moins un module de only est installé
            if not (only & installed):
                return []
        results = []
        titles = self._pack_titles()
        hints = self._pack_model_hints()
        for code, modules in self._pack_module_map().items():
            if only_modules and not (set(modules) & set(only_modules)):
                continue
            hit = [m for m in modules if m in installed]
            if not hit:
                continue
            model_name = hints.get(code)
            if model_name and model_name not in self.env:
                # Module technique présent mais modèle pas encore chargé
                continue
            results.append({
                'code': code,
                'label': titles.get(code, code),
                'modules': hit,
                'model': model_name,
            })
        return results

    @api.model
    def _ensure_direction_items(self, dash, force=False):
        """Consolide les tuiles clés des packs installés sur le dashboard Direction."""
        if not dash:
            return
        if dash.item_ids and not force:
            return
        if force and dash.item_ids:
            dash.item_ids.unlink()
        Item = self.env['merka.dashboard.item']
        # Reprendre jusqu'à 8 tuiles KPI des autres dashboards packs
        seq = 10
        seen = set()
        for pack in self.detect_available_packs():
            code = pack['code']
            if code == 'direction':
                continue
            src = self.search([('pack_code', '=', code), ('active', '=', True)], limit=1)
            if not src:
                continue
            for tile in src.item_ids.filtered(lambda i: i.item_type == 'tile' and i.active)[:2]:
                key = (tile.model_name, tile.code or tile.name)
                if key in seen:
                    continue
                seen.add(key)
                Item.create({
                    'dashboard_id': dash.id,
                    'name': '%s · %s' % (pack['label'], tile.name),
                    'code': tile.code or False,
                    'item_type': 'tile',
                    'data_source': tile.data_source,
                    'model_id': tile.model_id.id if tile.model_id else False,
                    'measure_field_id': tile.measure_field_id.id if tile.measure_field_id else False,
                    'date_field_id': tile.date_field_id.id if tile.date_field_id else False,
                    'aggregation': tile.aggregation,
                    'domain': tile.domain or '[]',
                    'date_filter': tile.date_filter or 'last_30',
                    'unit_label': tile.unit_label or False,
                    'kpi_id': tile.kpi_id.id if tile.kpi_id else False,
                    'formula': tile.formula or False,
                    'sequence': seq,
                    'layout_w': 3,
                    'note': _('Vue Direction'),
                })
                seq += 10
                if seq > 80:
                    return

    @api.model
    def _ensure_pack_items(self, dash, pack_code, force=False):
        """Crée les widgets du pack si absents ; complète avec le dictionnaire KPI."""
        if not dash:
            return
        if pack_code == 'direction':
            self._ensure_direction_items(dash, force=force)
            return
        Kpi = self.env['merka.dashboard.kpi']
        kpis = Kpi.search([
            ('pack_code', '=', pack_code),
            ('active', '=', True),
        ])
        if dash.item_ids and not force:
            if kpis:
                kpis._apply_to_dashboards()
                Kpi._dedupe_dashboard_tiles([pack_code])
            return
        if force and dash.item_ids:
            dash.item_ids.unlink()
        # Priorité au catalogue KPI (évite les doublons wizard + seed)
        if kpis:
            kpis._apply_to_dashboards()
        if not dash.item_ids:
            wiz_sel = dict(self.env['merka.dashboard.setup.wizard']._fields['pack_code'].selection)
            wiz = self.env['merka.dashboard.setup.wizard'].create({
                'name': dash.name,
                'pack_code': pack_code if pack_code in wiz_sel else 'custom',
                'company_id': False,
            })
            wiz._create_pack_items(dash)
            if kpis:
                kpis._apply_to_dashboards()
        Kpi._dedupe_dashboard_tiles([pack_code])

    @api.model
    def auto_setup_from_installed_modules(self, only_modules=None, force_recreate_items=False):
        """
        Crée automatiquement :
        - les KPI du dictionnaire (selon apps installées)
        - les dashboards packs
        - les indicateurs (widgets) sur chaque dashboard
        """
        config = self.env['merka.dashboard.config'].sudo().get_config()
        if not config.auto_detect_modules and not self.env.context.get('merka_force_auto_setup'):
            return {'created': [], 'existing': [], 'skipped': True}

        available = self.detect_available_packs(only_modules=only_modules)
        pack_codes = [p['code'] for p in available]

        # 1) Dictionnaire KPI
        kpi_result = {'created': [], 'updated': [], 'skipped': []}
        Kpi = self.env['merka.dashboard.kpi'].sudo()
        try:
            kpi_result = Kpi.auto_seed_kpis(pack_codes)
        except Exception as exc:
            _logger = __import__('logging').getLogger(__name__)
            _logger.exception('Merka KPI seed failed: %s', exc)

        # 2) Dashboards + items
        created, existing, errors = [], [], []
        for pack in available:
            code = pack['code']
            try:
                dash = self.search([
                    ('pack_code', '=', code),
                    ('active', '=', True),
                ], order='id', limit=1)
                if dash:
                    self._ensure_pack_items(dash, code, force=force_recreate_items and not dash.item_ids)
                    if force_recreate_items and not dash.item_ids:
                        self._ensure_pack_items(dash, code, force=True)
                    existing.append(code)
                else:
                    dash = self.get_or_create_pack_dashboard(code)
                    self._ensure_pack_items(dash, code, force=not bool(dash.item_ids))
                    created.append({
                        'code': code,
                        'id': dash.id,
                        'name': dash.name,
                        'items': len(dash.item_ids),
                        'modules': pack['modules'],
                    })
            except Exception as exc:
                errors.append({'code': code, 'error': str(exc)})

        # 3) Nettoyage doublons tuiles (pack wizard + seed KPI)
        try:
            Kpi._dedupe_dashboard_tiles(pack_codes)
        except Exception as exc:
            _logger = __import__('logging').getLogger(__name__)
            _logger.exception('Merka KPI dedupe failed: %s', exc)

        note = _(
            'Auto-setup Merka : dashboards créés=%(c)s, existants=%(e)s, '
            'KPI créés=%(kc)s, maj=%(ku)s, erreurs=%(err)s'
        ) % {
            'c': len(created),
            'e': len(existing),
            'kc': len(kpi_result.get('created') or []),
            'ku': len(kpi_result.get('updated') or []),
            'err': len(errors),
        }
        try:
            self.env['merka.dashboard.export'].sudo().create({
                'name': note,
                'export_type': 'json',
                'note': str({
                    'created': created,
                    'existing': existing,
                    'errors': errors,
                    'detected': available,
                    'kpis': kpi_result,
                }),
            })
        except Exception:
            pass

        self.sync_all_menus()
        try:
            config.last_auto_setup = fields.Datetime.now()
        except Exception:
            pass
        return {
            'created': created,
            'existing': existing,
            'errors': errors,
            'detected': available,
            'kpis': kpi_result,
        }

    @api.model
    def action_resync_packs(self):
        """Action manuelle : rescanner apps + KPI + dashboards."""
        result = self.with_context(merka_force_auto_setup=True).auto_setup_from_installed_modules(
            force_recreate_items=True,
        )
        created = result.get('created') or []
        kpis = result.get('kpis') or {}
        msg = _(
            '%(n)s dashboard(s) créé(s), %(e)s déjà présents. '
            'KPI : %(kc)s créés / %(ku)s mis à jour. Apps : %(d)s.'
        ) % {
            'n': len(created),
            'e': len(result.get('existing') or []),
            'kc': len(kpis.get('created') or []),
            'ku': len(kpis.get('updated') or []),
            'd': ', '.join(p['code'] for p in (result.get('detected') or [])) or '—',
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synchronisation packs + KPI Merka'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def get_sidebar_nav(self, current_id=None):
        """Sidebar : uniquement les packs dont l'app Odoo est installée (+ tableaux custom)."""
        available_codes = {p['code'] for p in self.detect_available_packs()}
        packs = [p for p in self._sidebar_pack_defs() if p['code'] in available_codes]
        nav = []
        seen_ids = set()
        for pack in packs:
            dash = self.search([
                ('pack_code', '=', pack['code']),
                ('active', '=', True),
            ], order='sequence, id', limit=1)
            if not dash:
                nav.append({
                    'id': False,
                    'pack_code': pack['code'],
                    'name': pack['label'],
                    'icon': pack['icon'],
                    'active': False,
                    'ensure_pack': True,
                })
                continue
            seen_ids.add(dash.id)
            nav.append({
                'id': dash.id,
                'pack_code': pack['code'],
                'name': pack['label'],
                'icon': pack['icon'],
                'active': bool(current_id and dash.id == current_id),
                'ensure_pack': False,
            })
        extras = self.search([
            ('active', '=', True),
            ('id', 'not in', list(seen_ids) or [0]),
        ], order='sequence, name')
        for dash in extras:
            # Masquer les packs d'apps non installées
            if dash.pack_code and dash.pack_code != 'custom' and dash.pack_code not in available_codes:
                continue
            nav.append({
                'id': dash.id,
                'pack_code': dash.pack_code or 'custom',
                'name': dash.name,
                'icon': 'fa-th-large',
                'active': bool(current_id and dash.id == current_id),
                'ensure_pack': False,
            })
        if current_id and not any(n.get('active') for n in nav):
            for n in nav:
                if n.get('id') == current_id:
                    n['active'] = True
        return nav

    @api.model
    def get_or_create_pack_dashboard(self, pack_code):
        """Retourne le tableau canonique d'un module (ex. Dashboard Ventes)."""
        titles = self._pack_titles()
        if pack_code not in titles:
            pack_code = 'sales'
        title = titles[pack_code]
        dashboard = self.search([
            ('name', '=', title),
            ('pack_code', '=', pack_code),
            ('active', '=', True),
        ], limit=1)
        if dashboard:
            self._ensure_pack_items(dashboard, pack_code, force=False)
            return dashboard

        wiz_selection = dict(self.env['merka.dashboard.setup.wizard']._fields['pack_code'].selection)
        wiz_pack = pack_code if pack_code in wiz_selection else 'custom'
        wiz = self.env['merka.dashboard.setup.wizard'].create({
            'name': title,
            'pack_code': wiz_pack,
            'company_id': False,  # packs partagés toutes sociétés
        })
        action = wiz.action_create_dashboard()
        dash_id = (action.get('params') or {}).get('dashboard_id') or (action.get('context') or {}).get('dashboard_id')
        dashboard = self.browse(dash_id) if dash_id else False
        if not dashboard:
            dashboard = self.search([('pack_code', '=', pack_code)], order='id desc', limit=1)
        if dashboard:
            dashboard.write({
                'name': title,
                'pack_code': pack_code,
                'is_favorite': True,
            })
            self._ensure_pack_items(dashboard, pack_code, force=not bool(dashboard.item_ids))
        return dashboard

    @api.model
    def action_open_pack_dashboard(self):
        """Action menu : ouvre le dashboard du module (context merka_pack_code)."""
        pack = self.env.context.get('merka_pack_code') or 'sales'
        available = {p['code'] for p in self.detect_available_packs()}
        if pack not in available:
            # Fallback : premier pack réellement installé
            order = [p['code'] for p in self._sidebar_pack_defs()]
            pack = next((c for c in order if c in available), None)
            if not pack:
                # Aucune app métier : hub rapports / liste
                return self.action_open_reports_hub()
        dashboard = self.get_or_create_pack_dashboard(pack)
        return dashboard.action_open_dashboard()

    @api.model
    def action_open_home_dashboard(self):
        """Entrée app : favori utilisateur, sinon premier pack détecté."""
        home = self.env.user.merka_home_dashboard_id
        if home and home.active:
            return home.action_open_dashboard()
        fav = self.search([('is_favorite', '=', True), ('active', '=', True)], limit=1)
        if fav:
            return fav.action_open_dashboard()
        return self.with_context(merka_pack_code=False).action_open_pack_dashboard()

    @api.model
    def resolve_default_dashboard_id(self):
        """
        Id du dashboard à ouvrir (refresh navigateur / action sans params).
        Ordre : accueil user → favori → 1er pack installé → 1er tableau actif.
        """
        home = self.env.user.merka_home_dashboard_id
        if home and home.exists() and home.active:
            return home.id
        fav = self.search([('is_favorite', '=', True), ('active', '=', True)], order='sequence, id', limit=1)
        if fav:
            return fav.id
        available = self.detect_available_packs()
        if available:
            order = [p['code'] for p in self._sidebar_pack_defs()]
            codes = {p['code'] for p in available}
            pack = next((c for c in order if c in codes), available[0]['code'])
            return self.get_or_create_pack_dashboard(pack).id
        any_dash = self.search([('active', '=', True)], order='sequence, id', limit=1)
        return any_dash.id if any_dash else False

    @api.model
    def ensure_pack_dashboard_id(self, pack_code):
        """Retourne l'id du dashboard pack (création à la volée si besoin)."""
        return self.get_or_create_pack_dashboard(pack_code).id

    @api.model
    def action_open_reports_hub(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'merka_reports_action',
            'name': _('Rapports Merka'),
            'target': 'current',
        }

    def action_open_report_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Générer un rapport'),
            'res_model': 'merka.dashboard.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_dashboard_id': self.id},
        }

    @api.model
    def get_reports_hub_payload(self):
        """Données pour le hub Rapports (sidebar)."""
        dashes = self.search([('active', '=', True)], order='sequence, name')
        cards = []
        for dash in dashes:
            tiles = []
            for item in dash.item_ids.filtered(
                lambda i: i.active and i.item_type == 'tile'
            ).sorted('sequence')[:4]:
                try:
                    data = self.env['merka.dashboard.item'].get_item_data(item.id)
                    tiles.append({
                        'id': item.id,
                        'name': item.name,
                        'value': data.get('value'),
                        'unit': data.get('unit') or '',
                        'trend': data.get('trend'),
                    })
                except Exception:
                    tiles.append({
                        'id': item.id,
                        'name': item.name,
                        'value': '—',
                        'unit': '',
                        'trend': None,
                    })
            last_export = self.env['merka.dashboard.export'].search(
                [('dashboard_id', '=', dash.id)], limit=1
            )
            cards.append({
                'id': dash.id,
                'name': dash.name,
                'pack_code': dash.pack_code,
                'item_count': len(dash.item_ids),
                'is_favorite': dash.is_favorite,
                'tiles': tiles,
                'last_export': last_export.create_date.isoformat() if last_export and last_export.create_date else False,
                'last_export_type': last_export.export_type if last_export else False,
            })
        exports = self.env['merka.dashboard.export'].search([], limit=12)
        recent = [{
            'id': e.id,
            'name': e.name,
            'dashboard': e.dashboard_id.name if e.dashboard_id else '—',
            'export_type': e.export_type,
            'date': e.create_date.isoformat() if e.create_date else False,
            'attachment_id': e.attachment_id.id if e.attachment_id else False,
        } for e in exports]
        schedules = self.env['merka.dashboard.schedule'].search([('active', '=', True)], limit=8)
        sched = [{
            'id': s.id,
            'name': s.name,
            'dashboard': s.dashboard_id.name,
            'interval': s.interval,
            'last_sent': s.last_sent.isoformat() if s.last_sent else False,
        } for s in schedules]
        return {
            'cards': cards,
            'recent_exports': recent,
            'schedules': sched,
            'generated_at': fields.Datetime.now().isoformat(),
        }

    def _build_report_html(self, global_date_filter=None, include_charts=True, include_lists=True):
        """Rapport HTML stylé (KPI + graphiques + listes)."""
        self.ensure_one()
        payload = self.get_dashboard_payload(global_date_filter=global_date_filter)
        now = datetime.now().strftime('%d/%m/%Y %H:%M')
        period = global_date_filter or 'tous'
        kpi_rows = []
        chart_blocks = []
        list_blocks = []
        for item in payload.get('items') or []:
            data = item.get('data') or {}
            itype = item.get('item_type') or data.get('type')
            if itype == 'tile' or data.get('type') == 'tile':
                trend = data.get('trend')
                trend_html = ''
                if trend is not None:
                    color = '#16a34a' if trend >= 0 else '#dc2626'
                    trend_html = f"<span style='color:{color};font-size:12px'>{trend:+.1f}%</span>"
                kpi_rows.append(
                    f"<div class='kpi'>"
                    f"<div class='kpi-label'>{item.get('name')}</div>"
                    f"<div class='kpi-value'>{data.get('value')} <small>{data.get('unit') or ''}</small></div>"
                    f"{trend_html}</div>"
                )
            elif include_charts and data.get('labels'):
                rows = ''.join(
                    "<tr><td>%s</td><td style='text-align:right'><b>%s</b></td></tr>" % (lbl, val)
                    for lbl, val in zip(data.get('labels') or [], data.get('values') or [])
                )
                empty_row = "<tr><td colspan='2'>Aucune donnée</td></tr>"
                chart_blocks.append(
                    "<div class='block'><h3>%s</h3><table>%s</table></div>" % (
                        item.get('name'),
                        rows or empty_row,
                    )
                )
            elif include_lists and itype == 'list':
                records = data.get('records') or []
                if not records:
                    continue
                keys = [k for k in records[0].keys() if k not in ('id',)][:4]
                head = ''.join("<th>%s</th>" % k for k in keys)
                body_rows = []
                for rec in records[:15]:
                    cells = []
                    for k in keys:
                        val = rec.get(k)
                        if isinstance(val, (list, tuple)):
                            val = val[1] if val else ''
                        cells.append("<td>%s</td>" % (val if val is not False and val is not None else ''))
                    body_rows.append("<tr>%s</tr>" % ''.join(cells))
                list_blocks.append(
                    "<div class='block'><h3>%s</h3><table><tr>%s</tr>%s</table></div>" % (
                        item.get('name'),
                        head,
                        ''.join(body_rows),
                    )
                )

        return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"/>
<title>Rapport {self.name}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#0B1220;color:#E2E8F0;margin:0;padding:24px}}
.header{{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:24px;
border-bottom:1px solid rgba(148,163,184,.25);padding-bottom:16px}}
.header h1{{margin:0;font-size:28px;color:#fff}}
.meta{{color:#94A3B8;font-size:13px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}}
.kpi{{background:linear-gradient(160deg,#151E2E,#1A2436);border:1px solid rgba(148,163,184,.2);
border-radius:12px;padding:14px 16px}}
.kpi-label{{color:#94A3B8;font-size:12px;font-weight:600}}
.kpi-value{{font-size:26px;font-weight:700;color:#fff;margin-top:6px}}
.kpi-value small{{font-size:13px;color:#94A3B8;font-weight:500}}
.block{{background:#151E2E;border:1px solid rgba(148,163,184,.2);border-radius:12px;padding:14px 16px;margin-bottom:14px}}
.block h3{{margin:0 0 10px;font-size:15px;color:#E2E8F0}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:8px 10px;border-bottom:1px solid rgba(148,163,184,.15);text-align:left}}
th{{color:#94A3B8;font-weight:600}}
.footer{{margin-top:28px;color:#64748B;font-size:11px;text-align:center}}
</style></head><body>
<div class="header">
  <div><div class="meta">Merkago · Rapport</div><h1>{self.name}</h1></div>
  <div class="meta">Période : {period}<br/>Généré le {now}</div>
</div>
<div class="kpis">{''.join(kpi_rows) or '<p class="meta">Aucun KPI</p>'}</div>
{''.join(chart_blocks)}
{''.join(list_blocks)}
<div class="footer">Merkago Dashboard Merka · {self.pack_code or 'custom'} · Confidentiel</div>
</body></html>"""

    def action_download_report(self, global_date_filter=None):
        """Génère et renvoie l'URL de téléchargement du rapport HTML."""
        self.ensure_one()
        html = self._build_report_html(global_date_filter=global_date_filter)
        attachment = self.env['ir.attachment'].create({
            'name': f"Rapport_{self.name}.html",
            'type': 'binary',
            'datas': base64.b64encode(html.encode('utf-8')),
            'mimetype': 'text/html',
            'res_model': 'merka.dashboard',
            'res_id': self.id,
        })
        self.env['merka.dashboard.export'].create({
            'name': _('Rapport %s') % self.name,
            'dashboard_id': self.id,
            'export_type': 'pdf',
            'attachment_id': attachment.id,
            'note': 'Hub rapports',
        })
        return {
            'attachment_id': attachment.id,
            'url': f'/web/content/{attachment.id}?download=true',
            'filename': attachment.name,
        }

    def action_export_report_csv(self, global_date_filter=None):
        """CSV consolidé de tous les KPI du tableau."""
        self.ensure_one()
        payload = self.get_dashboard_payload(global_date_filter=global_date_filter)
        lines = ['indicateur,type,valeur,unite,tendance']
        for item in payload.get('items') or []:
            data = item.get('data') or {}
            itype = item.get('item_type')
            if itype == 'tile' or data.get('type') == 'tile':
                name = (item.get('name') or '').replace(',', ' ')
                lines.append(
                    f"{name},tile,{data.get('value') or 0},{data.get('unit') or ''},{data.get('trend') or ''}"
                )
            elif data.get('labels'):
                for lbl, val in zip(data.get('labels') or [], data.get('values') or []):
                    safe = str(lbl).replace(',', ' ')
                    lines.append(f"{item.get('name')} / {safe},{itype},{val},,")
        content = '\n'.join(lines)
        attachment = self.env['ir.attachment'].create({
            'name': f"Rapport_{self.name}.csv",
            'type': 'binary',
            'datas': base64.b64encode(content.encode('utf-8')),
            'mimetype': 'text/csv',
            'res_model': 'merka.dashboard',
            'res_id': self.id,
        })
        self.env['merka.dashboard.export'].create({
            'name': _('CSV %s') % self.name,
            'dashboard_id': self.id,
            'export_type': 'csv',
            'attachment_id': attachment.id,
        })
        return {
            'attachment_id': attachment.id,
            'url': f'/web/content/{attachment.id}?download=true',
            'content': content,
            'filename': attachment.name,
        }

    def action_open_tv_mode(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'merka_dashboard_action',
            'name': self.name,
            'target': 'fullscreen',
            'params': {'dashboard_id': self.id, 'tv_mode': True},
            'context': {'dashboard_id': self.id, 'tv_mode': True},
        }

    def action_toggle_favorite(self):
        for rec in self:
            rec.is_favorite = not rec.is_favorite
        return True

    def action_set_as_home(self):
        """Définit ce dashboard comme accueil Merka de l'utilisateur courant."""
        self.ensure_one()
        self.env.user.sudo().write({'merka_home_dashboard_id': self.id})
        self.is_favorite = True
        return True

    def get_dashboard_payload(self, global_date_filter=None, date_from=None, date_to=None,
                              company_id=None, cross_filter=None):
        self.ensure_one()
        self.check_access_rights('read')
        self.check_access_rule('read')
        env = self.env
        if company_id:
            company = self.env['res.company'].browse(int(company_id))
            if company.exists():
                env = self.env(context=dict(self.env.context, allowed_company_ids=[company.id]))
                self = self.with_env(env)
        config = env['merka.dashboard.config'].get_config()
        settings = config.get_public_settings()
        theme = self.theme_override if self.theme_override and self.theme_override != 'auto' else (settings.get('theme') or 'dark')
        Item = env['merka.dashboard.item']
        # Normaliser cross_filter (dict JSON depuis le frontend)
        if cross_filter and not isinstance(cross_filter, dict):
            cross_filter = False
        items = []
        story_slides = []
        for item in self.item_ids.filtered('active').sorted(key=lambda i: (i.layout_y, i.layout_x, i.sequence)):
            try:
                data = Item.get_item_data(
                    item.id,
                    global_date_filter=global_date_filter,
                    date_from=date_from,
                    date_to=date_to,
                    cross_filter=cross_filter or None,
                )
            except Exception as exc:
                data = {
                    'type': item.item_type,
                    'value': 0,
                    'name': item.name,
                    'labels': [],
                    'values': [],
                    'error': str(exc),
                }
            items.append({
                'id': item.id,
                'name': item.name,
                'code': item.code or '',
                'note': item.note or '',
                'item_type': item.item_type,
                'model_name': item.model_name or '',
                'groupby': item.groupby_field_id.name if item.groupby_field_id else False,
                'layout_w': item.layout_w or (3 if item.item_type == 'tile' else 6),
                'layout_h': item.layout_h or 2,
                'layout_x': item.layout_x or 0,
                'layout_y': item.layout_y or 0,
                'sequence': item.sequence,
                'data': data,
            })
            if item.item_type in ('tile', 'bullet') or data.get('type') == 'tile':
                story_slides.append({
                    'id': item.id,
                    'title': item.name,
                    'value': data.get('value'),
                    'unit': data.get('unit') or '',
                    'trend': data.get('trend'),
                    'note': item.note or data.get('subtitle') or '',
                    'target': data.get('target'),
                    'progress_pct': data.get('progress_pct'),
                })
        companies = [
            {'id': c.id, 'name': c.name}
            for c in env['res.company'].search([])
        ]
        home_id = env.user.merka_home_dashboard_id.id if env.user.merka_home_dashboard_id else False
        lang = (env.user.lang or '').lower()
        rtl_langs = ('ar_', 'he_', 'fa_', 'ur_', 'yi_')
        auto_rtl = any(lang.startswith(p) for p in rtl_langs)
        return {
            'id': self.id,
            'name': self.name,
            'pack_code': self.pack_code,
            'is_favorite': self.is_favorite,
            'is_home': bool(home_id and home_id == self.id),
            'theme': theme,
            'refresh_seconds': settings.get('refresh_seconds') or 0,
            'ai_enabled': settings.get('ai_enabled'),
            'ai_multi_generate': settings.get('ai_multi_generate', True),
            'anomaly_threshold_pct': settings.get('anomaly_threshold_pct') or 15.0,
            'stream_enabled': settings.get('stream_enabled', True),
            'rtl': bool(settings.get('force_rtl') or auto_rtl),
            'lang': env.user.lang or 'fr_FR',
            'global_date_filter': global_date_filter or 'none',
            'date_from': date_from,
            'date_to': date_to,
            'company_id': company_id or env.company.id,
            'companies': companies,
            'items': items,
            'nav': self.get_sidebar_nav(current_id=self.id),
            'cross_filter': cross_filter or False,
            'story_slides': story_slides,
            'bookmarks': env['merka.dashboard.bookmark'].list_for_user(self.id),
        }

    def _notify_stream(self):
        """Push bus Odoo → clients en streaming rechargent le dashboard."""
        config = self.env['merka.dashboard.config'].get_config()
        if not config.stream_enabled:
            return
        for dash in self:
            try:
                self.env['bus.bus']._sendone(
                    f'merka.dashboard.{dash.id}',
                    'merka_dashboard_refresh',
                    {'dashboard_id': dash.id},
                )
            except Exception:
                _logger.debug('Merka stream notify failed for dashboard %s', dash.id, exc_info=True)

    @api.model
    def action_ping_stream(self, dashboard_id):
        """Heartbeat / forcer un refresh live côté clients."""
        dash = self.browse(int(dashboard_id))
        if dash.exists():
            dash._notify_stream()
        return {'ok': True}

    def action_open_kpi_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nouveau KPI'),
            'res_model': 'merka.dashboard.kpi.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_dashboard_id': self.id},
            'views': [(False, 'form')],
        }

    def save_layout(self, layouts):
        """Persiste layout_x/y/w depuis le mode édition frontend.

        layouts: [{id, layout_x, layout_y, layout_w, layout_h, sequence}]
        """
        self.ensure_one()
        self.check_access_rights('write')
        Item = self.env['merka.dashboard.item']
        for row in layouts or []:
            item = Item.browse(row.get('id'))
            if item.dashboard_id != self:
                continue
            item.write({
                'layout_x': int(row.get('layout_x') or 0),
                'layout_y': int(row.get('layout_y') or 0),
                'layout_w': int(row.get('layout_w') or 3),
                'layout_h': int(row.get('layout_h') or 2),
                'sequence': int(row.get('sequence') or item.sequence),
            })
        return True

    def export_item_csv(self, item_id, global_date_filter=None, date_from=None, date_to=None):
        self.ensure_one()
        Item = self.env['merka.dashboard.item']
        item = Item.browse(item_id)
        data = Item.get_item_data(
            item.id,
            global_date_filter=global_date_filter,
            date_from=date_from,
            date_to=date_to,
        )
        lines = ['label,value']
        if data.get('type') == 'list':
            lines = ['id,name']
            for rec in data.get('records') or []:
                name = (rec.get('display_name') or rec.get('name') or '').replace(',', ' ')
                lines.append(f"{rec.get('id')},{name}")
        elif data.get('type') == 'pivot':
            cols = data.get('cols') or []
            header = [(data.get('row_label') or 'ligne').replace(',', ' ')] + [
                str(c).replace(',', ' ') for c in cols
            ] + ['Total']
            lines = [','.join(header)]
            for i, row_label in enumerate(data.get('rows') or []):
                cells = (data.get('matrix') or [[]])[i] if i < len(data.get('matrix') or []) else []
                total = (data.get('row_totals') or [0])[i] if i < len(data.get('row_totals') or []) else 0
                line = [str(row_label).replace(',', ' ')] + [str(v) for v in cells] + [str(total)]
                lines.append(','.join(line))
            foot = ['Total'] + [str(v) for v in (data.get('col_totals') or [])] + [str(data.get('grand_total') or 0)]
            lines.append(','.join(foot))
        else:
            labels = data.get('labels') or [data.get('name') or item.name]
            values = data.get('values') or [data.get('value') or 0]
            for label, value in zip(labels, values):
                safe = str(label).replace(',', ' ')
                lines.append(f'{safe},{value}')
        return {
            'filename': f"{item.name or 'export'}.csv",
            'content': '\n'.join(lines),
            'mimetype': 'text/csv',
        }

    def export_dashboard_excel(self, global_date_filter=None, date_from=None, date_to=None):
        """Export Excel (SpreadsheetML) de tous les indicateurs du tableau."""
        self.ensure_one()
        payload = self.get_dashboard_payload(global_date_filter, date_from, date_to)
        rows = ['<?xml version="1.0"?><?mso-application progid="Excel.Sheet"?>']
        rows.append('<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"')
        rows.append(' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">')
        rows.append(f'<Worksheet ss:Name="{(self.name or "Merka")[:31].replace("/", "-")}"><Table>')
        rows.append('<Row><Cell><Data ss:Type="String">Indicateur</Data></Cell>'
                    '<Cell><Data ss:Type="String">Type</Data></Cell>'
                    '<Cell><Data ss:Type="String">Label</Data></Cell>'
                    '<Cell><Data ss:Type="String">Valeur</Data></Cell>'
                    '<Cell><Data ss:Type="String">Précédent</Data></Cell>'
                    '<Cell><Data ss:Type="String">Tendance %</Data></Cell></Row>')

        def _xml(s):
            return (str(s) if s is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        for item in payload.get('items') or []:
            data = item.get('data') or {}
            name = _xml(item.get('name'))
            itype = _xml(item.get('item_type'))
            if data.get('type') == 'list':
                for rec in data.get('records') or []:
                    rows.append(
                        f'<Row><Cell><Data ss:Type="String">{name}</Data></Cell>'
                        f'<Cell><Data ss:Type="String">{itype}</Data></Cell>'
                        f'<Cell><Data ss:Type="String">{_xml(rec.get("display_name") or rec.get("name"))}</Data></Cell>'
                        f'<Cell><Data ss:Type="String">{_xml(rec.get("id"))}</Data></Cell>'
                        f'<Cell><Data ss:Type="String"></Data></Cell>'
                        f'<Cell><Data ss:Type="String"></Data></Cell></Row>'
                    )
            else:
                labels = data.get('labels') or [item.get('name')]
                values = data.get('values') or [data.get('value') or 0]
                prev = data.get('previous')
                trend = data.get('trend')
                for label, value in zip(labels, values):
                    rows.append(
                        f'<Row><Cell><Data ss:Type="String">{name}</Data></Cell>'
                        f'<Cell><Data ss:Type="String">{itype}</Data></Cell>'
                        f'<Cell><Data ss:Type="String">{_xml(label)}</Data></Cell>'
                        f'<Cell><Data ss:Type="Number">{float(value or 0)}</Data></Cell>'
                        f'<Cell><Data ss:Type="String">{_xml("" if prev is None else prev)}</Data></Cell>'
                        f'<Cell><Data ss:Type="String">{_xml("" if trend is None else trend)}</Data></Cell></Row>'
                    )
        rows.append('</Table></Worksheet></Workbook>')
        content = '\n'.join(rows)
        self.env['merka.dashboard.export'].create({
            'name': _('Export Excel %s') % self.name,
            'dashboard_id': self.id,
            'export_type': 'excel',
            'note': 'SpreadsheetML',
        })
        return {
            'filename': f"{(self.name or 'merka').replace(' ', '_')}.xls",
            'content': content,
            'mimetype': 'application/vnd.ms-excel',
        }

    def _local_bi_insight(self, item, data):
        """Analyste BI local (sans API) : faits + conseil actionnable."""
        itype = data.get('type') or item.item_type
        advice = []
        if itype in ('tile', 'bullet'):
            trend = data.get('trend')
            target = data.get('target')
            value = data.get('value')
            unit = (data.get('unit') or '').strip()
            parts = [f"« {item.name} » = {value}{' ' + unit if unit else ''}."]
            if trend is not None:
                sens = 'hausse' if float(trend) >= 0 else 'baisse'
                parts.append(f"Tendance : {sens} de {abs(float(trend)):.1f} % vs période précédente.")
                if float(trend) <= -10:
                    advice.append("Priorité : investiguer la baisse (filtre période / équipe / canal).")
                elif float(trend) >= 15:
                    advice.append("Point fort : capitaliser sur ce qui marche (répliquer le levier).")
            if target:
                try:
                    pct = round(100.0 * float(value or 0) / float(target), 1)
                    parts.append(f"Objectif : {pct} % atteint (cible {target}).")
                    if pct < 70:
                        advice.append("Sous l'objectif : plan d'actions ou révision de la cible.")
                    elif pct >= 100:
                        advice.append("Objectif atteint — fixer une cible supérieure si pertinent.")
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
            anomaly = data.get('anomaly') or {}
            if anomaly.get('pct') is not None:
                parts.append(
                    f"⚠ Anomalie {anomaly.get('pct')} % vs moyenne 7j "
                    f"({anomaly.get('direction') or 'écart'})."
                )
                advice.append("Anomalie détectée : vérifier les données du jour et les filtres.")
            if value in (0, 0.0, None, '—') and not advice:
                advice.append("Valeur nulle : vérifier le domaine, la période ou les données source.")
            if advice:
                parts.append("Conseil : " + " ".join(advice[:2]))
            return " ".join(parts)

        labels = list(data.get('labels') or [])
        values = [float(v or 0) for v in (data.get('values') or [])]
        if not values:
            return f"« {item.name} » : aucune donnée sur la période. Conseil : élargir les filtres date."
        total = sum(values)
        pairs = sorted(zip(labels, values), key=lambda p: p[1], reverse=True)
        top3 = pairs[:3]
        bot_l, bot_v = pairs[-1]
        top_l, top_v = pairs[0]
        share = round(100.0 * top_v / total, 1) if total else 0
        top3_txt = ", ".join(
            f"{lab} ({round(val, 2)}, {round(100.0 * val / total, 1) if total else 0} %)"
            for lab, val in top3
        )
        parts = [
            f"« {item.name} » : {len(labels)} catégories, total {round(total, 2)}.",
            f"Top : {top3_txt}.",
            f"Plus bas : {bot_l} ({round(bot_v, 2)}).",
        ]
        if share >= 50:
            advice.append(f"Concentration forte sur « {top_l} » ({share} %) — surveiller la dépendance.")
        elif len(pairs) >= 3 and total:
            advice.append("Répartition relativement équilibrée — comparer aux objectifs par segment.")
        if bot_v == 0 and len(pairs) > 1:
            advice.append(f"« {bot_l} » à zéro : opportunité ou problème de couverture.")
        if advice:
            parts.append("Conseil : " + " ".join(advice[:2]))
        return " ".join(parts)

    def action_ai_dashboard_briefing(self, focus=None):
        """Briefing local du tableau entier (sans API). focus: downs|zeros|anomalies|who|None."""
        self.ensure_one()
        config = self.env['merka.dashboard.config'].get_config()
        threshold = config.anomaly_threshold_pct or 15.0
        health = self.env['merka.dashboard.history'].history_health(days=14)
        payload = self.get_dashboard_payload()
        tiles = []
        charts = []
        anomalies = []  # list of dicts
        zeros = []
        downs = []
        ups = []
        under_target = []
        for item in payload.get('items') or []:
            data = item.get('data') or {}
            itype = item.get('item_type') or data.get('type')
            name = item.get('name') or '?'
            iid = item.get('id')
            if itype in ('tile', 'bullet') or data.get('type') == 'tile':
                tiles.append({'id': iid, 'name': name, 'value': data.get('value'), 'trend': data.get('trend')})
                val = data.get('value')
                if val in (0, 0.0, None, '—'):
                    zeros.append({'id': iid, 'name': name})
                trend = data.get('trend')
                if trend is not None:
                    if float(trend) <= -10:
                        downs.append({'id': iid, 'name': name, 'trend': float(trend)})
                    elif float(trend) >= 15:
                        ups.append({'id': iid, 'name': name, 'trend': float(trend)})
                if data.get('anomaly'):
                    anomalies.append({
                        'id': iid,
                        'name': name,
                        'pct': data['anomaly'].get('pct'),
                        'value': data.get('value'),
                    })
                tgt = data.get('target')
                prog = data.get('progress_pct')
                if tgt and prog is not None and float(prog) < 70:
                    under_target.append({'id': iid, 'name': name, 'pct': prog})
            elif itype not in ('list', 'todo', 'map'):
                charts.append(name)

        focus = (focus or '').strip().lower() or None
        lines = [
            f"Briefing Merka BI (local) — {self.name}",
            f"• {len(tiles)} KPI · {len(charts)} graphiques · {len(payload.get('items') or [])} widgets",
            f"• Seuil anomalie : ±{threshold:g} % · Historique : {health.get('distinct_days')} j / couverture {health.get('coverage_pct')} %",
        ]

        def _fmt(rows, key='name', extra=None):
            bits = []
            for r in rows[:8]:
                label = r.get(key) or '?'
                if extra and r.get(extra) is not None:
                    label = f"{label} ({r[extra]} %)"
                bits.append(label)
            return ", ".join(bits) if bits else "—"

        if focus == 'downs':
            lines.append("Focus : où ça baisse")
            lines.append("• " + (_fmt(downs, extra='trend') if downs else "Aucune baisse significative (≥10 %)."))
        elif focus == 'zeros':
            lines.append("Focus : KPI vides / à zéro")
            lines.append("• " + (_fmt(zeros) if zeros else "Aucun KPI à zéro."))
        elif focus == 'anomalies':
            lines.append("Focus : anomalies")
            lines.append("• " + (_fmt(anomalies, extra='pct') if anomalies else "Aucune anomalie détectée."))
        elif focus == 'who':
            lines.append("Focus : qui / quoi performe")
            lines.append("• Hausses : " + _fmt(ups, extra='trend'))
            lines.append("• Baisses : " + _fmt(downs, extra='trend'))
        else:
            if anomalies:
                lines.append("• Anomalies : " + _fmt(anomalies, extra='pct'))
            else:
                lines.append(f"• Anomalies : aucune (seuil ±{threshold:g} % vs moy. 7j)")
            if downs:
                lines.append("• En baisse : " + _fmt(downs, extra='trend'))
            if ups:
                lines.append("• En hausse : " + _fmt(ups, extra='trend'))
            if zeros:
                lines.append("• À zéro / vide : " + _fmt(zeros))
            if under_target:
                lines.append("• Sous objectif (<70 %) : " + _fmt(under_target, extra='pct'))
            # Corrélations
            if len(downs) >= 2:
                lines.append(
                    "• Corrélation : plusieurs KPI en baisse ensemble — "
                    "regarder la période 7j et les filtres croisés."
                )
            if downs and zeros and len(downs) + len(zeros) >= 3:
                lines.append(
                    "• Signal : baisses + KPI à zéro — vérifier données source / période."
                )
            if health.get('needs_backfill'):
                lines.append(
                    "• Historique insuffisant pour des anomalies fiables — lancez un backfill 14j."
                )
            if not downs and not anomalies and not zeros:
                lines.append("• Situation stable — pas d'alerte majeure.")

        lines.append(
            "Conseil : utilisez les actions ci-dessous (filtre, alerte, ouvrir KPI)."
        )

        actions = [
            {'id': 'filter_7', 'label': 'Période 7j', 'type': 'filter', 'date_filter': 'last_7'},
            {'id': 'filter_30', 'label': 'Période 30j', 'type': 'filter', 'date_filter': 'last_30'},
        ]
        if health.get('needs_backfill'):
            actions.append({'id': 'backfill', 'label': 'Backfill histo. 14j', 'type': 'backfill'})
        # Actions contextuelles
        priority = anomalies or downs or under_target or zeros
        if priority:
            top = priority[0]
            actions.append({
                'id': f"open_{top['id']}",
                'label': _('Ouvrir · %s') % (top.get('name') or 'KPI')[:28],
                'type': 'open_item',
                'item_id': top['id'],
            })
            actions.append({
                'id': f"alert_{top['id']}",
                'label': _('Créer alerte'),
                'type': 'create_alert',
                'item_id': top['id'],
            })

        return {
            'explanation': "\n".join(lines),
            'source': 'local',
            'title': _('Briefing IA locale'),
            'actions': actions,
            'stats': {
                'tiles': len(tiles),
                'charts': len(charts),
                'anomalies': len(anomalies),
                'zeros': len(zeros),
                'downs': len(downs),
                'threshold': threshold,
                'history': health,
            },
        }

    def action_ai_create_alert(self, item_id):
        """Crée une alerte seuil sur un KPI (depuis le panel IA)."""
        self.ensure_one()
        item = self.env['merka.dashboard.item'].browse(int(item_id))
        if not item.exists():
            return {'ok': False, 'error': _('Indicateur introuvable')}
        data = self.env['merka.dashboard.item'].get_item_data(item.id)
        value = float(data.get('value') or 0)
        target = float(data.get('target') or 0)
        # Seuil : 80% de l'objectif, sinon valeur courante * 1.1, sinon 1
        if target:
            threshold = round(target * 0.8, 2)
            operator = 'lt'
            name = _('Alerte sous objectif · %s') % item.name
        elif value:
            threshold = round(abs(value) * 0.75, 2)
            operator = 'lt'
            name = _('Alerte baisse · %s') % item.name
        else:
            threshold = 1.0
            operator = 'lte'
            name = _('Alerte zéro · %s') % item.name
        alert = self.env['merka.dashboard.alert'].create({
            'name': name,
            'dashboard_id': self.id,
            'item_id': item.id,
            'threshold': threshold,
            'operator': operator,
            'notify_user_ids': [(6, 0, [self.env.user.id])],
        })
        return {
            'ok': True,
            'alert_id': alert.id,
            'name': alert.name,
            'threshold': threshold,
            'operator': operator,
        }

    def action_ai_open_item(self, item_id):
        """Ouvre le formulaire indicateur (depuis panel IA)."""
        item = self.env['merka.dashboard.item'].browse(int(item_id))
        item.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': item.name,
            'res_model': 'merka.dashboard.item',
            'res_id': item.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def action_ai_backfill_history(self, days=14):
        """Backfill historique déclenché depuis le panel IA."""
        self.ensure_one()
        return self.env['merka.dashboard.history'].action_backfill_history(days=days)

    def _call_external_ai(self, config, prompt, provider=None):
        """Appel HTTP OpenAI / Azure / custom. Retourne texte ou False.

        :param provider: openai|azure|custom|None (None = config.ai_provider défaut)
        """
        if not config.ai_enabled:
            return False
        creds = config.resolve_ai_credentials(provider)
        provider = creds.get('provider') or 'none'
        key = (creds.get('key') or '').strip()
        endpoint = (creds.get('endpoint') or '').strip()
        model = (creds.get('model') or 'gpt-4o-mini').strip()
        if not key or provider in (False, 'none'):
            return False
        system = 'Tu es un analyste BI Odoo. Réponds en français, concis (3-5 phrases).'
        if provider == 'openai':
            endpoint = endpoint or 'https://api.openai.com/v1/chat/completions'
            body = {
                'model': model or 'gpt-4o-mini',
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.3,
                'max_tokens': 350,
            }
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}',
            }
        elif provider == 'azure':
            if not endpoint:
                return False
            body = {
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.3,
                'max_tokens': 350,
            }
            headers = {
                'Content-Type': 'application/json',
                'api-key': key,
            }
        else:
            # custom : compatible OpenAI chat/completions ou {prompt}/{text}
            if not endpoint:
                return False
            body = {
                'model': model or 'gpt-4o-mini',
                'prompt': prompt,
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.3,
                'max_tokens': 350,
            }
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}',
            }
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(body).encode('utf-8'),
                headers=headers,
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode('utf-8'))
            if isinstance(raw, dict):
                choices = raw.get('choices') or []
                if choices:
                    msg = choices[0].get('message') or {}
                    return (msg.get('content') or choices[0].get('text') or '').strip()
                if raw.get('explanation'):
                    return str(raw['explanation']).strip()
                if raw.get('text'):
                    return str(raw['text']).strip()
                if raw.get('response'):
                    return str(raw['response']).strip()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, TypeError) as exc:
            _logger.warning('Merka AI call failed (%s): %s', provider, exc)
            return False
        return False

    def action_ai_test_provider(self, provider=None):
        """Test de sync / connexion vers un fournisseur (manager)."""
        self.ensure_one()
        config = self.env['merka.dashboard.config'].get_config()
        provider = provider or config.ai_provider
        if not config.ai_enabled:
            return {'ok': False, 'error': _('IA cloud désactivée dans la configuration.')}
        remote = self._call_external_ai(
            config,
            'Réponds uniquement: OK Merka',
            provider=provider,
        )
        if remote:
            return {
                'ok': True,
                'provider': provider,
                'preview': (remote or '')[:120],
            }
        return {
            'ok': False,
            'provider': provider,
            'error': _('Échec de connexion. Vérifiez clé / endpoint / firewall.'),
        }

    def action_ai_explain_item(self, item_id):
        """Insight BI : analyse locale + optionnellement API IA."""
        self.ensure_one()
        config = self.env['merka.dashboard.config'].get_config()
        item = self.env['merka.dashboard.item'].browse(item_id)
        data = self.env['merka.dashboard.item'].get_item_data(item_id)
        local = self._local_bi_insight(item, data)
        title = _('Insight · %s') % (item.name or '')
        actions = [
            {'id': 'filter_7', 'label': 'Période 7j', 'type': 'filter', 'date_filter': 'last_7'},
            {'id': 'filter_30', 'label': 'Période 30j', 'type': 'filter', 'date_filter': 'last_30'},
            {
                'id': f'open_{item.id}',
                'label': _('Ouvrir indicateur'),
                'type': 'open_item',
                'item_id': item.id,
            },
            {
                'id': f'alert_{item.id}',
                'label': _('Créer alerte'),
                'type': 'create_alert',
                'item_id': item.id,
            },
        ]
        if item.item_type in ('tile', 'bullet') or data.get('type') == 'tile':
            actions.append({
                'id': 'open_records',
                'label': _('Voir données'),
                'type': 'open_records',
                'item_id': item.id,
            })
        user_mode = self.env.user.get_merka_ai_mode()
        if not config.ai_enabled or user_mode == 'local':
            return {
                'explanation': local,
                'source': 'local',
                'title': title,
                'actions': actions,
            }
        provider = user_mode if user_mode in ('openai', 'azure', 'custom') else config.ai_provider
        prompt = (
            f"Dashboard: {self.name}\nItem: {item.name}\nType: {item.item_type}\n"
            f"Données JSON: {json.dumps(data, default=str)[:3500]}\n"
            f"Résumé local: {local}\n"
            "Donne une lecture métier actionnable."
        )
        remote = self._call_external_ai(config, prompt, provider=provider)
        if remote:
            return {
                'explanation': remote,
                'source': provider or config.ai_provider,
                'title': title,
                'actions': actions,
            }
        return {
            'explanation': local,
            'source': 'local_fallback',
            'title': title,
            'actions': actions,
        }

    def _ai_resolve_model_bundle(self, keyword):
        """Résout modèle + champs pour génération IA locale."""
        keyword = (keyword or '').strip()
        if not keyword:
            return False
        kw = keyword.lower()
        Model = self.env['ir.model'].sudo()
        hints = [
            ('sale.order', ['vente', 'sales', 'commande', 'ca', 'chiffre']),
            ('crm.lead', ['crm', 'lead', 'opportunité', 'pipeline']),
            ('account.move', ['facture', 'invoice', 'compta', 'accounting']),
            ('stock.quant', ['stock', 'inventaire', 'inventory', 'quantité']),
            ('purchase.order', ['achat', 'purchase', 'fournisseur']),
            ('res.partner', ['client', 'partner', 'contact', 'customer']),
            ('project.task', ['tâche', 'task', 'projet', 'project']),
            ('hr.employee', ['employé', 'rh', 'hr', 'personnel']),
        ]
        model_name = None
        for tech, words in hints:
            if any(w in kw for w in words) and tech in self.env:
                model_name = tech
                break
        if not model_name:
            found = Model.search([
                '|', ('name', 'ilike', keyword), ('model', 'ilike', keyword.replace(' ', '.')),
            ], limit=1)
            model_name = found.model if found else None
        if not model_name or model_name not in self.env:
            return False
        ir_model = Model.search([('model', '=', model_name)], limit=1)
        Fields = self.env['ir.model.fields'].sudo()
        measure = Fields.search([
            ('model_id', '=', ir_model.id),
            ('name', 'in', ['amount_total', 'amount_untaxed', 'quantity', 'qty_available', 'planned_revenue']),
            ('ttype', 'in', ['integer', 'float', 'monetary']),
        ], limit=1)
        date_f = Fields.search([
            ('model_id', '=', ir_model.id),
            ('name', 'in', ['date_order', 'invoice_date', 'create_date', 'date_deadline', 'date']),
            ('ttype', 'in', ['date', 'datetime']),
        ], limit=1)
        groupby = Fields.search([
            ('model_id', '=', ir_model.id),
            ('name', 'in', ['user_id', 'partner_id', 'stage_id', 'state', 'team_id', 'company_id']),
        ], limit=1)
        return {
            'keyword': keyword,
            'model_name': model_name,
            'ir_model': ir_model,
            'measure': measure,
            'date_f': date_f,
            'groupby': groupby,
        }

    def _ai_create_item_from_bundle(self, bundle, item_type, layout_x, layout_y, layout_w, seq):
        keyword = bundle['keyword']
        ir_model = bundle['ir_model']
        measure = bundle['measure']
        date_f = bundle['date_f']
        groupby = bundle['groupby']
        itype = item_type
        use_gb = bool(groupby) and itype != 'tile'
        if itype != 'tile' and not groupby:
            itype = 'tile'
            use_gb = False
        labels = {
            'tile': _('KPI %s') % keyword.title(),
            'line': _('Tendance %s') % keyword.title(),
            'pie': _('Répartition %s') % keyword.title(),
            'bar': _('%s · barres') % keyword.title(),
        }
        return self.env['merka.dashboard.item'].create({
            'dashboard_id': self.id,
            'name': labels.get(itype, f'{keyword.title()} · {ir_model.name}'),
            'item_type': itype,
            'data_source': 'odoo',
            'model_id': ir_model.id,
            'measure_field_id': measure.id if measure else False,
            'date_field_id': date_f.id if date_f else False,
            'groupby_field_id': groupby.id if use_gb else False,
            'aggregation': 'sum' if measure else 'count',
            'date_filter': 'last_30' if date_f else 'none',
            'layout_x': layout_x,
            'layout_y': layout_y,
            'layout_w': layout_w,
            'sequence': seq,
            'note': _('Généré par Merka BI (mot-clé : %s)') % keyword,
        })

    def action_ai_generate_item(self, keyword, item_type='bar', multi=None):
        """Créer 1 widget ou un pack (tuile + courbe + pie) selon config."""
        self.ensure_one()
        keyword = (keyword or '').strip()
        if not keyword:
            return {'ok': False, 'error': _('Mot-clé vide')}
        bundle = self._ai_resolve_model_bundle(keyword)
        if not bundle:
            return {
                'ok': False,
                'error': _(
                    'Aucun modèle Odoo trouvé pour « %s ». Essayez : ventes, crm, factures, stock.'
                ) % keyword,
            }
        config = self.env['merka.dashboard.config'].get_config()
        do_multi = config.ai_multi_generate if multi is None else bool(multi)
        max_y = max((i.layout_y or 0) for i in self.item_ids) if self.item_ids else 0
        seq0 = (max(self.item_ids.mapped('sequence') or [0]) + 10)
        created = []
        if do_multi:
            specs = [
                ('tile', 0, max_y + 2, 3),
                ('line', 3, max_y + 2, 5),
                ('pie', 8, max_y + 2, 4),
            ]
            # Si pas de groupby, pie/line inutiles → tuile + bar count
            if not bundle['groupby']:
                specs = [('tile', 0, max_y + 2, 3), ('bar', 3, max_y + 2, 6)]
            for i, (itype, x, y, w) in enumerate(specs):
                item = self._ai_create_item_from_bundle(bundle, itype, x, y, w, seq0 + i * 10)
                created.append({'id': item.id, 'name': item.name, 'type': item.item_type})
        else:
            itype = item_type if item_type in (
                'tile', 'bar', 'line', 'pie', 'doughnut', 'list', 'hbar', 'area', 'polar',
            ) else 'bar'
            item = self._ai_create_item_from_bundle(bundle, itype, 0, max_y + 2, 3 if itype == 'tile' else 6, seq0)
            created.append({'id': item.id, 'name': item.name, 'type': item.item_type})
        names = ", ".join(c['name'] for c in created)
        return {
            'ok': True,
            'item_id': created[0]['id'],
            'name': names,
            'model': bundle['model_name'],
            'items': created,
            'multi': do_multi,
        }

    def action_duplicate_dashboard(self):
        self.ensure_one()
        copy = self.copy(default={
            'name': f'{self.name} (copie)',
            'menu_id': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'merka.dashboard',
            'res_id': copy.id,
            'view_mode': 'form',
            'target': 'current',
        }
