# -*- coding: utf-8 -*-
import base64
import json

from odoo import _, fields, models
from odoo.exceptions import UserError


class MerkaDashboardImportWizard(models.TransientModel):
    _name = 'merka.dashboard.import.wizard'
    _description = 'Import Dashboard Merka'

    data_file = fields.Binary(required=True)
    data_filename = fields.Char()
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    def action_import(self):
        self.ensure_one()
        if not self.data_file:
            raise UserError(_('Veuillez sélectionner un fichier JSON.'))
        try:
            payload = json.loads(base64.b64decode(self.data_file).decode('utf-8'))
        except Exception as exc:
            raise UserError(_('Fichier JSON invalide : %s') % exc) from exc

        dashboard = self.env['merka.dashboard'].create({
            'name': payload.get('name') or 'Importé',
            'pack_code': payload.get('pack_code') or 'custom',
            'sequence': payload.get('sequence') or 10,
            'description': payload.get('description') or '',
            'company_id': self.company_id.id,
        })
        IrModel = self.env['ir.model']
        IrField = self.env['ir.model.fields']
        for raw in payload.get('items') or []:
            model = IrModel.search([('model', '=', raw.get('model'))], limit=1)
            if not model:
                continue
            vals = {
                'name': raw.get('name') or 'Élément',
                'dashboard_id': dashboard.id,
                'sequence': raw.get('sequence') or 10,
                'item_type': raw.get('item_type') or 'tile',
                'model_id': model.id,
                'aggregation': raw.get('aggregation') or 'count',
                'domain': raw.get('domain') or '[]',
                'limit': raw.get('limit') or 80,
                'sort': raw.get('sort') or '',
                'date_filter': raw.get('date_filter') or 'none',
                'layout_x': raw.get('layout_x') or 0,
                'layout_y': raw.get('layout_y') or 0,
                'layout_w': raw.get('layout_w') or 3,
                'layout_h': raw.get('layout_h') or 2,
                'target_value': raw.get('target_value') or 0,
                'unit_label': raw.get('unit_label') or '',
            }
            if raw.get('measure_field'):
                field = IrField.search([
                    ('model_id', '=', model.id),
                    ('name', '=', raw['measure_field']),
                ], limit=1)
                if field:
                    vals['measure_field_id'] = field.id
            if raw.get('date_field'):
                field = IrField.search([
                    ('model_id', '=', model.id),
                    ('name', '=', raw['date_field']),
                ], limit=1)
                if field:
                    vals['date_field_id'] = field.id
            if raw.get('groupby_field'):
                field = IrField.search([
                    ('model_id', '=', model.id),
                    ('name', '=', raw['groupby_field']),
                ], limit=1)
                if field:
                    vals['groupby_field_id'] = field.id
            self.env['merka.dashboard.item'].create(vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'merka.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'current',
        }
