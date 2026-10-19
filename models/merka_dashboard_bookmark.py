# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MerkaDashboardBookmark(models.Model):
    _name = 'merka.dashboard.bookmark'
    _description = 'Signet de vue Merka'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
        index=True,
    )
    dashboard_id = fields.Many2one(
        'merka.dashboard',
        required=True,
        ondelete='cascade',
        index=True,
    )
    date_filter = fields.Char(default='last_30')
    date_from = fields.Date()
    date_to = fields.Date()
    company_id = fields.Many2one('res.company')
    cross_filter_json = fields.Text(
        help='JSON du filtre croisé actif au moment du signet.',
    )

    @api.model
    def list_for_user(self, dashboard_id=None):
        domain = [('user_id', '=', self.env.uid)]
        if dashboard_id:
            domain.append(('dashboard_id', '=', int(dashboard_id)))
        rows = self.search(domain, limit=40)
        return [{
            'id': b.id,
            'name': b.name,
            'dashboard_id': b.dashboard_id.id,
            'dashboard_name': b.dashboard_id.name,
            'date_filter': b.date_filter or 'last_30',
            'date_from': b.date_from.isoformat() if b.date_from else False,
            'date_to': b.date_to.isoformat() if b.date_to else False,
            'company_id': b.company_id.id if b.company_id else False,
            'cross_filter': json.loads(b.cross_filter_json) if b.cross_filter_json else None,
        } for b in rows]

    @api.model
    def save_bookmark(self, name, dashboard_id, date_filter=None, date_from=None,
                      date_to=None, company_id=None, cross_filter=None):
        name = (name or '').strip()
        if not name:
            raise UserError(_('Nom du signet obligatoire.'))
        if not dashboard_id:
            raise UserError(_('Dashboard manquant.'))
        vals = {
            'name': name,
            'dashboard_id': int(dashboard_id),
            'user_id': self.env.uid,
            'date_filter': date_filter or 'last_30',
            'date_from': date_from or False,
            'date_to': date_to or False,
            'company_id': int(company_id) if company_id else False,
            'cross_filter_json': json.dumps(cross_filter) if cross_filter else False,
        }
        existing = self.search([
            ('user_id', '=', self.env.uid),
            ('dashboard_id', '=', int(dashboard_id)),
            ('name', '=', name),
        ], limit=1)
        if existing:
            existing.write(vals)
            return existing.id
        return self.create(vals).id

    def action_delete_bookmark(self):
        self.ensure_one()
        if self.user_id != self.env.user and not self.env.user.has_group(
            'merkago_dashboard_merka.group_merka_dashboard_manager'
        ):
            raise UserError(_('Vous ne pouvez supprimer que vos signets.'))
        self.unlink()
        return True
