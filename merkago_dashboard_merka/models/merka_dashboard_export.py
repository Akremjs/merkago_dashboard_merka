# -*- coding: utf-8 -*-
from odoo import fields, models


class MerkaDashboardExport(models.Model):
    _name = 'merka.dashboard.export'
    _description = 'Historique export Dashboard Merka'
    _order = 'create_date desc'

    name = fields.Char(required=True)
    dashboard_id = fields.Many2one('merka.dashboard', ondelete='set null')
    export_type = fields.Selection(
        [
            ('json', 'JSON (TB complet)'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
            ('pdf', 'PDF'),
            ('png', 'PNG'),
        ],
        required=True,
        default='json',
    )
    attachment_id = fields.Many2one('ir.attachment', string='Fichier', ondelete='set null')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    note = fields.Char()
