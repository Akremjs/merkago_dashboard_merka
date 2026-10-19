# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models


class MerkaDashboardSchedule(models.Model):
    _name = 'merka.dashboard.schedule'
    _description = 'Envoi planifié PDF Dashboard Merka'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    dashboard_id = fields.Many2one('merka.dashboard', required=True, ondelete='cascade')
    partner_ids = fields.Many2many('res.partner', string='Destinataires', required=True)
    interval = fields.Selection(
        [
            ('daily', 'Quotidien'),
            ('weekly', 'Hebdomadaire'),
            ('monthly', 'Mensuel'),
        ],
        default='weekly',
        required=True,
    )
    last_sent = fields.Datetime(readonly=True)
    company_id = fields.Many2one(related='dashboard_id.company_id', store=True)

    def _build_summary_html(self):
        self.ensure_one()
        return self.dashboard_id._build_report_html(
            global_date_filter='last_30',
            include_charts=True,
            include_lists=True,
        )

    def action_send_now(self):
        for rec in self:
            html = rec._build_summary_html()
            attachment = self.env['ir.attachment'].create({
                'name': f"Rapport_{rec.dashboard_id.name}.html",
                'type': 'binary',
                'datas': base64.b64encode(html.encode('utf-8')),
                'mimetype': 'text/html',
                'res_model': 'merka.dashboard',
                'res_id': rec.dashboard_id.id,
            })
            emails = rec.partner_ids.filtered('email').mapped('email')
            mail = self.env['mail.mail'].sudo().create({
                'subject': f"[Rapport Merka] {rec.dashboard_id.name}",
                'body_html': html,
                'email_to': ','.join(emails),
                'attachment_ids': [(4, attachment.id)],
            })
            mail.send()
            rec.last_sent = fields.Datetime.now()
            self.env['merka.dashboard.export'].create({
                'name': f"Schedule {rec.name}",
                'dashboard_id': rec.dashboard_id.id,
                'export_type': 'pdf',
                'attachment_id': attachment.id,
                'note': f'Envoi {rec.interval}',
            })
        return True

    @api.model
    def _cron_send_scheduled(self):
        now = fields.Datetime.now()
        for rec in self.search([('active', '=', True)]):
            if not rec.last_sent:
                rec.action_send_now()
                continue
            delta = now - rec.last_sent
            days = delta.total_seconds() / 86400.0
            need = (
                (rec.interval == 'daily' and days >= 1)
                or (rec.interval == 'weekly' and days >= 7)
                or (rec.interval == 'monthly' and days >= 28)
            )
            if need:
                rec.action_send_now()
