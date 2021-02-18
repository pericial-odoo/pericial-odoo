from odoo import fields, models, api


class Product(models.Model):
    _inherit = "product.template"

    installable = fields.Boolean(string="Generates work orders", default=False)

    work_order_tracking = fields.Selection(
        [
            ("no", "Don't create work order"),
            ("sale", "Create one work order per sale order"),
            ("line", "Create one work order per sale order line"),
        ],
        string="Work Order Tracking",
        default="no",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    work_order_line = fields.One2many(
        comodel_name="work.order.line", inverse_name="product_id"
    )

    def _compute_quantities_dict(
        self, lot_id, owner_id, package_id, from_date=False, to_date=False
    ):
        res = super(ProductProduct, self)._compute_quantities_dict(
            lot_id, owner_id, package_id, from_date, to_date
        )
        for product in self:
            lines = self.env["work.order.line"].search(
                [("state", "not in", ["done", "cancel", "draft"])]
            )
            lines = lines.filtered(lambda r: r.product_id.id == product.id)
            for line in lines:
                if line.state == "2binvoiced":
                    work_order_id = line.work_order_id
                    if work_order_id.invoice_method != "b4start":
                        if line.type == "add":
                            res[product.id]["virtual_available"] -= line.product_uom_qty
                            res[product.id]["outgoing_qty"] += line.product_uom_qty
                elif line.type == "add":
                    res[product.id]["virtual_available"] -= line.product_uom_qty
                    res[product.id]["outgoing_qty"] += line.product_uom_qty
        return res
