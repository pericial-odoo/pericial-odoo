from odoo import api, fields, models, _


class WorkOrderTeam(models.Model):
    _name = "work.order.team"
    _description = "Work Order Team"

    name = fields.Char(required=True)

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env["res.company"]._company_default_get(
            "work.order.team"
        ),
    )

    member_ids = fields.Many2many(
        comodel_name="res.users",
        relation="work_order_team_users",
        column1="team_id",
        column2="user_id",
        string="Team members",
    )

    color = fields.Integer("Color Index", default=0)

    category_ids = fields.Many2many(
        comodel_name="work.order.category",
        relation="work_order_team_category",
        column1="team_id",
        column2="category_id",
        string="Categories",
    )

    work_order_ids = fields.One2many("work.order", "work_order_team_id", copy=False)

    todo_work_order_ids = fields.One2many(
        "work.order", string="Work orders", compute="_compute_todo_work_orders"
    )

    todo_work_order_count = fields.Integer(
        string="Number of work orders", compute="_compute_todo_work_orders"
    )

    todo_work_order_count_date = fields.Integer(
        string="Number of work orders scheduled", compute="_compute_todo_work_orders"
    )
    todo_work_order_count_high_priority = fields.Integer(
        string="Number of work orders in high priority",
        compute="_compute_todo_work_orders",
    )

    todo_work_order_count_unscheduled = fields.Integer(
        string="Number of work orders unscheduled", compute="_compute_todo_work_orders"
    )

    todo_count_2binvoiced = fields.Integer(
        string="Number of work orders to be invoiced",
        compute="_compute_todo_work_orders",
    )

    @api.depends("work_order_ids")
    def _compute_todo_work_orders(self):
        for record in self:
            record.todo_work_order_ids = record.work_order_ids.filtered(
                lambda e: e.state in ["confirmed", "in_process"]
            )
            record.todo_work_order_count = len(record.todo_work_order_ids)
            record.todo_work_order_count_date = len(
                record.todo_work_order_ids.filtered(lambda e: e.date_planned_start)
            )
            record.todo_work_order_count_high_priority = len(
                record.todo_work_order_ids.filtered(lambda e: e.priority == "3")
            )
            record.todo_work_order_count_unscheduled = len(
                record.todo_work_order_ids.filtered(lambda e: not e.date_planned_start)
            )
            record.todo_count_2binvoiced = len(
                record.work_order_ids.filtered(lambda e: e.state == "2binvoiced")
            )

    def get_work_order_view_by_team(self):
        return {
            "name": self.name or _("Work Orders"),
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "work.order",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", self.work_order_ids.ids)],
        }
