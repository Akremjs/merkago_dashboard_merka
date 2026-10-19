# -*- coding: utf-8 -*-
"""Chat IA Merka — discussion locale (intents) + option API."""
import json
import logging
import re

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Intent → patterns (ordre = priorité)
_INTENT_PATTERNS = [
    ('greet', re.compile(
        r'^\s*(bonjour|bonsoir|salut|hello|hi|hey|coucou|yo|slt|bjr)\s*[!.?]*\s*$',
        re.I,
    )),
    ('brief', re.compile(
        r'\b(briefing|résumé|resume|synthese|synthèse|ça va|ca va|status|état|etat|overview)\b',
        re.I,
    )),
    ('downs', re.compile(
        r'\b(baisse|baissent|problème|probleme|mauvais|down|recul|chute)\b',
        re.I,
    )),
    ('ups', re.compile(
        r'\b(hausse|monte|performe|top|meilleur|gagnant|up|progress)\b',
        re.I,
    )),
    ('anomalies', re.compile(
        r'\b(anomalie|anormal|alerte|écart|ecart|spike|outlier)\b',
        re.I,
    )),
    ('zeros', re.compile(
        r'\b(zéro|zero|vide|null|sans donnée|sans donnee|empty)\b',
        re.I,
    )),
    ('who', re.compile(
        r'\b(qui|what|quoi perform|répartition|repartition|leader)\b',
        re.I,
    )),
    ('filter_7', re.compile(r'\b(7\s*j|7\s*jours|semaine|last\s*7|7d)\b', re.I)),
    ('filter_30', re.compile(r'\b(30\s*j|30\s*jours|mois|last\s*30|30d)\b', re.I)),
    ('backfill', re.compile(r'\b(historique|backfill|history|snapshot)\b', re.I)),
    ('help', re.compile(r'\b(aide|help|comment|que faire|options)\b', re.I)),
]

_GENERATE_RE = re.compile(
    r'(?:crée|cree|créer|creer|génère|genere|ajoute|pack|indicateur)\s+(?:un\s+|des\s+|le\s+|la\s+)?'
    r'(?P<kw>ventes?|crm|factures?|stock|achats?|clients?|projets?|rh|hr|commandes?)',
    re.I,
)
_GENERATE_KW_RE = re.compile(
    r'^(?P<kw>ventes?|crm|factures?|stock|achats?|clients?|projets?|rh)\s*$',
    re.I,
)
_EXPLAIN_RE = re.compile(
    r'(?:explique|explain|détail|detail|analyse)\s+(?:le\s+|la\s+|l[\'’])?(?P<name>.+)',
    re.I,
)
_ALERT_RE = re.compile(
    r'(?:alerte|alert)\s+(?:sur\s+|pour\s+)?(?P<name>.+)',
    re.I,
)
_OPEN_RE = re.compile(
    r'(?:ouvre|ouvrir|open)\s+(?P<name>.+)',
    re.I,
)

_SUGGESTIONS = [
    'Briefing',
    'Où ça baisse ?',
    'Anomalies',
    'Crée ventes',
    'Période 7j',
]


class MerkaAiThread(models.Model):
    _name = 'merka.ai.thread'
    _description = 'Fil de discussion IA Merka'
    _order = 'write_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    dashboard_id = fields.Many2one(
        'merka.dashboard',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
        index=True,
    )
    message_ids = fields.One2many('merka.ai.message', 'thread_id', string='Messages')
    message_count = fields.Integer(compute='_compute_message_count')

    @api.depends('dashboard_id', 'user_id')
    def _compute_name(self):
        for row in self:
            dash = row.dashboard_id.name or 'Dashboard'
            user = row.user_id.name or ''
            row.name = f'IA · {dash} · {user}'

    def _compute_message_count(self):
        for row in self:
            row.message_count = len(row.message_ids)

    @api.model
    def get_or_create_for(self, dashboard_id):
        dash = self.env['merka.dashboard'].browse(int(dashboard_id))
        dash.ensure_one()
        thread = self.search([
            ('dashboard_id', '=', dash.id),
            ('user_id', '=', self.env.user.id),
        ], limit=1)
        if not thread:
            thread = self.create({'dashboard_id': dash.id, 'user_id': self.env.user.id})
        return thread

    def export_messages(self, limit=40):
        self.ensure_one()
        msgs = self.message_ids.sorted('id')[-limit:]
        return [m.to_chat_dict() for m in msgs]


