from odoo import fields, models, api


class Category(models.Model):
    _name = "work.order.category"
    _description = "Work Order Category"

    name = fields.Char(required=True)

    invoice_method = fields.Selection(
        [
            ("none", "No Invoice"),
            ("b4start", "Before Work Order"),
            ("after_work_order", "After Work Order"),
        ],
        string="Invoice Method",
        index=True,
        help="Selecting 'Before Work Order' or 'After Work Order' will\
             allow you to generate invoice before or after the work order \
             is done respectively. 'No invoice' means you don't want \
             to generate invoice for this work order.",
    )

    team_ids = fields.Many2many(
        comodel_name="work.order.team",
        relation="work_order_team_category",
        column1="category_id",
        column2="team_id",
        string="Teams",
    )

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env["res.company"]._company_default_get(
            "work.order.category"
        ),
    )

    notes = fields.Char()
