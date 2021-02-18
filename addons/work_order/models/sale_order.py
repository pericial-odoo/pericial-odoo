from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    work_order_ids = fields.One2many(
        comodel_name="work.order", inverse_name="sale_order_id", string="Work orders"
    )

    work_order_ids_count = fields.Integer(compute="_compute_work_order_ids_count")

    def calculate_count(self):
        return len(self.work_order_ids)

    @api.multi
    def _compute_work_order_ids_count(self):
        for work_order_ids in self:
            work_order_ids.work_order_ids_count = self.calculate_count()

    def action_view_work_order_ids(self):
        active_ids = self.work_order_ids.ids
        return {
            "name": _("Work orders"),
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "work.order",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", active_ids)],
            "context": self.env.context,
        }

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        work_orders_list = []
        for order in self:
            one_per_line = order.order_line.filtered(
                lambda r: r.product_id.work_order_tracking == 'line' and r.product_id.installable == True and not r.work_order_id)
            one_per_order = order.order_line.filtered(
                lambda r: r.product_id.work_order_tracking == 'sale' and r.product_id.installable == True and not r.work_order_id)
            one_per_order_done = order.order_line.filtered(
                lambda r: r.product_id.work_order_tracking == 'sale' and r.product_id.installable == True and r.work_order_id)

            if one_per_order:
                if not one_per_order_done:
                    work_order_id = self.env["work.order"].create(
                        {
                            "work_address_id": self.partner_shipping_id.id,
                            "company_id": self.company_id.id,
                            "partner_id": self.partner_id.id,
                            "origin_document": self.name,
                            "pricelist_id": self.pricelist_id.id,
                            "invoice_method": 'none',
                            'team_id': self.team_id.id,
                            "analytic_account_id": self.analytic_account_id.id or False,
                            "state": "confirmed",
                        }
                    )
                else:
                    work_order_id = one_per_order_done[0].work_order_id
                work_order_id.write({
                    'invoice_method': 'none'
                })

                for order_line in one_per_order:
                    order_line.write({
                        'work_order_id': work_order_id.id
                    })
                    work_order_id.write(
                        {
                            "service_lines": [
                                (
                                    0,
                                    0,
                                    {
                                        "product_id": order_line.product_id.id,
                                        "name": order_line.name,
                                        "price_unit": order_line.price_unit,
                                        "price_subtotal": order_line.price_subtotal,
                                        "tax_id": [
                                            (6, 0, order_line.tax_id.ids)
                                        ],
                                        "product_uom": order_line.product_id.uom_id.id,
                                        "product_uom_qty": order_line.product_uom_qty,
                                    },
                                )
                            ],
                        }
                    )
                work_order_id.message_post_with_view(
                    "mail.message_origin_link",
                    values={"self": work_order_id, "origin": order},
                    subtype_id=self.env.ref("mail.mt_note").id,
                    author_id=self.env.user.partner_id.id,
                )
                work_orders_list.append((4, work_order_id.id))

            if one_per_line:
                for order_line in one_per_line:
                    work_order_id = self.env["work.order"].create(
                        {
                            "work_address_id": self.partner_shipping_id.id,
                            "company_id": self.company_id.id,
                            "partner_id": self.partner_id.id,
                            "origin_document": self.name,
                            "pricelist_id": self.pricelist_id.id,
                            "invoice_method": 'none',
                            'team_id': self.team_id.id,
                            "analytic_account_id": self.analytic_account_id.id or False,
                            "state": "confirmed",

                        }
                    )
                    work_order_id.write({
                        'invoice_method': 'none'
                    })
                    work_order_id.write(
                        {
                            "service_lines": [
                                (
                                    0,
                                    0,
                                    {
                                        "product_id": order_line.product_id.id,
                                        "name": order_line.name,
                                        "price_unit": order_line.price_unit,
                                        "price_subtotal": order_line.price_subtotal,
                                        "tax_id": [
                                            (6, 0, order_line.tax_id.ids)
                                        ],
                                        "product_uom": order_line.product_id.uom_id.id,
                                        "product_uom_qty": order_line.product_uom_qty,
                                    },
                                )
                            ],
                        }
                    )
                    order_line.write({
                        'work_order_id': work_order_id.id
                    })
                    work_order_id.message_post_with_view(
                        "mail.message_origin_link",
                        values={"self": work_order_id, "origin": order},
                        subtype_id=self.env.ref("mail.mt_note").id,
                        author_id=self.env.user.partner_id.id,
                    )
                    work_orders_list.append((4, work_order_id.id))

        self.work_order_ids = work_orders_list
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    work_order_id = fields.Many2one(
        copy=False,
        comodel_name='work.order',
        string='Work Order')
