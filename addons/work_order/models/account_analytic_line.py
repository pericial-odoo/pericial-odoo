from odoo import api, fields, models, _, exceptions


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    date_start = fields.Datetime("Start date")

    date_end = fields.Datetime("End date")

    work_order_id = fields.Many2one("work.order", "Work order")

    unit_amount = fields.Float("Duration", compute="_compute_duration", store=True, inverse='_set_unit_amount', )

    signature_id = fields.Many2one(
        comodel_name="work.order.signature", string="Signature"
    )

    @api.onchange('date_start')
    def _onchange_date_start(self):
        for record in self:
            if record.date_start:
                record.date = record.date_start.date()
            else:
                record.date = False

    def _set_unit_amount(self):
        return self.unit_amount

    @api.model
    def _get_default_employee(self):
        employee_ids = self.env["hr.employee"].search([("user_id", "=", self._uid)])
        return employee_ids[0] if employee_ids else None

    employee_id = fields.Many2one(
        comodel_name="hr.employee", string="Employee", default=_get_default_employee
    )

    @api.depends("date_end", "date_start")
    def _compute_duration(self):
        for blocktime in self:
            if blocktime.date_end:
                d1 = fields.Datetime.from_string(blocktime.date_start)
                d2 = fields.Datetime.from_string(blocktime.date_end)
                if d1 and d2:
                    diff = d2 - d1
                    dur = round(diff.total_seconds() / 60.0 / 60.0, 2)
                    if dur >= 0:
                        blocktime.unit_amount = dur
                    else:
                        raise exceptions.ValidationError(
                            _("Warning! End date is already due.")
                        )
            else:
                blocktime.unit_amount = 0

    @api.model
    def create(self, vals):
        if "name" not in vals:
            if "work_order_id" in vals:
                work_order_id = vals.get("work_order_id")
                if work_order_id:
                    vals["name"] = self.env['work.order'].search(
                        [('id', '=', work_order_id)]).name
                else:
                    vals["name"] = "/"
            vals["name"] = "/"

        if "account_id" not in vals or not vals["account_id"]:
            if not self.work_order_id.analytic_account_id:
                irDefault = self.env["ir.default"].sudo()
                work_order_analytic_method = irDefault.get(
                    "res.config.settings", "work_order_analytic_method"
                )
                if work_order_analytic_method == "new_by_partner":
                    if "work_order_id" in vals:
                        partner_id = self.env['work.order'].search([('id', '=', vals.get('work_order_id'))]).partner_id
                    # partner_id = self.env["res.partner"].search(
                    #     [("id", "=", vals.get("partner_id"))]
                    # )
                        if not partner_id.analytic_account_id:
                            analytic_account_obj = self.env["account.analytic.account"]
                            analytic_account_id = analytic_account_obj.search(
                                [("partner_id", "=", partner_id.id)]
                            )
                            if analytic_account_id:
                                vals["account_id"] = analytic_account_id[0].id
                            else:
                                analytic_account_id.create(
                                    {
                                        "name": _("Work Orders"),
                                        "company_id": vals.get(
                                            "company_id", self.env.user.company_id.id
                                        ),
                                        "partner_id": vals.get("partner_id"),
                                        "active": True,
                                    }
                                )
                                vals["account_id"] = analytic_account_id.id
                                self.env['work.order'].search([('id', '=', vals.get('work_order_id'))]).analytic_account_id = (
                                    analytic_account_id.id
                                )
                        else:
                            vals["account_id"] = partner_id.analytic_account_id.id
            else:
                work_order = self.work_order_id
                if not self.work_order_id:
                    work_order = self.env['work.order'].search([('id', '=', vals.get('work_order_id'))])
                vals["account_id"] = work_order.analytic_account_id.id
        return super(AccountAnalyticLine, self).create(vals)
