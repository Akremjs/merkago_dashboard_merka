# -*- coding: utf-8 -*-
"""Historique quotidien des KPI + cache court TTL."""
import json
import logging
from datetime import timedelta
from hashlib import sha1

from odoo import api, fields, models
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class MerkaDashboardHistory(models.Model):
    _name = 'merka.dashboard.history'
    _description = 'Historique valeur KPI Merka'
    _order = 'snapshot_date desc, id desc'

    item_id = fields.Many2one(
        'merka.dashboard.item',
        required=True,
        ondelete='cascade',
        index=True,
    )
    dashboard_id = fields.Many2one(
        related='item_id.dashboard_id',
        store=True,
        index=True,
    )
    snapshot_date = fields.Date(required=True, index=True, default=fields.Date.context_today)
    value = fields.Float(required=True)
    unit = fields.Char()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _sql_constraints = [
        (
            'item_date_uniq',
            'unique(item_id, snapshot_date, company_id)',
            'Un snapshot par indicateur et par jour.',
        ),
    ]

    @api.model
    def _upsert_snapshot(self, item, snapshot_date, value, unit=None):
        """Crée ou met à jour un snapshot journalier."""
        company = item.company_id or self.env.company
        existing = self.search([
            ('item_id', '=', item.id),
            ('snapshot_date', '=', snapshot_date),
            ('company_id', '=', company.id),
        ], limit=1)
        vals = {
            'value': float(value or 0),
            'unit': unit or item.unit_label or False,
        }
        if existing:
            existing.write(vals)
            return False
        self.create({
            'item_id': item.id,
            'snapshot_date': snapshot_date,
            'company_id': company.id,
            **vals,
        })
        return True

    @api.model
    def _daily_value_for_item(self, item, day):
        """Valeur agrégée sur une journée calendaire (pour backfill)."""
        if item.data_source == 'formula':
            # Formule : valeur courante (pas de série journalière fiable)
            data = self.env['merka.dashboard.item'].get_item_data(
                item.id, global_date_filter='last_30', use_cache=False,
            )
            return float(data.get('value') or 0), data.get('unit') or item.unit_label
        if item.data_source != 'odoo' or not item.model_name or item.model_name not in self.env:
            return 0.0, item.unit_label
        Model = self.env[item.model_name]
        measure = item.measure_field_id.name if item.measure_field_id else 'id'
        agg = item.aggregation or 'count'
        if not item.date_field_id:
            # Sans champ date : snapshot = valeur courante (répété)
            data = self.env['merka.dashboard.item'].get_item_data(
                item.id, use_cache=False,
            )
            return float(data.get('value') or 0), data.get('unit') or item.unit_label
        field = item.date_field_id.name
        base = item._resolve_domain()
        day_from = fields.Datetime.to_datetime(day)
        day_end = day_from + timedelta(days=1, seconds=-1)
        domain = expression.AND([
            base,
            [(field, '>=', day_from), (field, '<=', day_end)],
        ])
        try:
            value = float(item._aggregate(Model, domain, measure, agg) or 0)
        except Exception:
            value = 0.0
        return value, item.unit_label

    @api.model
    def action_backfill_history(self, days=14):
        """Remplit l'historique manquant sur N jours (anomalies / sparklines)."""
        days = max(3, min(60, int(days or 14)))
        Item = self.env['merka.dashboard.item']
        tiles = Item.search([
            ('active', '=', True),
            ('item_type', 'in', ('tile', 'bullet')),
            ('data_source', 'in', ('odoo', 'formula')),
        ])
        today = fields.Date.context_today(self)
        created = 0
        updated = 0
        for item in tiles:
            for offset in range(days - 1, -1, -1):
                day = today - timedelta(days=offset)
                try:
                    value, unit = self._daily_value_for_item(item, day)
                    was_new = self._upsert_snapshot(item, day, value, unit)
                    if was_new:
                        created += 1
                    else:
                        updated += 1
                except Exception as exc:
                    _logger.debug('Merka backfill skip item=%s day=%s: %s', item.id, day, exc)
        _logger.info('Merka history backfill: +%s new, %s upserted, days=%s', created, updated, days)
        return {
            'ok': True,
            'created': created,
            'updated': updated,
            'days': days,
            'tiles': len(tiles),
        }

    @api.model
    def _cron_snapshot_kpis(self):
        """Snapshot du jour + comble les trous des 7 derniers jours."""
        config = self.env['merka.dashboard.config'].get_config()
        if not config.history_enabled:
            return True
        # Backfill léger des 7 derniers jours (idempotent)
        self.action_backfill_history(days=7)
        old = fields.Date.context_today(self) - timedelta(days=400)
        self.search([('snapshot_date', '<', old)]).unlink()
        return True

    @api.model
    def get_series(self, item_id, days=30):
        """Série historique pour sparkline long terme."""
        today = fields.Date.context_today(self)
        start = today - timedelta(days=max(7, int(days or 30)))
        rows = self.search([
            ('item_id', '=', item_id),
            ('snapshot_date', '>=', start),
        ], order='snapshot_date asc')
        return [
            {'date': r.snapshot_date.isoformat(), 'value': r.value, 'unit': r.unit or ''}
            for r in rows
        ]

    @api.model
    def history_health(self, days=14):
        """État de couverture historique (pour IA / config)."""
        days = max(3, int(days or 14))
        today = fields.Date.context_today(self)
        start = today - timedelta(days=days - 1)
        Item = self.env['merka.dashboard.item']
        tiles = Item.search_count([
            ('active', '=', True),
            ('item_type', 'in', ('tile', 'bullet')),
        ])
        snaps = self.search_count([('snapshot_date', '>=', start)])
        distinct_days = len(set(self.search([('snapshot_date', '>=', start)]).mapped('snapshot_date')))
        expected = tiles * days
        coverage = round(100.0 * snaps / expected, 1) if expected else 0.0
        return {
            'tiles': tiles,
            'snapshots': snaps,
            'distinct_days': distinct_days,
            'expected': expected,
            'coverage_pct': coverage,
            'needs_backfill': distinct_days < min(7, days) or coverage < 40,
        }


