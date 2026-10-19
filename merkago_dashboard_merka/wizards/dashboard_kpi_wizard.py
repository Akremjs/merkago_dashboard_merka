# -*- coding: utf-8 -*-
"""Assistant Nouveau KPI en 3 étapes."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MerkaDashboardKpiWizard(models.TransientModel):
    _name = 'merka.dashboard.kpi.wizard'
    _description = 'Assistant Nouveau KPI Merka'

    step = fields.Selection(
        [
            ('1', '1. Tableau'),
            ('2', '2. Source'),
            ('3', '3. Affichage'),
        ],
        default='1',
        required=True,
    )
    dashboard_id = fields.Many2one(
        'merka.dashboard',
        string='Tableau',
        required=True,
        default=lambda self: self.env.context.get('default_dashboard_id'),
    )
    name = fields.Char(string='Nom de l’indicateur')
    code = fields.Char(string='Code (formules)', help='Ex: ca, commandes — pour les formules {ca}')
    model_id = fields.Many2one('ir.model', string='Modèle Odoo', ondelete='cascade')
    model_name = fields.Char(related='model_id.model', readonly=True)
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
    aggregation = fields.Selection(
        [
            ('count', 'Nombre'),
            ('sum', 'Somme'),
            ('avg', 'Moyenne'),
        ],
        default='count',
        required=True,
    )
    item_type = fields.Selection(
        [
            ('tile', 'Tuile KPI'),
            ('bar', 'Barres'),
            ('hbar', 'Barres horizontales'),
            ('line', 'Courbe'),
            ('area', 'Aires'),
            ('pie', 'Camembert'),
            ('doughnut', 'Anneau'),
            ('polar', 'Aires polaires'),
            ('flower', 'Fleur'),
            ('list', 'Liste'),
            ('pivot', 'Tableau croisé'),
            ('funnel', 'Entonnoir'),
            ('radar', 'Radar'),
        ],
        default='tile',
        required=True,
    )
    groupby_field_id = fields.Many2one(
        'ir.model.fields',
        string='Lignes / Grouper par',
        domain="[('model_id', '=', model_id)]",
    )
    col_groupby_field_id = fields.Many2one(
        'ir.model.fields',
        string='Colonnes (tableau croisé)',
        domain="[('model_id', '=', model_id)]",
    )
    domain = fields.Char(default='[]', string='Filtre (domaine)')
    date_filter = fields.Selection(
        [
            ('none', 'Aucun'),
            ('last_7', '7 jours'),
            ('last_30', '30 jours'),
            ('this_month', 'Ce mois'),
            ('this_year', 'Cette année'),
        ],
        default='last_30',
    )
    unit_label = fields.Char(string='Unité')
    target_value = fields.Float(string='Objectif')
    add_to_dictionary = fields.Boolean(
        string='Aussi au dictionnaire KPI',
        default=True,
    )

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.measure_field_id = False
        self.date_field_id = False
        self.groupby_field_id = False
        if self.model_id and not self.name:
            self.name = self.model_id.name

    @api.onchange('aggregation')
    def _onchange_aggregation(self):
        if self.aggregation == 'count':
            self.measure_field_id = False

    def action_next(self):
        self.ensure_one()
        if self.step == '1':
            if not self.dashboard_id:
                raise UserError(_('Choisissez un tableau.'))
            self.step = '2'
        elif self.step == '2':
            if not self.model_id:
                raise UserError(_('Choisissez un modèle Odoo.'))
            if self.aggregation != 'count' and not self.measure_field_id:
                raise UserError(_('Choisissez une mesure pour la somme / moyenne.'))
            if not self.name:
                self.name = self.model_id.name
            self.step = '3'
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        if self.step == '3':
            self.step = '2'
        elif self.step == '2':
            self.step = '1'
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'views': [(False, 'form')],
        }

    def action_create(self):
        self.ensure_one()
        if not self.dashboard_id or not self.model_id:
            raise UserError(_('Tableau et modèle obligatoires.'))
        if self.item_type == 'pivot':
            if not self.groupby_field_id or not self.col_groupby_field_id:
                raise UserError(_('Tableau croisé : choisissez Lignes et Colonnes.'))
        name = (self.name or '').strip() or self.model_id.name
        code = (self.code or '').strip() or False
        vals = {
            'dashboard_id': self.dashboard_id.id,
            'name': name,
            'code': code,
            'item_type': self.item_type,
            'data_source': 'odoo',
            'model_id': self.model_id.id,
            'aggregation': self.aggregation,
            'domain': self.domain or '[]',
            'date_filter': self.date_filter or 'none',
            'unit_label': self.unit_label or False,
            'target_value': self.target_value or 0,
            'layout_w': 3 if self.item_type == 'tile' else (12 if self.item_type == 'pivot' else 6),
            'layout_h': 2 if self.item_type != 'pivot' else 3,
        }
        if self.measure_field_id:
            vals['measure_field_id'] = self.measure_field_id.id
        if self.date_field_id:
            vals['date_field_id'] = self.date_field_id.id
        if self.groupby_field_id and self.item_type != 'tile':
            vals['groupby_field_id'] = self.groupby_field_id.id
        if self.col_groupby_field_id and self.item_type == 'pivot':
            vals['col_groupby_field_id'] = self.col_groupby_field_id.id

        item = self.env['merka.dashboard.item'].create(vals)

        if self.add_to_dictionary:
            pack = self.dashboard_id.pack_code or 'other'
            if pack == 'custom':
                pack = 'other'
            kpi_code = code or ('kpi_%s' % item.id)
            if pack != 'other' and not str(kpi_code).startswith(pack):
                kpi_code = '%s_%s' % (pack, kpi_code)
            Kpi = self.env['merka.dashboard.kpi']
            if not Kpi.search([('code', '=', kpi_code)], limit=1):
                kpi = Kpi.create({
                    'name': name,
                    'code': kpi_code,
                    'pack_code': pack if pack in dict(Kpi._fields['pack_code'].selection) else 'other',
                    'model_id': self.model_id.id,
                    'aggregation': self.aggregation,
                    'measure_field': self.measure_field_id.name if self.measure_field_id else False,
                    'date_field': self.date_field_id.name if self.date_field_id else False,
                    'domain': self.domain or '[]',
                    'formula_unit': self.unit_label or False,
                    'auto_generated': False,
                })
                item.kpi_id = kpi.id

        return self.dashboard_id.action_open_dashboard()
