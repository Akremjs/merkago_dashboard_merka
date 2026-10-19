# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

from .merka_formula import FORMULA_PRESETS, FORMULA_USER_GUIDE_HTML, PRESET_FORMULAS
from .merka_kpi_catalog import KPI_CATALOG, catalog_for_packs

_logger = logging.getLogger(__name__)


class MerkaDashboardKpi(models.Model):
    _name = 'merka.dashboard.kpi'
    _description = 'Dictionnaire indicateur Merkago'
    _order = 'pack_code, sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    pack_code = fields.Selection(
        [
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
            ('other', 'Autre'),
        ],
        required=True,
        default='other',
    )
    model_id = fields.Many2one('ir.model', string='Modèle source', ondelete='cascade')
    definition = fields.Text(string='Définition métier', translate=True)
    formula = fields.Text(
        string='Formule métier',
        help=(
            "Formule entre indicateurs via {code}.\n"
            "Exemple panier moyen : safe_div({ca}, {commandes})\n"
            "→ si ca=12000 et commandes=40, résultat = 300."
        ),
    )
    formula_preset = fields.Selection(
        selection=FORMULA_PRESETS,
        string='Modèle de formule',
        help='Remplit automatiquement le champ Formule avec un modèle métier.',
    )
    formula_unit = fields.Char(string='Unité formule', help='Ex: %, €, jours')
    formula_guide = fields.Html(
        string='Aide formules',
        compute='_compute_formula_guide',
        sanitize=False,
    )
    domain = fields.Char(default='[]')
    aggregation = fields.Selection(
        [
            ('count', 'Nombre'),
            ('sum', 'Somme'),
            ('avg', 'Moyenne'),
            ('min', 'Min'),
            ('max', 'Max'),
            ('formula', 'Formule'),
        ],
        default='count',
    )
    measure_field = fields.Char(help='Nom technique du champ mesure')
    date_field = fields.Char(help='Nom technique du champ date')
    audience = fields.Char(string='Public cible')
    refresh_hint = fields.Char(string='Fréquence recommandée')
    company_id = fields.Many2one('res.company', string='Société')
    auto_generated = fields.Boolean(
        string='Généré auto',
        default=False,
        help='Créé automatiquement selon les apps Odoo installées.',
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Le code KPI doit être unique.'),
    ]

    def _compute_formula_guide(self):
        for rec in self:
            rec.formula_guide = FORMULA_USER_GUIDE_HTML

    @api.onchange('formula_preset')
    def _onchange_formula_preset(self):
        if self.formula_preset and self.formula_preset in PRESET_FORMULAS:
            self.formula = PRESET_FORMULAS[self.formula_preset]
            self.aggregation = 'formula'
            if self.formula_preset in ('taux', 'evolution', 'marge', 'conversion', 'atteinte'):
                if not self.formula_unit:
                    self.formula_unit = '%'
            elif self.formula_preset == 'panier' and not self.formula_unit:
                self.formula_unit = '€'

    def _resolve_model(self, model_name):
        if not model_name or model_name not in self.env:
            return self.env['ir.model']
        return self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)

    @api.model
    def auto_seed_kpis(self, pack_codes=None):
        """
        Crée / met à jour les KPI du dictionnaire pour les packs détectés.
        Lie model_id + measure/date dès que le modèle existe dans la base.
        """
        if pack_codes is None:
            pack_codes = [
                p['code']
                for p in self.env['merka.dashboard'].detect_available_packs()
            ]
        catalog = catalog_for_packs(pack_codes)
        created, updated, skipped = [], [], []
        for spec in catalog:
            model_name = spec.get('model')
            # Formules : pas besoin de modèle
            if model_name and model_name not in self.env:
                skipped.append(spec['code'])
                continue
            model_rec = self._resolve_model(model_name) if model_name else self.env['ir.model']
            # Vérifier que les champs existent si modèle présent
            if model_name and model_name in self.env:
                Model = self.env[model_name]
                if spec.get('measure') and spec['measure'] not in Model._fields:
                    skipped.append(spec['code'])
                    continue
                if spec.get('date_field') and spec['date_field'] not in Model._fields:
                    # date optionnelle : on continue sans date
                    pass

            vals = {
                'name': spec['name'],
                'code': spec['code'],
                'pack_code': spec['pack_code'],
                'sequence': spec.get('sequence', 10),
                'definition': spec.get('definition'),
                'aggregation': spec.get('aggregation', 'count'),
                'domain': spec.get('domain') or '[]',
                'measure_field': spec.get('measure') or False,
                'date_field': spec.get('date_field') or False,
                'formula': spec.get('formula') or False,
                'formula_unit': spec.get('formula_unit') or False,
                'audience': spec.get('audience') or False,
                'refresh_hint': spec.get('refresh_hint') or 'Quotidien',
                'auto_generated': True,
                'active': True,
                'model_id': model_rec.id if model_rec else False,
            }
            existing = self.search([('code', '=', spec['code'])], limit=1)
            if existing:
                existing.write({
                    k: v for k, v in vals.items()
                    if k not in ('code',)  # code immuable
                })
                updated.append(spec['code'])
            else:
                self.create(vals)
                created.append(spec['code'])

        _logger.info(
            "Merka KPI seed: created=%s updated=%s skipped=%s packs=%s",
            created, updated, skipped, pack_codes,
        )
        return {
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'pack_codes': list(pack_codes),
        }

    def _short_code(self):
        self.ensure_one()
        prefix = (self.pack_code or '') + '_'
        if self.code and self.code.startswith(prefix):
            return self.code[len(prefix):]
        return self.code or ''

    def _apply_to_dashboards(self):
        """Crée les items manquants liés à ces KPI sur les dashboards packs."""
        Item = self.env['merka.dashboard.item']
        Dash = self.env['merka.dashboard']
        created = 0
        for kpi in self:
            if not kpi.pack_code or kpi.pack_code == 'other':
                continue
            dash = Dash.search([
                ('pack_code', '=', kpi.pack_code),
                ('active', '=', True),
            ], limit=1)
            if not dash:
                continue
            # Déjà présent via kpi_id, code ou même libellé
            domain_exist = [
                ('dashboard_id', '=', dash.id),
                '|', '|',
                ('kpi_id', '=', kpi.id),
                ('code', '=', kpi._short_code()),
                ('name', '=', kpi.name),
            ]
            if Item.search(domain_exist, limit=1):
                # Lier le kpi_id si item existant sans lien
                orphan = Item.search([
                    ('dashboard_id', '=', dash.id),
                    ('name', '=', kpi.name),
                    ('kpi_id', '=', False),
                ], limit=1)
                if orphan:
                    orphan.kpi_id = kpi.id
                    if not orphan.code:
                        orphan.code = kpi._short_code()
                continue
            vals = {
                'dashboard_id': dash.id,
                'name': kpi.name,
                'code': kpi._short_code(),
                'kpi_id': kpi.id,
                'sequence': kpi.sequence,
                'layout_w': 3,
                'unit_label': kpi.formula_unit or False,
            }
            if kpi.aggregation == 'formula' and kpi.formula:
                vals.update({
                    'data_source': 'formula',
                    'item_type': 'tile',
                    'formula': kpi.formula,
                    'aggregation': 'count',
                })
            elif kpi.model_id and kpi.model_id.model in self.env:
                vals.update({
                    'data_source': 'odoo',
                    'item_type': 'tile',
                    'model_id': kpi.model_id.id,
                    'aggregation': kpi.aggregation if kpi.aggregation != 'formula' else 'count',
                    'domain': kpi.domain or '[]',
                })
                Model = self.env[kpi.model_id.model]
                if kpi.measure_field and kpi.measure_field in Model._fields:
                    field = self.env['ir.model.fields'].search([
                        ('model_id', '=', kpi.model_id.id),
                        ('name', '=', kpi.measure_field),
                    ], limit=1)
                    if field:
                        vals['measure_field_id'] = field.id
                if kpi.date_field and kpi.date_field in Model._fields:
                    field = self.env['ir.model.fields'].search([
                        ('model_id', '=', kpi.model_id.id),
                        ('name', '=', kpi.date_field),
                    ], limit=1)
                    if field:
                        vals['date_field_id'] = field.id
                        vals['date_filter'] = 'last_30'
            else:
                continue
            Item.create(vals)
            created += 1
        return created

    @api.model
    def _dedupe_dashboard_tiles(self, pack_codes=None):
        """Supprime les tuiles en double (même code ou même nom) en gardant celle liée au KPI."""
        Item = self.env['merka.dashboard.item']
        Dash = self.env['merka.dashboard']
        domain = [('active', '=', True), ('pack_code', '!=', False)]
        if pack_codes:
            domain.append(('pack_code', 'in', list(pack_codes)))
        removed = 0
        for dash in Dash.search(domain):
            tiles = Item.search([
                ('dashboard_id', '=', dash.id),
                ('item_type', '=', 'tile'),
            ], order='id')
            seen_codes, seen_names = {}, {}
            to_unlink = Item.browse()
            for tile in tiles:
                key_c = (tile.code or '').strip().lower()
                key_n = (tile.name or '').strip().lower()
                dup = False
                if key_c and key_c in seen_codes:
                    keep, other = seen_codes[key_c], tile
                    if other.kpi_id and not keep.kpi_id:
                        to_unlink |= keep
                        seen_codes[key_c] = other
                    else:
                        to_unlink |= other
                    dup = True
                elif key_c:
                    seen_codes[key_c] = tile
                if key_n and key_n in seen_names and not dup:
                    keep, other = seen_names[key_n], tile
                    if other.kpi_id and not keep.kpi_id:
                        to_unlink |= keep
                        seen_names[key_n] = other
                    else:
                        to_unlink |= other
                elif key_n and not dup:
                    seen_names[key_n] = tile
            if to_unlink:
                removed += len(to_unlink)
                to_unlink.unlink()
        return removed

    def action_apply_to_dashboard(self):
        """Bouton UI : pousse les KPI sélectionnés vers les dashboards."""
        created = self._apply_to_dashboards()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('KPI appliqués'),
                'message': _('%s indicateur(s) ajouté(s) aux dashboards.') % created,
                'type': 'success',
            },
        }
