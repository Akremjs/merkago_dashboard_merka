# -*- coding: utf-8 -*-
from odoo import models


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def write(self, vals):
        """Quand une app métier passe à « installed », créer le pack Merka lié."""
        res = super().write(vals)
        if vals.get('state') == 'installed':
            try:
                self.env['merka.dashboard'].sudo().auto_setup_from_installed_modules(
                    only_modules=self.mapped('name'),
                )
            except Exception:
                # Ne jamais bloquer l'installation d'un autre module
                pass
        return res