class MerkaAiMessage(models.Model):
    _name = 'merka.ai.message'
    _description = 'Message chat IA Merka'
    _order = 'id asc'

    thread_id = fields.Many2one(
        'merka.ai.thread',
        required=True,
        ondelete='cascade',
        index=True,
    )
    role = fields.Selection(
        [('user', 'Utilisateur'), ('assistant', 'Assistant'), ('system', 'Système')],
        required=True,
        default='user',
    )
    body = fields.Text(required=True)
    source = fields.Char(default='local')
    intent = fields.Char()
    actions_json = fields.Text(default='[]')

    def to_chat_dict(self):
        self.ensure_one()
        try:
            actions = json.loads(self.actions_json or '[]')
        except Exception:
            actions = []
        return {
            'id': self.id,
            'role': self.role,
            'body': self.body,
            'source': self.source or 'local',
            'intent': self.intent or '',
            'actions': actions,
        }


class MerkaDashboard(models.Model):
    _inherit = 'merka.dashboard'

    def _ai_runtime(self):
        """Contexte mode IA utilisateur + config (sans secrets)."""
        config = self.env['merka.dashboard.config'].get_config()
        modes = config.get_available_ai_modes()
        mode_values = {m['value'] for m in modes}
        user_mode = self.env.user.get_merka_ai_mode()
        if user_mode not in mode_values:
            # fallback sûr
            if 'local' in mode_values:
                user_mode = 'local'
            else:
                user_mode = modes[0]['value'] if modes else 'local'
        allow_choice = bool(config.ai_allow_user_choice)
        if not allow_choice:
            if config.ai_enabled and config.ai_provider not in (False, 'none'):
                user_mode = 'auto'
            else:
                user_mode = 'local'
        return {
            'config': config,
            'mode': user_mode,
            'modes': modes,
            'ai_enabled': bool(config.ai_enabled),
            'allow_choice': allow_choice,
        }

    def action_ai_set_mode(self, mode):
        """Change le mode IA de l'utilisateur courant (depuis le chat)."""
        self.ensure_one()
        config = self.env['merka.dashboard.config'].get_config()
        if not config.ai_allow_user_choice:
            return {
                'ok': False,
                'error': _('Le choix du mode IA est verrouillé par l’administrateur.'),
                **self._ai_mode_payload(),
            }
        allowed = {m['value'] for m in config.get_available_ai_modes()}
        mode = (mode or 'local').strip()
        if mode not in allowed:
            return {
                'ok': False,
                'error': _('Mode IA non disponible.'),
                **self._ai_mode_payload(),
            }
        self.env['res.users'].set_merka_ai_mode(mode)
        return {'ok': True, **self._ai_mode_payload()}

    def _ai_mode_payload(self):
        rt = self._ai_runtime()
        return {
            'ai_mode': rt['mode'],
            'ai_modes': rt['modes'],
            'ai_enabled': rt['ai_enabled'],
            'ai_allow_user_choice': rt['allow_choice'],
        }

    def action_ai_chat_open(self):
        """Ouvre / charge le fil de discussion + message d'accueil si vide."""
        self.ensure_one()
        thread = self.env['merka.ai.thread'].get_or_create_for(self.id)
        msgs = thread.export_messages()
        if not msgs:
            welcome = self._ai_chat_welcome()
            self.env['merka.ai.message'].create({
                'thread_id': thread.id,
                'role': 'assistant',
                'body': welcome['body'],
                'source': 'local',
                'intent': 'welcome',
                'actions_json': json.dumps(welcome.get('actions') or []),
            })
            msgs = thread.export_messages()
        payload = {
            'thread_id': thread.id,
            'messages': msgs,
            'suggestions': list(_SUGGESTIONS),
        }
        payload.update(self._ai_mode_payload())
        return payload

    def _ai_chat_welcome(self):
        health = self.env['merka.dashboard.history'].history_health(days=14)
        rt = self._ai_runtime()
        mode_label = next(
            (m['label'] for m in rt['modes'] if m['value'] == rt['mode']),
            rt['mode'],
        )
        body = (
            f"Bonjour — je suis l'assistant Merka IA sur « {self.name} ».\n"
            f"Mode actuel : {mode_label}. Historique : {health.get('distinct_days')} j "
            f"(couverture {health.get('coverage_pct')} %).\n\n"
            "Posez une question ou choisissez une suggestion :\n"
            "• Briefing · Où ça baisse · Anomalies\n"
            "• Crée ventes / crm / stock\n"
            "• Période 7j · Explique [KPI]\n\n"
            "Changez le moteur IA via le sélecteur en haut du chat."
        )
        return {
            'body': body,
            'actions': [
                {'id': 'brief', 'label': 'Briefing', 'type': 'chat_preset', 'text': 'Briefing'},
                {'id': 'downs', 'label': 'Où ça baisse ?', 'type': 'chat_preset', 'text': 'Où ça baisse ?'},
                {'id': 'anom', 'label': 'Anomalies', 'type': 'chat_preset', 'text': 'Anomalies'},
            ],
        }

    def _ai_match_item_by_name(self, name):
        name = (name or '').strip().strip('?.!').strip()
        if not name:
            return self.env['merka.dashboard.item']
        items = self.item_ids.filtered(lambda i: i.active)
        exact = items.filtered(lambda i: (i.name or '').lower() == name.lower())
        if exact:
            return exact[:1]
        partial = items.filtered(lambda i: name.lower() in (i.name or '').lower())
        return partial[:1]

    def _ai_detect_intent(self, text):
        raw = (text or '').strip()
        if not raw:
            return 'brief', {}

        m = _GENERATE_RE.search(raw) or _GENERATE_KW_RE.match(raw)
        if m:
            return 'generate', {'keyword': m.group('kw')}

        m = _ALERT_RE.search(raw)
        if m:
            return 'alert', {'name': m.group('name').strip()}

        m = _OPEN_RE.search(raw)
        if m:
            return 'open', {'name': m.group('name').strip()}

        m = _EXPLAIN_RE.search(raw)
        if m:
            return 'explain', {'name': m.group('name').strip()}

        for intent, pattern in _INTENT_PATTERNS:
            if pattern.search(raw):
                return intent, {}

        # Mot-clé seul connu → generate
        low = raw.lower()
        for kw in ('ventes', 'vente', 'crm', 'factures', 'facture', 'stock', 'achats', 'achat'):
            if low == kw:
                return 'generate', {'keyword': kw}

        return 'unknown', {}

    def _ai_reply_from_intent(self, intent, params):
        """Exécute l'intent et renvoie body, actions, source, side_effects."""
        actions = []
        side = {}
        source = 'local'

        if intent == 'greet':
            welcome = self._ai_chat_welcome()
            return welcome['body'], welcome.get('actions') or [], source, side

        if intent in ('brief', 'welcome'):
            brief = self.action_ai_dashboard_briefing()
            return brief['explanation'], brief.get('actions') or [], source, side

        if intent == 'downs':
            brief = self.action_ai_dashboard_briefing('downs')
            return brief['explanation'], brief.get('actions') or [], source, side

        if intent in ('ups', 'who'):
            brief = self.action_ai_dashboard_briefing('who')
            return brief['explanation'], brief.get('actions') or [], source, side

        if intent == 'anomalies':
            brief = self.action_ai_dashboard_briefing('anomalies')
            return brief['explanation'], brief.get('actions') or [], source, side

        if intent == 'zeros':
            brief = self.action_ai_dashboard_briefing('zeros')
            return brief['explanation'], brief.get('actions') or [], source, side

        if intent == 'filter_7':
            side['date_filter'] = 'last_7'
            return (
                "J'applique la période **7 derniers jours** sur le tableau.",
                [{'id': 'f7', 'label': 'Actualiser 7j', 'type': 'filter', 'date_filter': 'last_7'}],
                source,
                side,
            )

        if intent == 'filter_30':
            side['date_filter'] = 'last_30'
            return (
                "J'applique la période **30 derniers jours** sur le tableau.",
                [{'id': 'f30', 'label': 'Actualiser 30j', 'type': 'filter', 'date_filter': 'last_30'}],
                source,
                side,
            )

        if intent == 'backfill':
            res = self.action_ai_backfill_history(14)
            return (
                f"Historique recalculé : +{res.get('created', 0)} snapshots "
                f"sur {res.get('days', 14)} j ({res.get('tiles', 0)} tuiles).",
                [
                    {'id': 'brief', 'label': 'Briefing', 'type': 'chat_preset', 'text': 'Briefing'},
                    {'id': 'anom', 'label': 'Anomalies', 'type': 'chat_preset', 'text': 'Anomalies'},
                ],
                source,
                {'reload': True},
            )

        if intent == 'generate':
            kw = params.get('keyword') or 'ventes'
            res = self.action_ai_generate_item(kw, 'bar', True)
            if not res.get('ok'):
                return res.get('error') or "Génération impossible.", [], source, side
            side['reload'] = True
            return (
                f"Pack créé sur le modèle « {res.get('model')} » :\n{res.get('name')}",
                [
                    {'id': 'brief', 'label': 'Briefing', 'type': 'chat_preset', 'text': 'Briefing'},
                    {'id': 'f30', 'label': 'Période 30j', 'type': 'filter', 'date_filter': 'last_30'},
                ],
                source,
                side,
            )

        if intent == 'explain':
            item = self._ai_match_item_by_name(params.get('name'))
            if not item:
                names = ', '.join(self.item_ids.filtered('active').mapped('name')[:8])
                return (
                    f"Je ne trouve pas « {params.get('name')} ».\nIndicateurs : {names}",
                    [],
                    source,
                    side,
                )
            res = self.action_ai_explain_item(item.id)
            return res.get('explanation') or '', res.get('actions') or [], res.get('source') or source, side

        if intent == 'alert':
            item = self._ai_match_item_by_name(params.get('name'))
            if not item:
                # fallback : premier KPI en baisse / zero via briefing
                tiles = self.item_ids.filtered(lambda i: i.active and i.item_type in ('tile', 'bullet'))[:1]
                item = tiles
            if not item:
                return "Aucun indicateur pour créer une alerte.", [], source, side
            res = self.action_ai_create_alert(item.id)
            if not res.get('ok'):
                return res.get('error') or "Alerte impossible.", [], source, side
            return (
                f"Alerte créée : {res.get('name')} "
                f"({res.get('operator')} {res.get('threshold')}).",
                [
                    {
                        'id': f"open_{item.id}",
                        'label': _('Ouvrir · %s') % item.name[:24],
                        'type': 'open_item',
                        'item_id': item.id,
                    },
                ],
                source,
                side,
            )

        if intent == 'open':
            item = self._ai_match_item_by_name(params.get('name'))
            if not item:
                return f"Indicateur « {params.get('name')} » introuvable.", [], source, side
            return (
                f"Ouverture de « {item.name} ».",
                [
                    {
                        'id': f"open_{item.id}",
                        'label': _('Ouvrir'),
                        'type': 'open_item',
                        'item_id': item.id,
                    },
                ],
                source,
                {'open_item_id': item.id},
            )

        if intent == 'help':
            return (
                "Je comprends notamment :\n"
                "• bonjour / salut (accueil)\n"
                "• briefing / où ça baisse / anomalies / qui performe / zéro\n"
                "• crée ventes|crm|stock|factures\n"
                "• explique [nom KPI] · alerte sur [KPI] · ouvre [KPI]\n"
                "• période 7j / 30j · historique\n\n"
                "Sans API = analyse locale. Activez l'IA cloud dans Configuration si besoin.",
                [
                    {'id': 'brief', 'label': 'Briefing', 'type': 'chat_preset', 'text': 'Briefing'},
                    {'id': 'gen', 'label': 'Crée ventes', 'type': 'chat_preset', 'text': 'Crée ventes'},
                ],
                source,
                side,
            )

        # unknown → briefing court + aide
        brief = self.action_ai_dashboard_briefing()
        body = (
            f"Je n'ai pas reconnu la demande. Voici le briefing :\n\n"
            f"{brief.get('explanation')}\n\n"
            "Astuce : tapez « aide » pour la liste des commandes."
        )
        actions = brief.get('actions') or []
        actions.append({'id': 'help', 'label': 'Aide', 'type': 'chat_preset', 'text': 'aide'})
        return body, actions, source, side

    def action_ai_chat(self, message, thread_id=None):
        """Envoie un message utilisateur → réponse assistant (persistée)."""
        self.ensure_one()
        text = (message or '').strip()
        if not text:
            return {'ok': False, 'error': _('Message vide')}

        Thread = self.env['merka.ai.thread']
        if thread_id:
            thread = Thread.browse(int(thread_id))
            if not thread.exists() or thread.dashboard_id.id != self.id:
                thread = Thread.get_or_create_for(self.id)
        else:
            thread = Thread.get_or_create_for(self.id)

        # Message user
        self.env['merka.ai.message'].create({
            'thread_id': thread.id,
            'role': 'user',
            'body': text,
            'source': 'user',
        })

        intent, params = self._ai_detect_intent(text)
        body, actions, source, side = self._ai_reply_from_intent(intent, params)

        # Cloud selon mode utilisateur
        rt = self._ai_runtime()
        config = rt['config']
        mode = rt['mode']
        use_cloud = False
        cloud_provider = None
        if mode == 'local':
            use_cloud = False
        elif mode in ('openai', 'azure', 'custom'):
            # Mode cloud dédié : API sur unknown (et explain déjà géré côté intent)
            use_cloud = intent == 'unknown' and config.ai_enabled
            cloud_provider = mode
        elif mode == 'auto':
            use_cloud = intent == 'unknown' and config.ai_enabled
            cloud_provider = config.ai_provider if config.ai_provider not in (False, 'none') else None

        if use_cloud and cloud_provider:
            prompt = (
                f"Dashboard Merka: {self.name}\n"
                f"Question utilisateur: {text}\n"
                f"Réponds en français, 3-5 phrases, orienté action BI."
            )
            remote = self._call_external_ai(config, prompt, provider=cloud_provider)
            if remote:
                body = remote
                source = cloud_provider
            elif mode in ('openai', 'azure', 'custom'):
                body = (
                    f"Le fournisseur « {cloud_provider} » n'a pas répondu. "
                    "Vérifiez la configuration (clé / endpoint) ou passez en mode Local.\n\n"
                    f"{body}"
                )
                source = f'{cloud_provider}_fallback'

        asst = self.env['merka.ai.message'].create({
            'thread_id': thread.id,
            'role': 'assistant',
            'body': body,
            'source': source,
            'intent': intent,
            'actions_json': json.dumps(actions or []),
        })

        result = {
            'ok': True,
            'thread_id': thread.id,
            'intent': intent,
            'user_message': {'role': 'user', 'body': text},
            'assistant_message': asst.to_chat_dict(),
            'side_effects': side,
            'suggestions': list(_SUGGESTIONS),
        }
        result.update(self._ai_mode_payload())
        return result

    def action_ai_chat_clear(self):
        """Efface le fil de discussion de l'utilisateur courant."""
        self.ensure_one()
        threads = self.env['merka.ai.thread'].search([
            ('dashboard_id', '=', self.id),
            ('user_id', '=', self.env.user.id),
        ])
        threads.unlink()
        return self.action_ai_chat_open()