class MerkaDashboardCache(models.Model):
    _name = 'merka.dashboard.cache'
    _description = 'Cache agrégats Merka'
    _log_access = False

    cache_key = fields.Char(required=True, index=True)
    payload = fields.Text(required=True)
    expire_at = fields.Datetime(required=True, index=True)

    _sql_constraints = [
        ('cache_key_uniq', 'unique(cache_key)', 'Clé de cache unique.'),
    ]

    @api.model
    def _make_key(self, *parts):
        raw = '|'.join(str(p) for p in parts)
        return sha1(raw.encode('utf-8')).hexdigest()

    @api.model
    def get_json(self, cache_key):
        now = fields.Datetime.now()
        row = self.sudo().search([
            ('cache_key', '=', cache_key),
            ('expire_at', '>', now),
        ], limit=1)
        if not row:
            return None
        try:
            return json.loads(row.payload)
        except Exception:
            return None

    @api.model
    def set_json(self, cache_key, data, ttl_seconds=60):
        ttl = max(5, int(ttl_seconds or 60))
        expire = fields.Datetime.now() + timedelta(seconds=ttl)
        payload = json.dumps(data, default=str)
        existing = self.sudo().search([('cache_key', '=', cache_key)], limit=1)
        if existing:
            existing.write({'payload': payload, 'expire_at': expire})
        else:
            self.sudo().create({
                'cache_key': cache_key,
                'payload': payload,
                'expire_at': expire,
            })
        return True

    @api.model
    def _cron_purge_expired(self):
        self.sudo().search([('expire_at', '<', fields.Datetime.now())]).unlink()
        return True
