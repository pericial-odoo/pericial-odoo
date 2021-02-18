from odoo import api, models, fields


class Employee(models.Model):
    _inherit = "hr.employee"

    employee_smart_button_work_order_view_count = fields.Integer(
        compute="_compute_employee_smart_button_work_order_view_count"
    )

    time_tracking_ids = fields.One2many(
        comodel_name="account.analytic.line",
        inverse_name="employee_id",
        string="Time tracking",
    )

    work_order_ids = fields.Many2many(
        comodel_name="work.order",
        string="Work order",
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
    )

    @api.multi
    def _compute_employee_smart_button_work_order_view_count(self):
        for employee in self:
            employee.employee_smart_button_work_order_view_count = len(
                employee.time_tracking_ids
            )

    def action_view_employee_smart_button_work_order_view(self):
        context = self.env.context.copy()
        context.update({"group_by": "account_id"})
        return {
            "name": "Work orders time tracking",
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "account.analytic.line",
            "type": "ir.actions.act_window",
            "domain": "[('id', 'in', " + str(self.time_tracking_ids.ids) + " )]",
            "context": context,
        }
