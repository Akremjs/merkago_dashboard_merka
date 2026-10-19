# -*- coding: utf-8 -*-
from odoo import fields, models


class MerkaDashboardSetupWizard(models.TransientModel):
    _name = 'merka.dashboard.setup.wizard'
    _description = 'Assistant création Dashboard Merka'

    name = fields.Char(required=True, string='Nom du tableau de bord')
    pack_code = fields.Selection(
        [
            ('custom', 'Personnalisé (vide)'),
            ('sales', 'Pack Ventes'),
            ('crm', 'Pack CRM'),
            ('purchase', 'Pack Achats'),
            ('accounting', 'Pack Comptabilité'),
            ('inventory', 'Pack Inventaire'),
            ('pos', 'Pack POS'),
            ('hr', 'Pack RH'),
            ('website', 'Pack Site web'),
            ('project', 'Pack Projets'),
            ('manufacturing', 'Pack Fabrication'),
            ('helpdesk', 'Pack Helpdesk'),
        ],
        default='sales',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=False,
        help='Vide = tableau visible dans toutes les sociétés.',
    )

    def _model(self, technical_name):
        return self.env['ir.model'].search([('model', '=', technical_name)], limit=1)

    def _field(self, model_rec, field_name):
        if not model_rec:
            return self.env['ir.model.fields']
        return self.env['ir.model.fields'].search([
            ('model_id', '=', model_rec.id),
            ('name', '=', field_name),
        ], limit=1)

    def _item_vals(self, dashboard, **kwargs):
        return {
            'dashboard_id': dashboard.id,
            **kwargs,
        }

    def _create_pack_items(self, dashboard):
        """Construit un pack riche (tuiles + graphiques) selon les apps installées."""
        Item = self.env['merka.dashboard.item']
        pack = self.pack_code

        # --- Ventes (layout type Power BI : 4 KPI + bar + donut + 2 tables) ---
        if pack == 'sales':
            so = self._model('sale.order')
            sol = self._model('sale.order.line')
            if so:
                amount = self._field(so, 'amount_total')
                date_order = self._field(so, 'date_order')
                state = self._field(so, 'state')
                partner = self._field(so, 'partner_id')
                user = self._field(so, 'user_id')
                Item.create(self._item_vals(dashboard,
                    name="Chiffre d'affaires", code='ca', item_type='tile', model_id=so.id,
                    measure_field_id=amount.id if amount else False,
                    date_field_id=date_order.id if date_order else False,
                    aggregation='sum', domain="[('state', 'in', ['sale', 'done'])]",
                    date_filter='last_30', target_value=100000, unit_label='€',
                    layout_w=3, sequence=10,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Commandes', code='commandes', item_type='tile', model_id=so.id,
                    date_field_id=date_order.id if date_order else False,
                    aggregation='count', domain="[('state', 'in', ['sale', 'done'])]",
                    date_filter='last_30', target_value=50, layout_w=3, sequence=20,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Devis en cours', code='devis', item_type='tile', model_id=so.id,
                    aggregation='count', domain="[('state', 'in', ['draft', 'sent'])]",
                    layout_w=3, sequence=30, target_value=20,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Panier moyen', code='panier', item_type='tile',
                    data_source='formula',
                    formula='safe_div({ca}, {commandes})  # CA / commandes',
                    formula_decimals=2,
                    unit_label='€', layout_w=3, sequence=40,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Taux conversion devis', code='taux_conv', item_type='tile',
                    data_source='formula',
                    formula='pct({commandes}, {commandes} + {devis})  # commandes / (commandes+devis)',
                    formula_decimals=1,
                    unit_label='%', layout_w=3, sequence=50,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Ventes par période', item_type='bar', model_id=so.id,
                    measure_field_id=amount.id if amount else False,
                    groupby_field_id=date_order.id if date_order else False,
                    date_field_id=date_order.id if date_order else False,
                    aggregation='sum', domain="[('state', 'in', ['sale', 'done'])]",
                    date_filter='last_30', layout_w=8, sequence=50, limit=12,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Sources de revenus', item_type='doughnut', model_id=so.id,
                    groupby_field_id=user.id if user else (state.id if state else False),
                    measure_field_id=amount.id if amount else False,
                    date_field_id=date_order.id if date_order else False,
                    aggregation='sum', domain="[('state', 'in', ['sale', 'done'])]",
                    date_filter='last_30', layout_w=4, sequence=60, limit=8,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Dernières commandes', item_type='list', model_id=so.id,
                    measure_field_id=amount.id if amount else False,
                    date_field_id=date_order.id if date_order else False,
                    aggregation='count', domain="[('state', 'in', ['sale', 'done'])]",
                    sort='date_order desc', layout_w=6, sequence=70, limit=8,
                ))
                if sol:
                    product = self._field(sol, 'product_id')
                    qty = self._field(sol, 'product_uom_qty')
                    price = self._field(sol, 'price_subtotal')
                    Item.create(self._item_vals(dashboard,
                        name='Meilleures ventes', item_type='hbar', model_id=sol.id,
                        measure_field_id=price.id if price else (qty.id if qty else False),
                        groupby_field_id=product.id if product else False,
                        aggregation='sum',
                        domain="[('order_id.state', 'in', ['sale', 'done']), ('product_id', '!=', False)]",
                        layout_w=6, sequence=80, limit=8,
                    ))
                elif partner:
                    Item.create(self._item_vals(dashboard,
                        name='Top clients', item_type='hbar', model_id=so.id,
                        measure_field_id=amount.id if amount else False,
                        groupby_field_id=partner.id if partner else False,
                        date_field_id=date_order.id if date_order else False,
                        aggregation='sum', domain="[('state', 'in', ['sale', 'done'])]",
                        date_filter='this_year', layout_w=6, sequence=80, limit=8,
                    ))
                return

        # --- CRM ---
        if pack == 'crm':
            lead = self._model('crm.lead')
            if lead:
                expected = self._field(lead, 'expected_revenue')
                stage = self._field(lead, 'stage_id')
                team = self._field(lead, 'team_id')
                create_date = self._field(lead, 'create_date')
                Item.create(self._item_vals(dashboard,
                    name='Opportunités ouvertes', item_type='tile', model_id=lead.id,
                    aggregation='count', domain="[('type', '=', 'opportunity'), ('probability', '&lt;', 100), ('active', '=', True)]".replace('&lt;', '<'),
                    layout_w=3, sequence=10, target_value=30,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Pipeline (€)', item_type='tile', model_id=lead.id,
                    measure_field_id=expected.id if expected else False,
                    aggregation='sum', domain="[('type', '=', 'opportunity'), ('active', '=', True)]",
                    unit_label='€', layout_w=3, sequence=20, target_value=200000,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Gagnées', item_type='tile', model_id=lead.id,
                    aggregation='count', domain="[('probability', '=', 100)]",
                    date_field_id=create_date.id if create_date else False,
                    date_filter='last_30', layout_w=3, sequence=30,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Pipeline par étape', item_type='bar', model_id=lead.id,
                    measure_field_id=expected.id if expected else False,
                    groupby_field_id=stage.id if stage else False,
                    aggregation='sum', domain="[('type', '=', 'opportunity'), ('active', '=', True)]",
                    layout_w=8, sequence=40, limit=10,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Par équipe', item_type='pie', model_id=lead.id,
                    groupby_field_id=team.id if team else False,
                    aggregation='count', domain="[('type', '=', 'opportunity')]",
                    layout_w=4, sequence=50, limit=8,
                ))
                return

        # --- Comptabilité ---
        if pack == 'accounting':
            move = self._model('account.move')
            if move:
                amount = self._field(move, 'amount_total')
                residual = self._field(move, 'amount_residual')
                invoice_date = self._field(move, 'invoice_date')
                partner = self._field(move, 'partner_id')
                Item.create(self._item_vals(dashboard,
                    name='Factures clients', item_type='tile', model_id=move.id,
                    aggregation='count',
                    domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
                    date_field_id=invoice_date.id if invoice_date else False,
                    date_filter='this_month', layout_w=3, sequence=10,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Encours clients', item_type='tile', model_id=move.id,
                    measure_field_id=residual.id if residual else amount.id if amount else False,
                    aggregation='sum',
                    domain="[('move_type', '=', 'out_invoice'), ('payment_state', 'in', ['not_paid', 'partial']), ('state', '=', 'posted')]",
                    unit_label='€', layout_w=3, sequence=20, target_value=50000,
                ))
                Item.create(self._item_vals(dashboard,
                    name='CA facturé', item_type='area', model_id=move.id,
                    measure_field_id=amount.id if amount else False,
                    groupby_field_id=partner.id if partner else False,
                    aggregation='sum',
                    domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
                    date_field_id=invoice_date.id if invoice_date else False,
                    date_filter='this_year', layout_w=12, sequence=30, limit=10,
                ))
                return

        # --- Inventaire ---
        if pack == 'inventory':
            quant = self._model('stock.quant')
            move = self._model('stock.move')
            if quant:
                product = self._field(quant, 'product_id')
                qty = self._field(quant, 'quantity')
                location = self._field(quant, 'location_id')
                Item.create(self._item_vals(dashboard,
                    name='Lignes de stock', item_type='tile', model_id=quant.id,
                    aggregation='count',
                    domain="[('location_id.usage', '=', 'internal')]",
                    layout_w=3, sequence=10,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Quantité totale', item_type='tile', model_id=quant.id,
                    measure_field_id=qty.id if qty else False,
                    aggregation='sum',
                    domain="[('location_id.usage', '=', 'internal')]",
                    layout_w=3, sequence=20,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Stock par emplacement', item_type='bar', model_id=quant.id,
                    measure_field_id=qty.id if qty else False,
                    groupby_field_id=location.id if location else False,
                    aggregation='sum',
                    domain="[('location_id.usage', '=', 'internal')]",
                    layout_w=6, sequence=30, limit=8,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Top produits', item_type='doughnut', model_id=quant.id,
                    measure_field_id=qty.id if qty else False,
                    groupby_field_id=product.id if product else False,
                    aggregation='sum',
                    domain="[('location_id.usage', '=', 'internal')]",
                    layout_w=6, sequence=40, limit=8,
                ))
            if move:
                Item.create(self._item_vals(dashboard,
                    name='Mouvements terminés', item_type='tile', model_id=move.id,
                    aggregation='count', domain="[('state', '=', 'done')]",
                    layout_w=3, sequence=50,
                ))
            return

        if pack == 'purchase':
            po = self._model('purchase.order')
            if po:
                amount = self._field(po, 'amount_total')
                partner = self._field(po, 'partner_id')
                state = self._field(po, 'state')
                date_order = self._field(po, 'date_order')
                Item.create(self._item_vals(dashboard,
                    name='Commandes achat', item_type='tile', model_id=po.id,
                    aggregation='count',
                    domain="[('state', 'in', ['purchase', 'done'])]",
                    date_field_id=date_order.id if date_order else False,
                    date_filter='last_30', layout_w=3, sequence=10, target_value=40,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Montant achats', item_type='tile', model_id=po.id,
                    measure_field_id=amount.id if amount else False,
                    aggregation='sum',
                    domain="[('state', 'in', ['purchase', 'done'])]",
                    date_field_id=date_order.id if date_order else False,
                    date_filter='last_30', unit_label='€', layout_w=3, sequence=20,
                ))
                Item.create(self._item_vals(dashboard,
                    name='RFQ en cours', item_type='tile', model_id=po.id,
                    aggregation='count',
                    domain="[('state', 'in', ['draft', 'sent', 'to approve'])]",
                    layout_w=3, sequence=30,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Par fournisseur', item_type='hbar', model_id=po.id,
                    measure_field_id=amount.id if amount else False,
                    groupby_field_id=partner.id if partner else False,
                    aggregation='sum',
                    domain="[('state', 'in', ['purchase', 'done'])]",
                    layout_w=6, sequence=40, limit=8,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Répartition états', item_type='doughnut', model_id=po.id,
                    groupby_field_id=state.id if state else False,
                    aggregation='count', layout_w=6, sequence=50, limit=10,
                ))
            return

        if pack == 'pos':
            order = self._model('pos.order')
            if order:
                amount = self._field(order, 'amount_total')
                session = self._field(order, 'session_id')
                date_order = self._field(order, 'date_order')
                Item.create(self._item_vals(dashboard,
                    name='Tickets POS', item_type='tile', model_id=order.id,
                    aggregation='count', date_filter='last_30',
                    date_field_id=date_order.id if date_order else False,
                    layout_w=3, sequence=10, target_value=100,
                ))
                Item.create(self._item_vals(dashboard,
                    name='CA POS', item_type='tile', model_id=order.id,
                    measure_field_id=amount.id if amount else False,
                    aggregation='sum', date_filter='last_30',
                    date_field_id=date_order.id if date_order else False,
                    unit_label='€', layout_w=3, sequence=20,
                ))
                Item.create(self._item_vals(dashboard,
                    name='CA par session', item_type='bar', model_id=order.id,
                    measure_field_id=amount.id if amount else False,
                    groupby_field_id=session.id if session else False,
                    aggregation='sum', layout_w=12, sequence=30, limit=10,
                ))
            return

        if pack == 'hr':
            emp = self._model('hr.employee')
            leave = self._model('hr.leave')
            if emp:
                dept = self._field(emp, 'department_id')
                Item.create(self._item_vals(dashboard,
                    name='Employés', item_type='tile', model_id=emp.id,
                    aggregation='count', layout_w=3, sequence=10,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Par département', item_type='doughnut', model_id=emp.id,
                    groupby_field_id=dept.id if dept else False,
                    aggregation='count', layout_w=6, sequence=20, limit=8,
                ))
            if leave:
                Item.create(self._item_vals(dashboard,
                    name='Congés validés', item_type='tile', model_id=leave.id,
                    aggregation='count', domain="[('state', '=', 'validate')]",
                    layout_w=3, sequence=30,
                ))
            return

        if pack == 'website':
            visitor = self._model('website.visitor')
            if visitor:
                country = self._field(visitor, 'country_id')
                Item.create(self._item_vals(dashboard,
                    name='Visiteurs', item_type='tile', model_id=visitor.id,
                    aggregation='count', layout_w=3, sequence=10,
                ))
                Item.create(self._item_vals(dashboard,
                    name='Par pays', item_type='hbar', model_id=visitor.id,
                    groupby_field_id=country.id if country else False,
                    aggregation='count', layout_w=9, sequence=20, limit=10,
                ))
            return

        # custom / fallback KPI dictionary
        kpis = self.env['merka.dashboard.kpi'].search([
            ('pack_code', '=', pack),
            ('active', '=', True),
        ])
        for kpi in kpis:
            if not kpi.model_id:
                continue
            Item.create(self._item_vals(dashboard,
                name=kpi.name, item_type='tile', model_id=kpi.model_id.id,
                aggregation=kpi.aggregation or 'count',
                domain=kpi.domain or '[]', kpi_id=kpi.id, layout_w=3,
            ))

    def action_create_dashboard(self):
        self.ensure_one()
        dashboard = self.env['merka.dashboard'].create({
            'name': self.name,
            'pack_code': self.pack_code,
            'company_id': self.company_id.id if self.company_id else False,
        })
        self._create_pack_items(dashboard)
        return dashboard.action_open_dashboard()
