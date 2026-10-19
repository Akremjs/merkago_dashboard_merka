# -*- coding: utf-8 -*-
import csv
import io
import re

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval

from .merka_formula import (
    FORMULA_PRESETS,
    FORMULA_USER_GUIDE_HTML,
    PRESET_FORMULAS,
    evaluate_formula,
    extract_codes,
    FormulaError,
)


class MerkaDashboardItem(models.Model):
    _name = 'merka.dashboard.item'
    _description = 'Merkago Dashboard Item'
    _order = 'sequence, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    dashboard_id = fields.Many2one(
        'merka.dashboard',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='dashboard_id.company_id',
        store=True,
        readonly=True,
    )
    item_type = fields.Selection(
        [
            ('tile', 'Tuile KPI'),
            ('line', 'Courbe'),
            ('bar', 'Barres'),
            ('hbar', 'Barres horizontales'),
            ('pie', 'Camembert'),
            ('doughnut', 'Anneau'),
            ('list', 'Liste'),
            ('funnel', 'Entonnoir'),
            ('radar', 'Radar'),
            ('scatter', 'Nuage de points'),
            ('bullet', 'Bullet / jauge'),
            ('waterfall', 'Cascade'),
            ('polar', 'Aires polaires'),
            ('flower', 'Fleur'),
            ('pivot', 'Tableau croisé'),
            ('map', 'Carte'),
            ('todo', 'Tâches'),
            ('area', 'Aires'),
        ],
        default='tile',
        required=True,
    )
    note = fields.Text(
        string='Annotation',
        help='Commentaire visible sur le dashboard (équipe).',
    )
    code = fields.Char(
        string='Code',
        index=True,
        help="Code technique pour les formules, ex: ca, commandes. Référence : {ca}",
    )
    data_source = fields.Selection(
        [
            ('odoo', 'Modèle Odoo'),
            ('sql', 'SQL lecture seule'),
            ('csv', 'CSV / Excel texte'),
            ('formula', 'Formule'),
        ],
        default='odoo',
        required=True,
    )
    formula = fields.Text(
        string='Formule',
        help=(
            "Formule entre indicateurs du même tableau via {code}.\n"
            "Exemple : safe_div({ca}, {commandes}) → panier moyen "
            "(si ca=12000 et commandes=40 → 300)."
        ),
    )
    formula_preset = fields.Selection(
        selection=FORMULA_PRESETS,
        string='Modèle de formule',
        help='Remplit automatiquement le champ Formule avec un modèle métier.',
    )
    formula_decimals = fields.Integer(
        string='Décimales',
        default=2,
        help='Nombre de décimales affichées pour le résultat de la formule.',
    )
    formula_codes_help = fields.Text(
        string='Codes disponibles',
        compute='_compute_formula_codes_help',
        help='Codes des autres indicateurs du même tableau utilisables dans {code}.',
    )
    formula_preview = fields.Char(
        string='Aperçu résultat',
        compute='_compute_formula_preview',
    )
    formula_guide = fields.Html(
        string='Aide formules',
        compute='_compute_formula_guide',
        sanitize=False,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Modèle',
        ondelete='cascade',
    )
    model_name = fields.Char(related='model_id.model', store=True, readonly=True)
    sql_query = fields.Text(
        string='Requête SQL',
        help='SELECT uniquement. Colonnes attendues : label, value (ou 2 premières colonnes).',
    )
    csv_data = fields.Text(
        string='Données CSV',
        help='Format: label,value (une ligne d’en-tête optionnelle).',
    )
    measure_field_id = fields.Many2one(
        'ir.model.fields',
        string='Mesure',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['integer', 'float', 'monetary'])]",
    )
    date_field_id = fields.Many2one(
        'ir.model.fields',
        string='Champ date',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime'])]",
    )
    groupby_field_id = fields.Many2one(
        'ir.model.fields',
        string='Lignes / Group By',
        domain="[('model_id', '=', model_id)]",
        help='Dimension en lignes (tableau croisé) ou groupement du graphique.',
    )
    col_groupby_field_id = fields.Many2one(
        'ir.model.fields',
        string='Colonnes (tableau croisé)',
        domain="[('model_id', '=', model_id)]",
        help='Dimension en colonnes pour le type Tableau croisé.',
    )
    aggregation = fields.Selection(
        [
            ('count', 'Nombre'),
            ('sum', 'Somme'),
            ('avg', 'Moyenne'),
            ('min', 'Min'),
            ('max', 'Max'),
        ],
        default='count',
        required=True,
    )
    domain = fields.Char(default='[]', help='Domaine Odoo. Variables: %UID, %MYCOMPANY')
    limit = fields.Integer(default=80)
    sort = fields.Char(string='Tri', help="Ex: 'date desc' ou 'amount_total desc'")
    date_filter = fields.Selection(
        [
            ('none', 'Aucun'),
            ('today', "Aujourd'hui"),
            ('last_7', '7 derniers jours'),
            ('last_30', '30 derniers jours'),
            ('last_90', '90 derniers jours'),
            ('this_month', 'Mois en cours'),
            ('last_month', 'Mois précédent'),
            ('this_year', "Année en cours"),
            ('custom', 'Période personnalisée'),
        ],
        default='none',
    )
    date_from = fields.Date()
    date_to = fields.Date()
    target_value = fields.Float(string='Objectif')
    layout_x = fields.Integer(default=0)
    layout_y = fields.Integer(default=0)
    layout_w = fields.Integer(default=3)
    layout_h = fields.Integer(default=2)
    kpi_id = fields.Many2one('merka.dashboard.kpi', string='Indicateur dictionnaire')
    show_values = fields.Boolean(default=True)
    currency_id = fields.Many2one('res.currency')
    unit_label = fields.Char(string='Unité')

    def _compute_formula_guide(self):
        for item in self:
            item.formula_guide = FORMULA_USER_GUIDE_HTML

    @api.depends('dashboard_id', 'dashboard_id.item_ids', 'dashboard_id.item_ids.code', 'dashboard_id.item_ids.name')
    def _compute_formula_codes_help(self):
        for item in self:
            siblings = item.dashboard_id.item_ids.filtered(
                lambda i: i.id != item.id and i.active and (i.code or '').strip()
            )
            if not siblings:
                item.formula_codes_help = _(
                    "Aucun code disponible. Donnez un code aux autres indicateurs "
                    "(ex: ca, commandes) pour les utiliser ici : {ca}"
                )
                continue
            lines = [
                _('Utilisez ces codes dans votre formule (ex: {ca}) :'),
                '',
            ]
            for sib in siblings.sorted('sequence'):
                lines.append('%s → %s (%s)' % (
                    '{%s}' % sib.code.strip(),
                    sib.name,
                    sib.data_source or 'odoo',
                ))
            item.formula_codes_help = '\n'.join(lines)

    @api.depends(
        'formula', 'data_source', 'kpi_id', 'kpi_id.formula',
        'dashboard_id', 'dashboard_id.item_ids',
    )
    def _compute_formula_preview(self):
        for item in self:
            if item.data_source != 'formula':
                item.formula_preview = False
                continue
            try:
                data = item._data_from_formula()
                if data.get('error'):
                    item.formula_preview = _('Erreur : %s') % data['error']
                else:
                    unit = data.get('unit') or ''
                    item.formula_preview = '%s %s' % (data.get('value'), unit)
            except Exception as exc:
                item.formula_preview = _('Erreur : %s') % exc

    @api.onchange('formula_preset')
    def _onchange_formula_preset(self):
        if self.formula_preset and self.formula_preset in PRESET_FORMULAS:
            self.formula = PRESET_FORMULAS[self.formula_preset]
            self.data_source = 'formula'
            if self.formula_preset in ('taux', 'evolution', 'marge', 'conversion', 'atteinte'):
                if not self.unit_label:
                    self.unit_label = '%'

    @api.onchange('kpi_id')
    def _onchange_kpi_id_formula(self):
        if self.kpi_id and self.kpi_id.formula and not self.formula:
            self.formula = self.kpi_id.formula
            self.data_source = 'formula'
            if self.kpi_id.formula_unit and not self.unit_label:
                self.unit_label = self.kpi_id.formula_unit
            if not self.code and self.kpi_id.code:
                self.code = self.kpi_id.code

    def action_preview_formula(self):
        self.ensure_one()
        data = self._data_from_formula()
        msg = _(
            "Formule : %(formula)s\n"
            "Variables : %(vars)s\n"
            "Résultat : %(value)s %(unit)s\n"
            "%(err)s"
        ) % {
            'formula': data.get('formula') or self.formula or '—',
            'vars': data.get('formula_vars') or {},
            'value': data.get('value'),
            'unit': data.get('unit') or '',
            'err': (_('Erreur : %s') % data['error']) if data.get('error') else '',
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Aperçu formule'),
                'message': msg,
                'type': 'warning' if data.get('error') else 'success',
                'sticky': False,
            },
        }

    def _resolve_domain(self):
        self.ensure_one()
        domain = safe_eval(self.domain or '[]')
        uid = self.env.uid
        company_id = self.env.company.id
        resolved = []
        for leaf in domain:
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3:
                field, op, value = leaf
                if value == '%UID':
                    value = uid
                elif value == '%MYCOMPANY':
                    value = company_id
                resolved.append((field, op, value))
            else:
                resolved.append(leaf)
        return resolved

    def _date_bounds(self, filter_code=None, override_from=None, override_to=None):
        """Return (date_from, date_to) for a filter code."""
        self.ensure_one()
        if override_from or override_to:
            return override_from, override_to
        code = filter_code or self.date_filter
        today = fields.Date.context_today(self)
        if code in (False, 'none'):
            return None, None
        if code == 'today':
            return today, today
        if code == 'last_7':
            return today - relativedelta(days=6), today
        if code == 'last_30':
            return today - relativedelta(days=29), today
        if code == 'last_90':
            return today - relativedelta(days=89), today
        if code == 'this_month':
            return today.replace(day=1), today
        if code == 'last_month':
            first_this = today.replace(day=1)
            last_prev = first_this - relativedelta(days=1)
            return last_prev.replace(day=1), last_prev
        if code == 'this_year':
            return today.replace(month=1, day=1), today
        if code == 'custom':
            return self.date_from, self.date_to
        return None, None

    def _effective_date_filter(self, global_date_filter=None):
        self.ensure_one()
        if global_date_filter and global_date_filter != 'none':
            return global_date_filter
        return self.date_filter or 'none'

    def _date_domain(self, filter_code=None, global_date_filter=None, date_from=None, date_to=None):
        self.ensure_one()
        if not self.date_field_id:
            return []
        code = filter_code or self._effective_date_filter(global_date_filter)
        d_from, d_to = self._date_bounds(code, override_from=date_from, override_to=date_to)
        if not d_from and not d_to:
            return []
        field = self.date_field_id.name
        domain = []
        if d_from:
            domain.append((field, '>=', d_from))
        if d_to:
            domain.append((field, '<=', d_to))
        return domain

    def _data_from_pivot(self, Model, domain, measure, agg, date_label):
        """Tableau croisé : lignes × colonnes → matrice de valeurs."""
        self.ensure_one()
        row_field = self.groupby_field_id
        col_field = self.col_groupby_field_id
        if not row_field or not col_field:
            return {
                'type': 'pivot',
                'name': self.name,
                'error': _('Définissez Lignes et Colonnes pour le tableau croisé.'),
                'rows': [],
                'cols': [],
                'matrix': [],
                'row_totals': [],
                'col_totals': [],
                'grand_total': 0,
            }
        row_gb = row_field.name
        col_gb = col_field.name
        if row_field.ttype in ('date', 'datetime'):
            row_gb = f'{row_gb}:month'
        if col_field.ttype in ('date', 'datetime'):
            col_gb = f'{col_gb}:month'

        groups = Model.read_group(
            domain,
            [measure] if measure != 'id' and agg != 'count' else [],
            [row_gb, col_gb],
            lazy=False,
            limit=self.limit or 200,
        )
        rows_order, cols_order = [], []
        row_raws, col_raws = {}, {}
        rows_seen, cols_seen = set(), set()
        cells = {}  # (row_label, col_label) -> value

        for group in groups:
            r_raw = group.get(row_gb)
            c_raw = group.get(col_gb)
            r_label = self._format_label(r_raw)
            c_label = self._format_label(c_raw)
            if r_label not in rows_seen:
                rows_seen.add(r_label)
                rows_order.append(r_label)
                row_raws[r_label] = r_raw[0] if isinstance(r_raw, (list, tuple)) else r_raw
            if c_label not in cols_seen:
                cols_seen.add(c_label)
                cols_order.append(c_label)
                col_raws[c_label] = c_raw[0] if isinstance(c_raw, (list, tuple)) else c_raw
            if agg == 'count':
                val = group.get('__count') or group.get(f'{row_gb}_count') or 0
            else:
                val = group.get(measure) or 0
            key = (r_label, c_label)
            cells[key] = cells.get(key, 0) + float(val or 0)

        # Limiter colonnes trop nombreuses
        max_cols = 12
        if len(cols_order) > max_cols:
            # garder les colonnes au plus fort total
            col_sums = {
                c: sum(cells.get((r, c), 0) for r in rows_order)
                for c in cols_order
            }
            cols_order = sorted(cols_order, key=lambda c: col_sums[c], reverse=True)[:max_cols]

        matrix = []
        row_totals = []
        for r in rows_order:
            line = [cells.get((r, c), 0) for c in cols_order]
            matrix.append(line)
            row_totals.append(sum(line))
        col_totals = [
            sum(matrix[i][j] for i in range(len(rows_order))) if rows_order else 0
            for j in range(len(cols_order))
        ]
        grand = sum(row_totals)
        flat = [v for line in matrix for v in line]
        vmax = max(flat) if flat else 0
        intensities = [
            [round((v / vmax), 3) if vmax else 0 for v in line]
            for line in matrix
        ]
        return {
            'type': 'pivot',
            'name': self.name,
            'rows': rows_order,
            'cols': cols_order,
            'matrix': matrix,
            'intensities': intensities,
            'row_totals': row_totals,
            'col_totals': col_totals,
            'grand_total': grand,
            'row_label': row_field.field_description,
            'col_label': col_field.field_description,
            'row_field': row_field.name,
            'col_field': col_field.name,
            'row_raws': row_raws,
            'col_raws': col_raws,
            'cross_model': self.model_name,
            'unit': self.unit_label or '',
            'date_filter': date_label,
            'show_values': self.show_values,
            'heatmap': True,
        }

    def _cross_filter_domain(self, cross_filter=None):
        """Applique un filtre croisé (clic graphique) si le champ existe sur le modèle."""
        self.ensure_one()
        if not cross_filter or not self.model_name or self.model_name not in self.env:
            return []
        # Ne pas refiltrer la source du clic (évite un camembert à 1 part)
        if cross_filter.get('source_item_id') and cross_filter['source_item_id'] == self.id:
            return []
        field = cross_filter.get('field')
        value = cross_filter.get('value')
        if not field or value in (None, False, ''):
            return []
        Model = self.env[self.model_name]
        if field not in Model._fields:
            return []
        ftype = Model._fields[field].type
        if ftype == 'many2one' and isinstance(value, str):
            comodel = Model._fields[field].comodel_name
            found = self.env[comodel].name_search(value, operator='ilike', limit=1)
            if found:
                value = found[0][0]
            else:
                return []
        return [(field, '=', value)]

    def _data_from_csv(self):
        self.ensure_one()
        raw = (self.csv_data or '').strip()
        if not raw:
            return {'type': self.item_type, 'labels': [], 'values': [], 'name': self.name}
        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)
        if not rows:
            return {'type': self.item_type, 'labels': [], 'values': [], 'name': self.name}
        start = 1 if rows and rows[0] and not self._is_number(rows[0][-1]) else 0
        labels, values = [], []
        for row in rows[start:]:
            if len(row) < 2:
                continue
            labels.append(row[0])
            try:
                values.append(float(str(row[1]).replace(' ', '').replace(',', '.')))
            except ValueError:
                values.append(0)
        if self.item_type == 'tile':
            return {
                'type': 'tile',
                'value': sum(values),
                'name': self.name,
                'target': self.target_value,
                'unit': self.unit_label or '',
            }
        return {
            'type': self.item_type,
            'labels': labels,
            'values': values,
            'name': self.name,
            'subtitle': 'CSV',
        }

    @api.model
    def _is_number(self, value):
        try:
            float(str(value).replace(' ', '').replace(',', '.'))
            return True
        except Exception:
            return False

    def _data_from_sql(self):
        self.ensure_one()
        config = self.env['merka.dashboard.config'].get_config()
        if not config.allow_sql_kpi:
            raise UserError(_('Les KPI SQL sont désactivés dans la configuration.'))
        query = (self.sql_query or '').strip().rstrip(';')
        if not query:
            return {'type': self.item_type, 'labels': [], 'values': [], 'name': self.name}
        if not re.match(r'(?is)^\s*select\b', query):
            raise UserError(_('Seules les requêtes SELECT sont autorisées.'))
        forbidden = re.search(
            r'(?is)\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call)\b',
            query,
        )
        if forbidden:
            raise UserError(_('Requête SQL non autorisée.'))
        self.env.cr.execute(query)
        rows = self.env.cr.fetchall()
        labels, values = [], []
        for row in rows[: self.limit or 50]:
            if len(row) >= 2:
                labels.append(str(row[0]))
                values.append(float(row[1] or 0))
            elif len(row) == 1:
                labels.append(str(len(labels) + 1))
                values.append(float(row[0] or 0))
        if self.item_type == 'tile':
            return {
                'type': 'tile',
                'value': values[0] if len(values) == 1 else sum(values),
                'name': self.name,
                'target': self.target_value,
                'unit': self.unit_label or '',
            }
        return {
            'type': self.item_type if self.item_type != 'list' else 'bar',
            'labels': labels,
            'values': values,
            'name': self.name,
            'subtitle': 'SQL',
        }

    def _format_label(self, value):
        if value is False or value is None:
            return 'N/A'
        if isinstance(value, (list, tuple)):
            return value[1] if len(value) > 1 else str(value[0])
        return str(value)

    def _aggregate(self, Model, domain, measure, agg):
        if agg == 'count':
            return Model.search_count(domain)
        groups = Model.read_group(domain, [measure], [])
        if not groups:
            return 0
        return groups[0].get(measure) or 0

    def action_open_records(self):
        """Drill vers les enregistrements sources."""
        self.ensure_one()
        if self.data_source != 'odoo' or not self.model_name:
            raise UserError(_('Drill disponible uniquement pour les sources modèle Odoo.'))
        domain = expression.AND([self._resolve_domain(), self._date_domain()])
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self.model_name,
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'limit': self.limit or 80,
            'context': dict(self.env.context),
        }

    def action_open_record(self, res_id):
        """Ouvre une fiche depuis une ligne de liste."""
        self.ensure_one()
        if self.data_source != 'odoo' or not self.model_name:
            raise UserError(_('Ouverture disponible uniquement pour les sources modèle Odoo.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self.model_name,
            'res_id': int(res_id),
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_open_chat(self):
        """Ouvre le chatter Discuss de l'indicateur (popup)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Discussion · %s') % self.name,
            'res_model': 'merka.dashboard.item',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'},
        }

    def action_post_chat_message(self, body):
        """Poster un commentaire depuis le dashboard (tous lecteurs autorisés)."""
        self.ensure_one()
        body = (body or '').strip()
        if not body:
            raise UserError(_('Message vide.'))
        # sudo pour permettre aux User/Restricted de commenter sans droit write item
        self.sudo().message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=self.env.user.partner_id.id,
        )
        if self.dashboard_id:
            self.dashboard_id._notify_stream()
        return {'ok': True}

    def write(self, vals):
        res = super().write(vals)
        # Invalidation cache + push streaming aux clients ouverts
        if any(k not in ('message_follower_ids', 'message_ids', 'activity_ids') for k in vals):
            for dash in self.mapped('dashboard_id'):
                dash._notify_stream()
        return res

    def action_drill_groupby(self, label_value=None, global_date_filter=None, date_from=None, date_to=None):
        """Drill-down : filtre le modèle sur la valeur cliquée du graphique."""
        self.ensure_one()
        if self.data_source != 'odoo' or not self.model_name:
            raise UserError(_('Drill disponible uniquement pour les sources modèle Odoo.'))
        domain = expression.AND([
            self._resolve_domain(),
            self._date_domain(
                global_date_filter=global_date_filter,
                date_from=date_from,
                date_to=date_to,
            ),
        ])
        if self.groupby_field_id and label_value not in (None, False, '', 'N/A'):
            field = self.groupby_field_id.name
            # Many2one labels arrivent souvent en texte → recherche id
            if self.groupby_field_id.ttype == 'many2one':
                comodel = self.env[self.model_name]._fields[field].comodel_name
                partner = self.env[comodel].search([('display_name', '=', label_value)], limit=1)
                if not partner:
                    partner = self.env[comodel].name_search(label_value, operator='ilike', limit=1)
                    partner = self.env[comodel].browse(partner[0][0]) if partner else self.env[comodel]
                if partner:
                    domain = expression.AND([domain, [(field, '=', partner.id)]])
            elif self.groupby_field_id.ttype in ('date', 'datetime'):
                # label formaté → pas de filtre précis, ouvrir période globale
                pass
            else:
                domain = expression.AND([domain, [(field, '=', label_value)]])
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s · %s') % (self.name, label_value or _('Détail')),
            'res_model': self.model_name,
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
            'limit': self.limit or 80,
        }

    def _compute_compare(self, Model, measure, agg, global_date_filter=None, date_from=None, date_to=None):
        """Retourne {trend, previous, current} vs période précédente de même durée."""
        self.ensure_one()
        empty = {'trend': None, 'previous': None, 'current': None}
        code = self._effective_date_filter(global_date_filter)
        if date_from or date_to:
            code = 'custom'
        if not self.date_field_id or code in (False, 'none'):
            return empty
        d_from, d_to = self._date_bounds(code, override_from=date_from, override_to=date_to)
        if not d_from or not d_to:
            return empty
        days = (d_to - d_from).days + 1
        prev_to = d_from - relativedelta(days=1)
        prev_from = prev_to - relativedelta(days=days - 1)
        field = self.date_field_id.name
        base = self._resolve_domain()
        curr_domain = expression.AND([
            base,
            self._date_domain(global_date_filter=global_date_filter, date_from=date_from, date_to=date_to),
        ])
        prev_domain = expression.AND([base, [(field, '>=', prev_from), (field, '<=', prev_to)]])
        current = self._aggregate(Model, curr_domain, measure, agg)
        previous = self._aggregate(Model, prev_domain, measure, agg)
        if not previous:
            trend = 100.0 if current else 0.0
        else:
            trend = round(((current - previous) / abs(previous)) * 100.0, 1)
        return {
            'trend': trend,
            'previous': previous,
            'current': current,
        }

    def _compute_trend(self, Model, measure, agg, global_date_filter=None, date_from=None, date_to=None):
        return self._compute_compare(
            Model, measure, agg,
            global_date_filter=global_date_filter,
            date_from=date_from,
            date_to=date_to,
        ).get('trend')

    def _compute_sparkline(self, Model, measure, agg, points=8):
        """Série courte (derniers jours) pour mini-courbe KPI."""
        self.ensure_one()
        if not self.date_field_id or self.model_name not in self.env:
            return []
        field = self.date_field_id.name
        base = self._resolve_domain()
        today = fields.Datetime.now()
        series = []
        for i in range(points - 1, -1, -1):
            day_to = today - relativedelta(days=i)
            day_from = day_to.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_from + relativedelta(days=1, seconds=-1)
            domain = expression.AND([
                base,
                [(field, '>=', day_from), (field, '<=', day_end)],
            ])
            try:
                series.append(float(self._aggregate(Model, domain, measure, agg) or 0))
            except Exception:
                series.append(0.0)
        return series

    def _resolve_formula_expr(self):
        self.ensure_one()
        expr = (self.formula or '').strip()
        if not expr and self.kpi_id and self.kpi_id.formula:
            expr = (self.kpi_id.formula or '').strip()
        return expr

    def _resolve_formula_var(self, code, global_date_filter=None, date_from=None, date_to=None, _stack=None):
        """Résout un {code} vers une valeur numérique (indicateur frère ou 0)."""
        self.ensure_one()
        sibling = self.dashboard_id.item_ids.filtered(
            lambda i, c=code: (i.code or '').strip() == c and i.id != self.id and i.active
        )[:1]
        if not sibling:
            return 0.0, _('code introuvable: %s') % code
        if sibling.data_source == 'formula':
            data = sibling._data_from_formula(
                global_date_filter=global_date_filter,
                date_from=date_from,
                date_to=date_to,
                _stack=_stack,
            )
        else:
            data = self.get_item_data(
                sibling.id,
                global_date_filter=global_date_filter,
                date_from=date_from,
                date_to=date_to,
            )
        try:
            return float(data.get('value') or 0.0), False
        except (TypeError, ValueError):
            return 0.0, _('valeur invalide: %s') % code

    def _data_from_formula(self, global_date_filter=None, date_from=None, date_to=None, _stack=None):
        """Évalue une formule {code} entre indicateurs du même tableau."""
        self.ensure_one()
        unit = self.unit_label or (self.kpi_id.formula_unit if self.kpi_id else '') or ''
        decimals = self.formula_decimals if self.formula_decimals is not False else 2
        decimals = max(0, min(6, int(decimals or 2)))

        stack = set(_stack or [])
        if self.id in stack:
            return {
                'type': 'tile',
                'value': 0,
                'name': self.name,
                'error': _('Boucle détectée dans les formules'),
                'unit': unit,
            }
        stack.add(self.id)

        expr = self._resolve_formula_expr()
        if not expr:
            return {
                'type': 'tile',
                'value': 0,
                'name': self.name,
                'error': _('Formule vide'),
                'unit': unit,
            }

        warnings = []
        resolved = {}
        for code in extract_codes(expr):
            val, warn = self._resolve_formula_var(
                code,
                global_date_filter=global_date_filter,
                date_from=date_from,
                date_to=date_to,
                _stack=stack,
            )
            resolved[code] = val
            if warn:
                warnings.append(warn)

        try:
            value = evaluate_formula(expr, resolved)
        except FormulaError as exc:
            return {
                'type': 'tile',
                'value': 0,
                'name': self.name,
                'error': str(exc),
                'formula': expr,
                'formula_vars': resolved,
                'unit': unit,
            }
        except Exception as exc:
            return {
                'type': 'tile',
                'value': 0,
                'name': self.name,
                'error': str(exc),
                'formula': expr,
                'formula_vars': resolved,
                'unit': unit,
            }

        value = round(float(value), decimals)
        return {
            'type': 'tile' if self.item_type in ('tile', 'bullet') else self.item_type,
            'value': value,
            'name': self.name,
            'target': self.target_value,
            'unit': unit,
            'trend': None,
            'sparkline': [],
            'formula': expr,
            'formula_vars': resolved,
            'formula_warnings': warnings,
            'show_values': self.show_values,
            'labels': [self.name],
            'values': [value],
        }

    @api.model
    def get_item_data(self, item_id, global_date_filter=None, date_from=None, date_to=None,
                      cross_filter=None, use_cache=True):
        """Données agrégées pour le rendu frontend."""
        item = self.browse(item_id)
        item.check_access_rights('read')
        item.check_access_rule('read')

        # Cache court TTL
        Cache = self.env['merka.dashboard.cache']
        config = self.env['merka.dashboard.config'].get_config()
        ttl = config.cache_ttl_seconds if use_cache else 0
        cache_key = False
        if ttl and ttl > 0:
            cache_key = Cache._make_key(
                item.id,
                global_date_filter,
                date_from,
                date_to,
                cross_filter,
                self.env.company.id,
            )
            cached = Cache.get_json(cache_key)
            if cached is not None:
                cached['from_cache'] = True
                return cached

        if item.data_source == 'csv':
            return item._data_from_csv()
        if item.data_source == 'sql':
            return item._data_from_sql()
        if item.data_source == 'formula':
            data = item._data_from_formula(
                global_date_filter=global_date_filter,
                date_from=date_from,
                date_to=date_to,
            )
            if cache_key and ttl:
                Cache.set_json(cache_key, data, ttl)
            return data

        if not item.model_name or item.model_name not in self.env:
            return {'type': 'tile', 'value': 0, 'name': item.name, 'error': 'model'}
        Model = self.env[item.model_name]
        domain = expression.AND([
            item._resolve_domain(),
            item._date_domain(
                global_date_filter=global_date_filter,
                date_from=date_from,
                date_to=date_to,
            ),
            item._cross_filter_domain(cross_filter),
        ])
        measure = item.measure_field_id.name if item.measure_field_id else 'id'
        agg = item.aggregation or 'count'
        date_label = 'custom' if (date_from or date_to) else item._effective_date_filter(global_date_filter)

        def _store(result):
            if cache_key and ttl:
                Cache.set_json(cache_key, result, ttl)
            return result

        if item.item_type == 'list':
            order = item.sort or 'id desc'
            fields_list = ['display_name']
            if item.measure_field_id:
                fields_list.append(item.measure_field_id.name)
            if item.date_field_id:
                fields_list.append(item.date_field_id.name)
            records = Model.search_read(domain, fields=fields_list, limit=item.limit or 12, order=order)
            return _store({'type': 'list', 'records': records, 'name': item.name, 'date_filter': date_label})

        if item.item_type == 'pivot':
            return _store(item._data_from_pivot(
                Model, domain, measure, agg, date_label,
            ))

        chart_types = (
            'bar', 'hbar', 'line', 'pie', 'doughnut', 'area', 'radar',
            'funnel', 'scatter', 'bullet', 'waterfall', 'polar', 'flower',
        )
        if item.groupby_field_id and item.item_type in chart_types:
            groupby = item.groupby_field_id.name
            # Agrégation temporelle pour les champs date/datetime
            if item.groupby_field_id.ttype in ('date', 'datetime'):
                groupby = f'{groupby}:week'
            groups = Model.read_group(
                domain,
                [measure] if measure != 'id' else [],
                [groupby],
                limit=item.limit or 12,
                orderby=f'{groupby} asc' if ':week' in groupby or ':month' in groupby or ':day' in groupby
                else (f'{measure} desc' if measure != 'id' and agg != 'count' else False),
            )
            labels, values, raw_keys = [], [], []
            for group in groups:
                labels.append(item._format_label(group.get(groupby)))
                raw_keys.append(group.get(groupby))
                if agg == 'count':
                    values.append(group.get(f'{groupby}_count') or group.get('__count') or 0)
                else:
                    values.append(group.get(measure) or 0)
            return _store({
                'type': item.item_type,
                'labels': labels,
                'values': values,
                'raw_keys': raw_keys,
                'name': item.name,
                'subtitle': item.groupby_field_id.field_description,
                'show_values': item.show_values,
                'target': item.target_value,
                'date_filter': date_label,
                'drillable': True,
                'cross_field': item.groupby_field_id.name,
                'cross_model': item.model_name,
            })

        value = item._aggregate(Model, domain, measure, agg)
        compare = item._compute_compare(
            Model, measure, agg,
            global_date_filter=global_date_filter,
            date_from=date_from,
            date_to=date_to,
        )
        sparkline = []
        if item.item_type in ('tile', 'bullet'):
            sparkline = item._compute_sparkline(Model, measure, agg)
            # Enrichir avec historique long terme si disponible
            hist = self.env['merka.dashboard.history'].get_series(item.id, days=30)
            if hist and len(hist) >= 3:
                sparkline = [h['value'] for h in hist]
        target = item.target_value or 0
        progress = round(min(100.0, (float(value) / target) * 100.0), 1) if target else None
        anomaly = None
        if sparkline and len(sparkline) >= 4:
            window = sparkline[-7:]
            baseline = sum(window) / float(len(window))
            if baseline:
                delta_pct = round(((float(value) - baseline) / abs(baseline)) * 100.0, 1)
                threshold = self.env['merka.dashboard.config'].get_config().anomaly_threshold_pct or 15.0
                if abs(delta_pct) >= float(threshold):
                    anomaly = {
                        'pct': delta_pct,
                        'direction': 'up' if delta_pct > 0 else 'down',
                        'baseline': round(baseline, 2),
                        'threshold': threshold,
                        'label': _('Anomalie %+0.1f %% vs moy. 7j') % delta_pct,
                    }
        return _store({
            'type': 'tile' if item.item_type in ('tile', 'bullet') else item.item_type,
            'value': value,
            'name': item.name,
            'target': item.target_value,
            'progress_pct': progress,
            'unit': item.unit_label or '',
            'trend': compare.get('trend'),
            'previous': compare.get('previous'),
            'sparkline': sparkline,
            'anomaly': anomaly,
            'show_values': item.show_values,
            'date_filter': date_label,
            'labels': [item.name],
            'values': [value],
            'note': item.note or '',
        })
