# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Après install / upgrade Merka (Odoo 18.0+) :
    1. Détecte les apps Odoo installées (Ventes, CRM, Stock…)
    2. Crée automatiquement les dashboards packs + indicateurs
    3. Nettoie les anciens sous-menus dynamiques
    """
    try:
        result = env['merka.dashboard'].with_context(
            merka_force_auto_setup=True,
        ).auto_setup_from_installed_modules(force_recreate_items=True)
        _logger.info(
            "Merka auto-setup: created=%s existing=%s detected=%s errors=%s",
            len(result.get('created') or []),
            len(result.get('existing') or []),
            [p.get('code') for p in (result.get('detected') or [])],
            result.get('errors'),
        )
    except Exception:
        _logger.exception("Merka auto-setup failed")
    try:
        env['merka.dashboard'].sync_all_menus()
    except Exception:
        _logger.exception("Merka menu sync failed")
    try:
        result = env['merka.dashboard.history'].action_backfill_history(days=14)
        _logger.info(
            "Merka history backfill: created=%s updated=%s days=%s tiles=%s",
            result.get('created'), result.get('updated'),
            result.get('days'), result.get('tiles'),
        )
    except Exception:
        _logger.exception("Merka history backfill failed")
