# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    merka_home_dashboard_id = fields.Many2one(
        'merka.dashboard',
        string='Dashboard Merka (accueil)',
        help='Si défini, peut servir d’écran de pilotage favori.',
    )
    merka_ai_mode = fields.Selection(
        [
            ('local', 'Local (Merka)'),
            ('auto', 'Auto (local + cloud)'),
            ('openai', 'OpenAI'),
            ('azure', 'Azure OpenAI'),
            ('custom', 'Endpoint custom'),
        ],
        string='Mode IA Merka',
        default='local',
        help='Choix personnel du moteur IA dans le chat Merka.',
    )

    def get_merka_ai_mode(self):
        self.ensure_one()
        return self.merka_ai_mode or 'local'

    @api.model
    def set_merka_ai_mode(self, mode):
        """Enregistre le mode IA de l'utilisateur courant."""
        allowed = {'local', 'auto', 'openai', 'azure', 'custom'}
        mode = (mode or 'local').strip()
        if mode not in allowed:
            mode = 'local'
        self.env.user.sudo().write({'merka_ai_mode': mode})
        return {'ok': True, 'mode': mode}
