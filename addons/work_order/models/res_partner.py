from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    client_smart_button_work_order_view_count = fields.Integer(
        compute="_compute_client_smart_button_work_order_view_count"
    )

    work_order_ids = fields.One2many(
        comodel_name="work.order", inverse_name="partner_id", string="Work orders"
    )

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')

    @api.multi
    def _compute_client_smart_button_work_order_view_count(self):
        for partner in self:
            partner.client_smart_button_work_order_view_count = len(
                partner.work_order_ids
            )

    def action_view_client_smart_button_work_order_view(self):
        return {
            "name": _("Work orders"),
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "work.order",
            "type": "ir.actions.act_window",
            "domain": "[('id', 'in', " + str(self.work_order_ids.ids) + " )]",
            "context": self.env.context,
        }
