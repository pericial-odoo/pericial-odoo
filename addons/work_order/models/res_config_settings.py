from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    group_timesheet_work_order = fields.Boolean(
        default=True,
        string="Use timesheets on work orders",
        implied_group="work_order.group_timesheet_work_order",
    )

    work_order_analytic_method = fields.Selection([
        ('none', 'None'),
        ('default', 'Account by default'),
        ('new_by_partner', 'Create an account by Partner'),
        ],
        default="new_by_partner",
        required=True,
        string="Analytic in Work Orders",
    )

    @api.onchange('work_order_analytic_method')
    def onchange_work_order_analytic_method(self):
        if self.work_order_analytic_method != 'default':
            self.default_analytic_account_id = False

    @api.onchange('group_analytic_accounting')
    def onchange_group_analytic_accounting(self):
        if self.group_analytic_accounting is False:
            self.work_order_analytic_method = 'new_by_partner'

    default_analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        default_model="work.order",
    )

    group_maintenance_type = fields.Boolean(
        string="Show maintenance type",
        implied_group="work_order.group_maintenance_type",
    )

    group_employee_warehouse = fields.Boolean(
        string="Employee's warehouse preference",
        implied_group="work_order.group_employee_warehouse",
    )

    group_add_remove_product = fields.Boolean(
        string="Choose add or remove product",
        implied_group="work_order.group_add_remove_product",
        help="This option allows to choose if adding or removing products in work order lines."
    )

    default_invoice_method = fields.Selection(
        [
            ("none", "No Invoice"),
            ("b4start", "Before Work Order"),
            ("after_work_order", "After Work Order"),
        ],
        string="Invoice Method",
        default="none",
        required=True,
        default_model="work.order",
        index=True,
        help="Selecting 'Before Work Order' or 'After Work Order' will\
                 allow you to generate invoice before or after the work order \
                 is done respectively. 'No invoice' means you don't want \
                 to generate invoice for this work order.",
    )

    group_work_order_category_invoice = fields.Boolean(
        string="Invoicing per category",
        implied_group='work_order.group_work_order_category_invoice',
        help="This option will change the invoice method when category is modified."
    )

    manual_category_invoice = fields.Boolean(
        string='Allow manual modification')

    operation_id_default = fields.Many2one(
        comodel_name="product.product", string="Operation by default"
    )

    operation_by_default = fields.Boolean(string="Operation by default")

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrDefault = self.env["ir.default"].sudo()
        res.update(
            {
                "operation_id_default": IrDefault.get(
                    "res.config.settings", "operation_id_default"
                ),
                "work_order_analytic_method": IrDefault.get(
                    "res.config.settings", "work_order_analytic_method"
                ),
                "default_invoice_method": IrDefault.get(
                    "res.config.settings", "default_invoice_method"
                )
                or "none",
                "operation_by_default": IrDefault.get(
                    "res.config.settings", "operation_by_default"
                ),
                "manual_category_invoice": IrDefault.get(
                    "res.config.settings", "manual_category_invoice"
                ),
            }
        )
        return res

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrDefault = self.env["ir.default"].sudo()
        IrDefault.set(
            "res.config.settings", "operation_id_default", self.operation_id_default.id
        )
        IrDefault.set(
            "res.config.settings", "work_order_analytic_method", self.work_order_analytic_method
        )
        IrDefault.set(
            "res.config.settings", "default_invoice_method", self.default_invoice_method
        )
        IrDefault.set(
            "res.config.settings", "operation_by_default", self.operation_by_default
        )
        IrDefault.set(
            "res.config.settings",
            "manual_category_invoice",
            self.manual_category_invoice,
        )
        return True
