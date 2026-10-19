# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MerkaDashboardAlert(models.Model):
    _name = 'merka.dashboard.alert'
    _description = 'Alerte seuil Dashboard Merka'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    dashboard_id = fields.Many2one('merka.dashboard', ondelete='cascade')
    item_id = fields.Many2one('merka.dashboard.item', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='item_id.company_id', store=True)
    threshold = fields.Float(required=True, string='Seuil')
    operator = fields.Selection(
        [
            ('gt', '>'),
            ('gte', '≥'),
            ('lt', '<'),
            ('lte', '≤'),
            ('eq', '='),
        ],
        default='gt',
        required=True,
    )
    notify_user_ids = fields.Many2many('res.users', string='Notifier')
    last_value = fields.Float(readonly=True)
    last_triggered = fields.Datetime(readonly=True)
    mail_template_body = fields.Text(
        default='Alerte Dashboard Merka : %(name)s = %(value)s (seuil %(op)s %(threshold)s)',
    )

    def _compare(self, value):
        self.ensure_one()
        op = self.operator
        t = self.threshold
        if op == 'gt':
            return value > t
        if op == 'gte':
            return value >= t
        if op == 'lt':
            return value < t
        if op == 'lte':
            return value <= t
        return value == t

    @api.model
    def _cron_check_alerts(self):
        alerts = self.search([('active', '=', True)])
        Item = self.env['merka.dashboard.item']
        for alert in alerts:
            try:
                data = Item.get_item_data(alert.item_id.id)
                value = float(data.get('value') or 0)
                if data.get('type') not in ('tile', None) and data.get('values'):
                    value = float(sum(data.get('values') or [0]))
                alert.last_value = value
                if alert._compare(value):
                    # Anti-spam : max 1 alerte / heure pour le même seuil
                    last = alert.last_triggered
                    now = fields.Datetime.now()
                    if last and (now - last).total_seconds() < 3600:
                        continue
                    alert.last_triggered = now
                    users = alert.notify_user_ids or alert.item_id.dashboard_id.create_uid
                    body = (alert.mail_template_body or '') % {
                        'name': alert.name,
                        'value': value,
                        'op': alert.operator,
                        'threshold': alert.threshold,
                    }
                    Mail = self.env['mail.mail'].sudo()
                    for user in users:
                        if not user.partner_id:
                            continue
                        dash = alert.item_id.dashboard_id
                        dash.message_post(
                            body=body,
                            partner_ids=[user.partner_id.id],
                            subtype_xmlid='mail.mt_comment',
                        )
                        # Activité Odoo
                        try:
                            dash.activity_schedule(
                                'mail.mail_activity_data_todo',
                                user_id=user.id,
                                summary=alert.name,
                                note=body,
                            )
                        except Exception:
                            pass
                        # E-mail réel
                        email = user.email or user.partner_id.email
                        if email:
                            Mail.create({
                                'subject': f'[Merka] {alert.name}',
                                'body_html': f'<p>{body}</p>',
                                'email_to': email,
                                'auto_delete': True,
                            }).send()
            except Exception:
                continue
