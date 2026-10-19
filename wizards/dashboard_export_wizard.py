# -*- coding: utf-8 -*-
import base64
import json

from odoo import fields, models


class MerkaDashboardExportWizard(models.TransientModel):
    _name = 'merka.dashboard.export.wizard'
    _description = 'Export Dashboard Merka'

    dashboard_id = fields.Many2one('merka.dashboard', required=True)
    export_type = fields.Selection(
        [('json', 'JSON (TB complet)')],
        default='json',
        required=True,
    )
    data_file = fields.Binary(readonly=True)
    data_filename = fields.Char(readonly=True)

    def action_export(self):
        self.ensure_one()
        dashboard = self.dashboard_id
        payload = {
            'name': dashboard.name,
            'pack_code': dashboard.pack_code,
            'sequence': dashboard.sequence,
            'description': dashboard.description or '',
            'items': [],
        }
        for item in dashboard.item_ids:
            payload['items'].append({
                'name': item.name,
                'sequence': item.sequence,
                'item_type': item.item_type,
                'model': item.model_name,
                'aggregation': item.aggregation,
                'domain': item.domain or '[]',
                'limit': item.limit,
                'sort': item.sort or '',
                'date_filter': item.date_filter,
                'layout_x': item.layout_x,
                'layout_y': item.layout_y,
                'layout_w': item.layout_w,
                'layout_h': item.layout_h,
                'measure_field': item.measure_field_id.name if item.measure_field_id else '',
                'date_field': item.date_field_id.name if item.date_field_id else '',
                'groupby_field': item.groupby_field_id.name if item.groupby_field_id else '',
                'target_value': item.target_value,
                'unit_label': item.unit_label or '',
            })
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        filename = f"{dashboard.name or 'dashboard'}.merka.json"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(content.encode('utf-8')),
            'mimetype': 'application/json',
            'res_model': 'merka.dashboard',
            'res_id': dashboard.id,
        })
        self.env['merka.dashboard.export'].create({
            'name': filename,
            'dashboard_id': dashboard.id,
            'export_type': 'json',
            'attachment_id': attachment.id,
            'note': 'Export assistant',
        })
        self.write({
            'data_file': attachment.datas,
            'data_filename': filename,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'merka.dashboard.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
