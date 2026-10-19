# -*- coding: utf-8 -*-
import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class MerkaDashboardReportWizard(models.TransientModel):
    _name = 'merka.dashboard.report.wizard'
    _description = 'Générer / envoyer un rapport Merka'

    dashboard_id = fields.Many2one('merka.dashboard', required=True, string='Tableau')
    date_filter = fields.Selection(
        [
            ('none', 'Tous'),
            ('today', "Aujourd'hui"),
            ('last_7', '7 derniers jours'),
            ('last_30', '30 derniers jours'),
            ('last_90', '90 derniers jours'),
            ('this_month', 'Mois en cours'),
            ('last_month', 'Mois précédent'),
            ('this_year', "Année en cours"),
        ],
        default='last_30',
        required=True,
        string='Période',
    )
    partner_ids = fields.Many2many('res.partner', string='Destinataires email')
    include_charts = fields.Boolean(string='Inclure aperçu graphiques', default=True)
    include_lists = fields.Boolean(string='Inclure listes', default=True)
    send_email = fields.Boolean(string='Envoyer par email', default=False)

    def action_generate(self):
        self.ensure_one()
        html = self.dashboard_id._build_report_html(
            global_date_filter=self.date_filter if self.date_filter != 'none' else None,
            include_charts=self.include_charts,
            include_lists=self.include_lists,
        )
        attachment = self.env['ir.attachment'].create({
            'name': f"Rapport_{self.dashboard_id.name}.html",
            'type': 'binary',
            'datas': base64.b64encode(html.encode('utf-8')),
            'mimetype': 'text/html',
            'res_model': 'merka.dashboard',
            'res_id': self.dashboard_id.id,
        })
        self.env['merka.dashboard.export'].create({
            'name': _('Rapport %s') % self.dashboard_id.name,
            'dashboard_id': self.dashboard_id.id,
            'export_type': 'pdf',
            'attachment_id': attachment.id,
            'note': _('Période: %s') % self.date_filter,
        })
        if self.send_email:
            emails = self.partner_ids.filtered('email').mapped('email')
            if not emails:
                raise UserError(_('Ajoutez au moins un destinataire avec email.'))
            mail = self.env['mail.mail'].sudo().create({
                'subject': _('[Rapport Merka] %s') % self.dashboard_id.name,
                'body_html': html,
                'email_to': ','.join(emails),
                'attachment_ids': [(4, attachment.id)],
            })
            mail.send()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
