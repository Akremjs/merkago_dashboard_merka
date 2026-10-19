# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MerkaDashboardConfig(models.Model):
    _name = 'merka.dashboard.config'
    _description = 'Configuration Merkago Dashboard Merka'

    name = fields.Char(default='Configuration Dashboard Merka', required=True)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    ai_enabled = fields.Boolean(
        string='Activer l’IA cloud',
        default=False,
        help='Autorise les appels vers des IA externes (clés ci-dessous). Le mode local reste toujours dispo.',
    )
    ai_allow_user_choice = fields.Boolean(
        string='Laisser choisir le mode IA',
        default=True,
        help='Chaque utilisateur choisit Local / Auto / OpenAI / Azure / Custom dans le chat.',
    )
    ai_provider = fields.Selection(
        [
            ('none', 'Aucun (défaut)'),
            ('openai', 'OpenAI'),
            ('azure', 'Azure OpenAI'),
            ('custom', 'Endpoint custom'),
        ],
        default='none',
        required=True,
        help='Fournisseur par défaut (mode Auto).',
    )
    ai_api_key = fields.Char(
        string='Clé API (legacy / défaut)',
        groups='merkago_dashboard_merka.group_merka_dashboard_manager',
        help='Utilisée si la clé du fournisseur dédié est vide.',
    )
    ai_endpoint = fields.Char(
        string='Endpoint (legacy / défaut)',
        help='Utilisé si l’endpoint du fournisseur dédié est vide.',
    )
    # ——— Environnement multi-IA (sync) ———
    ai_openai_key = fields.Char(
        string='OpenAI · clé',
        groups='merkago_dashboard_merka.group_merka_dashboard_manager',
    )
    ai_openai_endpoint = fields.Char(
        string='OpenAI · endpoint',
        default='https://api.openai.com/v1/chat/completions',
        help='Laisser le défaut OpenAI, ou un proxy compatible.',
    )
    ai_openai_model = fields.Char(
        string='OpenAI · modèle',
        default='gpt-4o-mini',
    )
    ai_azure_key = fields.Char(
        string='Azure · clé',
        groups='merkago_dashboard_merka.group_merka_dashboard_manager',
    )
    ai_azure_endpoint = fields.Char(
        string='Azure · endpoint',
        help='URL complète du déploiement chat/completions Azure.',
    )
    ai_custom_key = fields.Char(
        string='Custom · clé',
        groups='merkago_dashboard_merka.group_merka_dashboard_manager',
    )
    ai_custom_endpoint = fields.Char(
        string='Custom · endpoint',
        help='Proxy LiteLLM, Ollama gateway, Mistral, Claude via compat OpenAI…',
    )
    ai_custom_label = fields.Char(
        string='Custom · libellé',
        default='Custom',
        help='Nom affiché dans le sélecteur utilisateur (ex: Ollama, Mistral).',
    )
    default_theme = fields.Selection(
        [
            ('dark', 'Sombre analytics'),
            ('light', 'Clair professionnel'),
            ('ocean', 'Océan'),
            ('contrast', 'Haut contraste'),
        ],
        default='dark',
        required=True,
    )
    default_refresh_seconds = fields.Integer(
        string='Refresh auto (secondes)',
        default=0,
        help='0 = désactivé. Ex: 60 pour actualiser chaque minute.',
    )
    allow_sql_kpi = fields.Boolean(
        string='Autoriser KPI SQL (lecture seule)',
        default=False,
    )
    auto_backup_exports = fields.Boolean(
        string='Backup auto des exports',
        default=True,
    )
    auto_detect_modules = fields.Boolean(
        string='Détection auto des apps Odoo',
        default=True,
        help=(
            "À l'installation de Merka (et quand une nouvelle app est installée), "
            "crée automatiquement les dashboards Ventes/CRM/Stock… selon les modules présents."
        ),
    )
    cache_ttl_seconds = fields.Integer(
        string='Cache agrégats (secondes)',
        default=60,
        help='0 = désactivé. Cache court des calculs KPI pour alléger la base.',
    )
    history_enabled = fields.Boolean(
        string='Historique KPI quotidien',
        default=True,
        help='Snapshot nocturne des tuiles pour courbes long terme.',
    )
    force_rtl = fields.Boolean(
        string='Forcer RTL',
        default=False,
        help='Interface droite-à-gauche (arabe, hébreu…). Sinon détecté via la langue utilisateur.',
    )
    stream_enabled = fields.Boolean(
        string='Streaming live',
        default=True,
        help='Notifie les dashboards ouverts via le bus Odoo quand les données changent.',
    )
    anomaly_threshold_pct = fields.Float(
        string='Seuil anomalie (%)',
        default=15.0,
        help='Écart min. vs moyenne 7 jours pour signaler une anomalie (ex: 15).',
    )
    ai_multi_generate = fields.Boolean(
        string='IA : pack multi-widgets',
        default=True,
        help='Un mot-clé crée tuile + courbe + répartition (sinon 1 seul widget).',
    )
    last_auto_setup = fields.Datetime(
        string='Dernière synchro packs',
        readonly=True,
    )

    _sql_constraints = [
        (
            'company_uniq',
            'unique(company_id)',
            'Une seule configuration par société.',
        ),
    ]

    @api.model
    def get_config(self, company=None):
        company = company or self.env.company
        config = self.search([('company_id', '=', company.id)], limit=1)
        if not config:
            config = self.create({'company_id': company.id})
        return config

    def get_public_settings(self):
        self.ensure_one()
        return {
            'theme': self.default_theme,
            'refresh_seconds': self.default_refresh_seconds or 0,
            'ai_enabled': bool(self.ai_enabled),
            'ai_allow_user_choice': bool(self.ai_allow_user_choice),
            'allow_sql_kpi': bool(self.allow_sql_kpi),
            'auto_detect_modules': bool(self.auto_detect_modules),
            'cache_ttl_seconds': self.cache_ttl_seconds or 0,
            'history_enabled': bool(self.history_enabled),
            'force_rtl': bool(self.force_rtl),
            'stream_enabled': bool(self.stream_enabled),
            'anomaly_threshold_pct': self.anomaly_threshold_pct or 15.0,
            'ai_multi_generate': bool(self.ai_multi_generate),
        }

    def _ai_provider_ready(self, provider):
        """True si le fournisseur a assez de config pour un appel HTTP."""
        self.ensure_one()
        provider = (provider or '').strip()
        if provider == 'openai':
            key = (self.ai_openai_key or self.ai_api_key or '').strip()
            return bool(key)
        if provider == 'azure':
            key = (self.ai_azure_key or self.ai_api_key or '').strip()
            endpoint = (self.ai_azure_endpoint or self.ai_endpoint or '').strip()
            return bool(key and endpoint)
        if provider == 'custom':
            key = (self.ai_custom_key or self.ai_api_key or '').strip()
            endpoint = (self.ai_custom_endpoint or self.ai_endpoint or '').strip()
            return bool(key and endpoint)
        return False

    def get_available_ai_modes(self):
        """Modes proposés aux utilisateurs (sans secrets)."""
        self.ensure_one()
        modes = [
            {'value': 'local', 'label': 'Local', 'ready': True},
            {
                'value': 'auto',
                'label': 'Auto (local + cloud)',
                'ready': bool(self.ai_enabled and self.ai_provider not in (False, 'none')),
            },
        ]
        if self.ai_enabled:
            if self._ai_provider_ready('openai') or self.ai_provider == 'openai':
                modes.append({
                    'value': 'openai',
                    'label': 'OpenAI',
                    'ready': self._ai_provider_ready('openai'),
                })
            if self._ai_provider_ready('azure') or self.ai_provider == 'azure':
                modes.append({
                    'value': 'azure',
                    'label': 'Azure',
                    'ready': self._ai_provider_ready('azure'),
                })
            custom_ready = self._ai_provider_ready('custom')
            if custom_ready or self.ai_provider == 'custom':
                modes.append({
                    'value': 'custom',
                    'label': self.ai_custom_label or 'Custom',
                    'ready': custom_ready,
                })
        # Toujours au moins local
        if not self.ai_allow_user_choice:
            default = self.ai_provider if self.ai_enabled and self.ai_provider not in (False, 'none') else 'local'
            return [m for m in modes if m['value'] in ('local', default, 'auto')]
        return modes

    def resolve_ai_credentials(self, provider):
        """Retourne dict provider/key/endpoint/model pour un appel."""
        self.ensure_one()
        provider = (provider or self.ai_provider or 'none').strip()
        if provider in (False, 'none', 'local', 'auto'):
            provider = self.ai_provider if self.ai_provider not in (False, 'none') else 'none'
        if provider == 'openai':
            return {
                'provider': 'openai',
                'key': (self.ai_openai_key or self.ai_api_key or '').strip(),
                'endpoint': (self.ai_openai_endpoint or self.ai_endpoint or '').strip()
                    or 'https://api.openai.com/v1/chat/completions',
                'model': (self.ai_openai_model or 'gpt-4o-mini').strip(),
            }
        if provider == 'azure':
            return {
                'provider': 'azure',
                'key': (self.ai_azure_key or self.ai_api_key or '').strip(),
                'endpoint': (self.ai_azure_endpoint or self.ai_endpoint or '').strip(),
                'model': '',
            }
        if provider == 'custom':
            return {
                'provider': 'custom',
                'key': (self.ai_custom_key or self.ai_api_key or '').strip(),
                'endpoint': (self.ai_custom_endpoint or self.ai_endpoint or '').strip(),
                'model': (self.ai_openai_model or 'gpt-4o-mini').strip(),
                'label': self.ai_custom_label or 'Custom',
            }
        return {'provider': 'none', 'key': '', 'endpoint': '', 'model': ''}

    def action_resync_packs(self):
        """Bouton config : rescanner les apps Odoo et créer les packs manquants."""
        return self.env['merka.dashboard'].action_resync_packs()

    def action_backfill_history(self):
        """Bouton config : remplir l'historique KPI (14 jours)."""
        result = self.env['merka.dashboard.history'].action_backfill_history(days=14)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Historique Merka',
                'message': (
                    f"Backfill {result.get('days')}j : "
                    f"+{result.get('created')} créés, {result.get('updated')} maj "
                    f"({result.get('tiles')} tuiles)."
                ),
                'type': 'success',
                'sticky': False,
            },
        }
