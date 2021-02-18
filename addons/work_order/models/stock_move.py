from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    work_order_id = fields.Many2one("work.order")
