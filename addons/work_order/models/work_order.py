import base64
from datetime import datetime, timedelta
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError
from odoo.tools import float_is_zero


class WorkOrder(models.Model):
    _name = "work.order"
    _description = "Work Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name desc, id desc"

    @api.model
    def _default_warehouse_id(self):
        if self.user_has_groups('work_order.group_employee_warehouse'):
            employee_ids = self.env["hr.employee"].search(
                [("user_id", "=", self._uid)], limit=1)
            if employee_ids.warehouse_id:
                return employee_ids.warehouse_id
        company = self.env.user.company_id.id
        warehouse_ids = self.env['stock.warehouse'].search(
            [('company_id', '=', company)], limit=1)
        return warehouse_ids

    name = fields.Char(
        "Work Order Reference",
        default=lambda self: _("New"),
        copy=False,
        required=True,
        states={"confirmed": [("readonly", True)]},
    )

    @api.model
    def _default_user(self):
        return self.env.context.get('user_id', self.env.user.id)

    user_id = fields.Many2one('res.users', string='Sales Manager', default=_default_user)

    manual_category_invoice = fields.Boolean(
        compute="_compute_manual_category_invoice"
    )

    def _compute_manual_category_invoice(self):
        irDefault = self.env["ir.default"].sudo()
        allow = irDefault.get(
            "res.config.settings",
            "manual_category_invoice"
        )
        for record in self:
            if record.user_has_groups('work_order.group_work_order_category_invoice'):
                record.manual_category_invoice = allow
            else:
                record.manual_category_invoice = True

    # _sql_constraints = [
    #     ('name',
    #      'unique (name)',
    #      'The name of the Work Order must be unique!'),
    # ]

    unsigned_due_hours = fields.Float(
        string="Unsigned hours",
        compute="compute_unsigned_due_hours",
        help="Unsigned time tracking's entries due hours"
    )

    partner_id = fields.Many2one(
        "res.partner",
        "Customer",
        required=True,
        index=True,
        states={"confirmed": [("readonly", True)]},
        help="Choose partner for whom the order \
            will be invoiced and delivered.",
    )

    work_address_id = fields.Many2one(
        "res.partner",
        "Address",
        domain="[('parent_id','=',partner_id)]",
        states={"confirmed": [("readonly", True)]},
    )

    state = fields.Selection(
        [
            ("draft", "Quotation"),
            ("cancel", "Cancelled"),
            ("confirmed", "Confirmed"),
            ("in_process", "In process"),
            ("2binvoiced", "To be Invoiced"),
            ("invoice_except", "Invoice Exception"),
            ("done", "Finished"),
        ],
        string="Status",
        copy=False,
        default="draft",
        readonly=True,
        track_visibility="onchange",
        help="* The 'Quotation' status is used when a user is encoding a new\
                    and unconfirmed work order.\n"
             "* The 'Confirmed' status is used when a user confirms the work\
                         order.\n"
             "* The 'In process' status is used to indicate that the work \
                         order is being done.\n"
             "* The 'To be Invoiced' status is used to generate the invoice\
                         before or after the work order is done.\n"
             "* The 'Finished' status is set when the work order is\
                         completed.\n"
             "* The 'Cancelled' status is used when the user cancels the\
                         work order.",
    )

    # Fields related to product shown in Parts page
    product_parts = fields.Text(string="Product")

    product_parts_qty = fields.Float("Product Quantity")

    lot_id_text = fields.Text(string="Lot/Serial")

    guarantee_limit = fields.Date(
        "Warranty Expiration", states={"confirmed": [("readonly", True)]}
    )

    work_order_lines = fields.One2many("work.order.line", "work_order_id", "Products", copy=True)

    pricelist_id = fields.Many2one(
        "product.pricelist",
        "Pricelist",
        default=lambda self: self.env["product.pricelist"].search([], limit=1).id,
    )

    partner_invoice_id = fields.Many2one("res.partner", "Invoicing Address")

    invoice_method = fields.Selection(
        [
            ("none", "No Invoice"),
            ("b4start", "Before Work Order"),
            ("after_work_order", "After Work Order"),
        ],
        string="Invoice Method",
        default="none",
        index=True,
        readonly=True,
        required=True,
        states={"draft": [("readonly", False)]},
        help="Selecting 'Before Work Order' or 'After Work Order' will\
                 allow you to generate invoice before or after the work order \
                 is done respectively. 'No invoice' means you don't want \
                 to generate invoice for this work order.",
    )

    invoice_count = fields.Integer(string='Invoice Count', compute='_get_invoiced', readonly=True)

    invoice_ids = fields.Many2many(
        "account.invoice",
        string='Invoices',
        compute="_get_invoiced",
        readonly=True,
        copy=False
    )

    invoice_status = fields.Selection([
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
    ], string='Invoice Status',
        compute='_get_invoice_status', store=True, readonly=True)

    move_id = fields.Many2one(
        "stock.move",
        "Move",
        copy=False,
        readonly=True,
        track_visibility="onchange",
        help="Move created by the work order",
    )

    service_lines = fields.One2many(
        "work.order.service", "work_order_id", "Services", copy=True
    )

    internal_notes = fields.Text("Internal Notes")

    quotation_notes = fields.Text("Quotation Notes")

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env["res.company"]._company_default_get("work.order"),
    )

    invoiced = fields.Boolean("Invoiced", copy=False, readonly=True)

    finished = fields.Boolean("Finished", copy=False, readonly=True)

    resp = fields.Many2one(comodel_name="res.users", string="Assigned to")

    allowed_to_time_tracking = fields.Boolean(
        string="Allowed", compute="_compute_allowed"
    )

    maintenance_type = fields.Selection(
        [("corrective", "Corrective"), ("preventive", "Preventive")],
        string="Maintenance Type",
    )

    origin_document = fields.Char(string="Origin Document")

    priority = fields.Selection(
        [("0", _("Low")), ("1", _("Medium")), ("2", _("High")), ("3", _("Very High"))],
        string="Priority",
        default="1",
    )

    work_order_team_id = fields.Many2one("work.order.team", string="Team")

    work_order_member_ids = fields.Many2many(
        compute="_compute_work_order_member_ids",
        comodel_name="res.users",
        relation="work_order_member_ids",
        column1="work_order_id",
        column2="user_id",
        string="Work order team members",
    )

    category_id = fields.Many2one(comodel_name="work.order.category", string="Category")

    work_order_team_ids = fields.Many2many(
        compute="_compute_work_order_team_ids",
        comodel_name="work.order.team",
        relation="work_order_teams",
        column1="work_order_id",
        column2="team_ids",
        string="Category teams",
    )

    date_planned_start = fields.Datetime(
        "Scheduled Date Start",
        states={"done": [("readonly", True)], "cancel": [("readonly", True)]},
    )

    date_planned_finished = fields.Datetime(
        "Scheduled Date Finished",
        states={"done": [("readonly", True)], "cancel": [("readonly", True)]},
    )

    date_start = fields.Datetime(
        "Effective start date", compute="_compute_date_start", readonly=True, store=True
    )

    date_finished = fields.Datetime(
        "Effective finish date",
        compute="_compute_date_finished",
        readonly=True,
        store=True,
    )

    duration_expected = fields.Float(
        "Expected Duration",
        digits=(16, 2),
        default=1,
        states={"done": [("readonly", True)], "cancel": [("readonly", True)]},
        help="Expected duration (in hours)",
    )

    duration = fields.Float(
        "Real Duration", compute="_compute_duration", readonly=True, store=True
    )

    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Analytic Account')

    time_ids = fields.One2many(
        "account.analytic.line", "work_order_id",
    )

    amount_untaxed = fields.Monetary(
        "Untaxed Amount", compute="_amount_untaxed", store=True
    )

    amount_tax = fields.Monetary("Taxes", compute="_amount_tax", store=True)

    amount_total = fields.Monetary("Total", compute="_amount_total", store=True)

    sale_order_id = fields.Many2one(comodel_name="sale.order", string="Sale order")

    employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Employees",
    )

    last_signature = fields.Binary(string="Last signature", compute="_last_signature")

    tag_ids = fields.Many2many(comodel_name="work.order.tag", string="Tags", )

    currency_id = fields.Many2one(
        "res.currency",
        related="pricelist_id.currency_id",
        string="Currency",
        readonly=True,
        required=True,
    )

    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position')

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        default=_default_warehouse_id, check_company=True)

    @api.depends('state', 'work_order_lines.invoice_status', 'service_lines.invoice_status')
    def _get_invoice_status(self):
        unconfirmed_orders = self.filtered(lambda so: so.state in ['draft'])
        unconfirmed_orders.update({'invoice_status': 'no'})
        confirmed_orders = self - unconfirmed_orders
        if not confirmed_orders:
            return
        lines = self.env['work.order.line'].read_group([
            ('work_order_id', 'in', confirmed_orders.ids),
            # ('is_downpayment', '=', False),
            ('display_type', '=', False),
        ],
            ['work_order_id', 'invoice_status'],
            ['work_order_id', 'invoice_status'], lazy=False)
        services = self.env['work.order.service'].read_group([
            ('work_order_id', 'in', confirmed_orders.ids),
            # ('is_downpayment', '=', False),
            ('display_type', '=', False),
        ],
            ['work_order_id', 'invoice_status'],
            ['work_order_id', 'invoice_status'], lazy=False)
        line_invoice_status_all = [
            (d['work_order_id'][0], d['invoice_status'])
            for d in lines + services]
        for order in confirmed_orders:
            line_invoice_status = [d[1] for d in line_invoice_status_all if d[0] == order.id]
            if order.state in ('draft'):
                order.invoice_status = 'no'
            elif order.invoice_method == 'b4start' and order.state not in ['draft', 'cancel', 'in_process']:
                if any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
                    order.invoice_status = 'to invoice'
                elif line_invoice_status and all(
                        invoice_status == 'invoiced' for invoice_status in line_invoice_status):
                    order.invoice_status = 'invoiced'
            elif order.invoice_method == 'after_work_order' and order.state not in ['draft', 'cancel', 'confirmed',
                                                                                    'in_process']:
                if any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
                    order.invoice_status = 'to invoice'
                elif line_invoice_status and all(
                        invoice_status == 'invoiced' for invoice_status in line_invoice_status):
                    order.invoice_status = 'invoiced'
            else:
                order.invoice_status = 'no'

    @api.depends('work_order_lines.invoice_lines', 'service_lines.invoice_lines')
    def _get_invoiced(self):
        for order in self:
            invoices = order.work_order_lines.mapped('invoice_lines').mapped('invoice_id').filtered(
                lambda r: r.type in ('out_invoice', 'out_refund'))
            invoices += order.service_lines.mapped('invoice_lines').mapped('invoice_id').filtered(
                lambda r: r.type in ('out_invoice', 'out_refund'))
            invoices = self.env['account.invoice'].search([('id', 'in', invoices.ids)])
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    team_id = fields.Many2one(
        'crm.team', 'Sales Team',
        change_default=True, default=_get_default_team, check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    def _last_signature(self):
        if self.time_ids:
            self.last_signature = self.time_ids[-1]["signature_id"].signature

    def action_sign_time_ids(self, id_signature):
        signature_id = self.env["work.order.signature"].search([("id", "=", id_signature)])
        for record in self:
            message, signature_name = "", ""
            for time_tracking_id in record.time_ids:
                if not time_tracking_id.signature_id and time_tracking_id.date_end:
                    time_tracking_id.signature_id = signature_id.id
                    message = "Signed by {}".format(signature_id.signed_by)
                    signature_name = "{} - {} - {}".format(
                        self.name, signature_id.signed_by, datetime.now()
                    )

            if message and signature_name:
                self.message_post(
                    body=message,
                    message_type="notification",
                    attachments=[(signature_name, base64.b64decode(signature_id.signature))],
                )

    @api.depends("time_ids")
    def compute_unsigned_due_hours(self):
        for record in self:
            record.unsigned_due_hours = sum(
                record.time_ids.filtered(
                    lambda time_tracking_id: not time_tracking_id.signature_id
                ).mapped("unit_amount")
            )
            return record.unsigned_due_hours

    @api.model
    def default_get(self, fields):
        res = super(WorkOrder, self).default_get(fields)
        irDefault = self.env["ir.default"].sudo()
        allow = irDefault.get("res.config.settings", "manual_category_invoice")
        if self.user_has_groups('work_order.group_work_order_category_invoice'):
            res["manual_category_invoice"] = allow
        else:
            res["manual_category_invoice"] = True
        return res

    @api.depends(
        "work_order_lines.price_subtotal",
        "invoice_method",
        "time_ids",
        "service_lines.price_subtotal",
        "pricelist_id.currency_id",
    )
    def _amount_untaxed(self):
        for record in self:
            total = sum(operation.price_subtotal for operation in record.work_order_lines)
            total += sum(service.price_subtotal for service in record.service_lines)
            record.amount_untaxed = record.pricelist_id.currency_id.round(total)

    @api.depends(
        "work_order_lines.price_unit",
        "work_order_lines.product_uom_qty",
        "work_order_lines.product_id",
        "service_lines.price_unit",
        "service_lines.product_uom_qty",
        "service_lines.product_id",
        "pricelist_id.currency_id",
        "partner_id",
        "time_ids",
    )
    def _amount_tax(self):
        for record in self:
            val = 0.0
            for operation in record.work_order_lines:
                if operation.tax_id:
                    tax_calculate = operation.tax_id.compute_all(
                        operation.price_unit,
                        record.pricelist_id.currency_id,
                        operation.product_uom_qty,
                        operation.product_id,
                        record.partner_id,
                    )
                    for c in tax_calculate["taxes"]:
                        val += c["amount"]
            for service in record.service_lines:
                if service.tax_id:
                    tax_calculate = service.tax_id.compute_all(
                        service.price_unit,
                        record.pricelist_id.currency_id,
                        service.product_uom_qty,
                        service.product_id,
                        record.partner_id,
                    )
                    for c in tax_calculate["taxes"]:
                        val += c["amount"]
            record.amount_tax = val

    @api.depends("amount_untaxed", "amount_tax")
    def _amount_total(self):
        for record in self:
            record.amount_total = record.pricelist_id.currency_id.round(
                record.amount_untaxed + record.amount_tax
            )

    @api.depends("work_order_member_ids", "category_id", "work_order_team_id")
    def _compute_allowed(self):
        for record in self:
            record._onchange_domains()
            record.allowed_to_time_tracking = False
            if record.state not in ['confirmed', 'in_process']:
                record.allowed_to_time_tracking = False
            else:
                if not record.work_order_team_id:
                    record.allowed_to_time_tracking = True
                else:
                    if self._uid in record.work_order_member_ids.ids:
                        record.allowed_to_time_tracking = True

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        if not self.partner_id:
            self.work_address_id = False
            self.partner_invoice_id = False
            self.fiscal_position_id = False
            self.pricelist_id = self.env["product.pricelist"].search([], limit=1).id
            irDefault = self.env["ir.default"].sudo()
            work_order_analytic_method = irDefault.get(
                "res.config.settings", "work_order_analytic_method"
            )
            if work_order_analytic_method == "new_by_partner":
                self.analytic_account_id = False
        else:
            irDefault = self.env["ir.default"].sudo()
            work_order_analytic_method = irDefault.get(
                "res.config.settings", "work_order_analytic_method"
            )
            if work_order_analytic_method == "new_by_partner":
                self.analytic_account_id = self.partner_id.analytic_account_id.id
            addresses = self.partner_id.address_get(["delivery", "invoice", "contact"])
            self.work_address_id = addresses["delivery"] or addresses["contact"]
            self.partner_invoice_id = addresses["invoice"]
            self.pricelist_id = self.partner_id.property_product_pricelist.id
            self.fiscal_position_id = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id,
                                                                                              self.work_address_id.id)
            partner_user = self.partner_id.user_id or self.partner_id.commercial_partner_id.user_id
            user_id = partner_user.id
            if not self.env.context.get('not_self_saleperson'):
                user_id = user_id or self.env.uid
            if self.user_id.id != user_id:
                self.user_id = user_id
            if self.partner_id.team_id:
                self.team_id = self.partner_id.team_id.id

    @api.model
    def get_work_order_analytic_method(self):
        """
         Check if the analytic method is set to "None".
        This is useful for 3rd party clients as they can't read sudo()-dependant
        methods

        :return: true if the selected conf has "none" as its value
        """
        return self.env["ir.default"].sudo().get(
            "res.config.settings", "work_order_analytic_method"
        ) == "none"

    @api.multi
    def action_work_order_cancel_draft(self):
        if self.filtered(lambda work_order: work_order.state != "cancel"):
            raise UserError(
                _(
                    "Work order must be cancelled in order to \
                reset it to draft."
                )
            )
        self.mapped("work_order_lines").write({"state": "draft"})
        return self.write({"state": "draft"})

    @api.multi
    def action_work_order_confirm(self):
        """ Work order state is set to 'To be invoiced' when invoice method
        is 'Before Work Order' else state becomes 'Confirmed'.
        @param *arg: Arguments
        @return: True
        """
        if self.filtered(lambda work_order: work_order.state != "draft"):
            raise UserError(_("Can only confirm draft work orders."))
        before_work_order = self.filtered(
            lambda work_order: work_order.invoice_method == "b4start"
        )
        before_work_order.write({"state": "2binvoiced"})
        to_confirm = self - before_work_order
        lines_to_confirm = to_confirm.mapped("work_order_lines")
        lines_to_confirm.write({"state": "confirmed"})
        to_confirm.write({"state": "confirmed"})
        return True

    @api.multi
    def action_work_order_cancel(self):
        if self.filtered(lambda work_order: work_order.state == "done"):
            raise UserError(_("Cannot cancel finished work orders."))
        # if any(work_order.invoiced for work_order in self):
        #     for record in self:
        #         record.invoice_id.unlink()
        self.mapped("work_order_lines").write({"state": "cancel"})
        return self.write({"state": "cancel"})

    @api.multi
    def action_send_mail(self):
        self.ensure_one()
        template_id = self.env.ref("work_order.mail_template_work_order_quotation").id
        ctx = {
            "default_model": "work.order",
            "default_res_id": self.id,
            "default_use_template": bool(template_id),
            "default_template_id": template_id,
            "default_composition_mode": "comment",
        }
        return {
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "target": "new",
            "context": ctx,
        }

    @api.multi
    def action_send_mail_work_order_done(self):
        self.ensure_one()
        template_id = self.env.ref("work_order.mail_template_work_order_done").id
        ctx = {
            "default_model": "work.order",
            "default_res_id": self.id,
            "default_use_template": bool(template_id),
            "default_template_id": template_id,
            "default_composition_mode": "comment",
        }
        return {
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "target": "new",
            "context": ctx,
        }

    @api.multi
    def print_work_order(self):
        return self.env.ref("work_order.action_report_work_order").report_action(self)

    def action_work_order_invoice_create(self):
        for work_order in self:
            work_order.action_invoice_create()
            if work_order.invoice_method == "b4start":
                work_order.action_work_order_ready()
            elif work_order.invoice_method == "after_work_order":
                work_order.write({"state": "done"})
        return True

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a work order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        # ensure a correct context for the _get_default_journal method and company-dependent fields
        company_id = self.company_id.id
        journal_id = (
            self.env['account.invoice'].with_context(company_id=company_id or self.env.user.company_id.id).default_get(
                ['journal_id'])['journal_id'])
        if not journal_id:
            raise UserError(_('Please define an accounting sales journal for this company.'))
        self = self.with_context(default_company_id=self.company_id.id, force_company=self.company_id.id)

        invoice_vals = {
            'type': 'out_invoice',
            'comment': self.quotation_notes,
            'currency_id': self.pricelist_id.currency_id.id,
            'user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_invoice_id.id or self.partner_id.id,
            'partner_shipping_id': self.work_address_id.id,
            'partner_bank_id': self.company_id.partner_id.bank_ids[:1].id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
            'journal_id': journal_id,  # company comes from the journal
            'origin': self.name,
            # 'invoice_payment_term_id': self.payment_term_id.id,
            # 'invoice_payment_ref': self.reference,
            'work_order_ids': [(4, self.id)],
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals

    def _get_invoice_grouping_keys(self):
        return ['company_id', 'partner_id', 'currency_id']

    def action_invoice_create(self, group=False):
        """ Creates invoice(s) for work order.
        @param group: It is set to true when group invoice is to be generated.
        @return: Invoice Ids.
        """
        if not self.env['account.invoice'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.invoice']
        # res = dict.fromkeys(self.ids, False)
        # invoices_group = {}
        # InvoiceLine = self.env["account.move.line"]
        # Invoice = self.env["account.move"]
        invoice_vals_list = []
        for work_order in self.filtered(
                lambda work_order: work_order.state not in ("draft", "cancel")
                                   and work_order.invoice_status == "to invoice"
        ):
            if not work_order.partner_id.id and not work_order.partner_invoice_id.id:
                raise UserError(
                    _(
                        "You have to select a Partner Invoice Address \
                    in the work order form!"
                    )
                )
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            pending_section = None
            invoice_vals = work_order._prepare_invoice()
            for line in work_order.work_order_lines:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue
                if float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if line.qty_to_invoice > 0 or (line.qty_to_invoice < 0):
                    if pending_section:
                        invoice_vals['invoice_line_ids'].append((0, 0, pending_section._prepare_invoice_line()))
                        pending_section = None
                    invoice_vals['invoice_line_ids'].append((0, 0, line._prepare_invoice_line()))
            pending_section = None
            for service in work_order.service_lines:
                if service.display_type == 'line_section':
                    pending_section = service
                    continue
                if float_is_zero(service.qty_to_invoice, precision_digits=precision):
                    continue
                if service.qty_to_invoice > 0 or (service.qty_to_invoice < 0):
                    if pending_section:
                        invoice_vals['invoice_line_ids'].append((0, 0, pending_section._prepare_invoice_line()))
                        pending_section = None
                    invoice_vals['invoice_line_ids'].append((0, 0, service._prepare_invoice_line()))

            if not invoice_vals['invoice_line_ids']:
                raise UserError(_('There is no invoiceable line.'))

            invoice_vals_list.append(invoice_vals)
        if not invoice_vals_list:
            for wo in self:
                if wo.invoice_status in ['no', 'to invoice']:
                    raise UserError(_(
                        'There is no invoiceable line.'))

        if group:
            new_invoice_vals_list = []
            invoice_grouping_keys = self._get_invoice_grouping_keys()
            for grouping_keys, invoices in groupby(invoice_vals_list,
                                                   key=lambda x: [x.get(grouping_key) for grouping_key in
                                                                  invoice_grouping_keys]):
                origins = set()
                ref_invoice_vals = None
                for invoice_vals in invoices:
                    if not ref_invoice_vals:
                        ref_invoice_vals = invoice_vals
                    else:
                        ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                    origins.add(invoice_vals['origin'])
                ref_invoice_vals.update({
                    'origin': ', '.join(origins),
                })
                new_invoice_vals_list.append(ref_invoice_vals)
            invoice_vals_list = new_invoice_vals_list

        moves = self.env['account.invoice'].sudo().with_context(default_type='out_invoice').create(invoice_vals_list)

        return moves

    @api.multi
    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids')
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.invoice_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_work_order_ready(self):
        self.mapped("work_order_lines").write({"state": "confirmed"})
        return self.write({"state": "confirmed"})

    @api.multi
    def action_work_order_start(self):
        """ Writes work order state to 'In process'
        @return: True
        """
        if self.filtered(lambda r: r.state not in ["confirmed"]):
            raise UserError(
                _(
                    "Work order must be confirmed before \
                starting the work."
                )
            )
        self.mapped("work_order_lines").write({"state": "confirmed"})

        if self.user_has_groups('work_order.group_timesheet_work_order'):
            for record in self:
                if record.analytic_account_id:
                    time_tracking = self.env["account.analytic.line"].create({
                        "account_id": record.analytic_account_id.id,
                        "date": datetime.now().date(),
                        "user_id": self._uid,
                        "date_start": datetime.now()
                    }
                    )
                    record.update({"time_ids": [(4, time_tracking.id)]})

        return self.write({"state": "in_process"})

    @api.multi
    def action_work_order_end(self):
        """ Writes work order state to 'To be invoiced' if invoice method is
        After work order else state is set to 'Ready'.
        @return: True
        """
        if self.filtered(lambda work_order: work_order.state != "in_process"):
            raise UserError(
                _(
                    "Work Order must be 'In process' in order to end \
                the work order."
                )
            )
        for record in self:
            record.write({"finished": True})
            vals = {"state": "done"}
            vals["move_id"] = record.action_work_order_done().get(record.id)
            qty_invoiced = sum(record.service_lines.mapped('qty_invoiced')) + sum(
                record.work_order_lines.mapped('qty_invoiced'))
            product_uom_qty = sum(record.service_lines.mapped('product_uom_qty')) + sum(
                record.work_order_lines.mapped('product_uom_qty'))
            if qty_invoiced < product_uom_qty and record.invoice_method == "after_work_order":
                vals["state"] = "2binvoiced"
            record.write(vals)

            for time_tracking_id in record.time_ids:
                if time_tracking_id.date_end is False:
                    time_tracking_id.date_end = datetime.now()
            record.time_ids._compute_duration()
        return True

    @api.multi
    def action_work_order_done(self):
        """ Creates stock move for operation.
        @return: Move ids of final products

        """
        if self.filtered(lambda work_order: not work_order.finished):
            raise UserError(
                _(
                    "Work Order must be finished in order \
                to make the product moves."
                )
            )
        res = {}
        Move = self.env["stock.move"]
        for work_order in self:
            owner_id = work_order.partner_id.id
            moves = self.env["stock.move"]
            for operation in work_order.work_order_lines.filtered(lambda r: r.product_id):
                move = Move.create(
                    {
                        "name": work_order.name,
                        "product_id": operation.product_id.id,
                        "product_uom_qty": operation.product_uom_qty,
                        "product_uom": operation.product_uom.id,
                        "partner_id": work_order.work_address_id.id,
                        "location_id": operation.location_id.id,
                        "location_dest_id": operation.location_dest_id.id,
                        "move_line_ids": [
                            (
                                0,
                                0,
                                {
                                    "product_id": operation.product_id.id,
                                    "lot_id": operation.lot_id.id,
                                    "product_uom_qty": 0,
                                    "product_uom_id": operation.product_uom.id,
                                    "qty_done": operation.product_uom_qty,
                                    "package_id": False,
                                    "result_package_id": False,
                                    "owner_id": owner_id,
                                    "location_id": operation.location_id.id,
                                    "location_dest_id": operation.location_dest_id.id,
                                },
                            )
                        ],
                        "work_order_id": work_order.id,
                        "origin": work_order.name,
                    }
                )
                moves |= move
                operation.write({"move_id": move.id, "state": "done"})
            moves._action_done()
        return res

    def write(self, vals):
        keys = vals.keys()

        if vals.get("date_planned_finished"):
            start = vals.get("date_planned_start") or self.date_planned_start
            start = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(
                vals.get("date_planned_finished"), "%Y-%m-%d %H:%M:%S"
            )
            vals["duration_expected"] = (end - start) / timedelta(minutes=1) / 60

        # if "date_planned_start" in keys:
        #     vals["planned_start_date"] = vals["date_planned_start"].split()[0]

        if "duration_expected" in keys and not vals.get("date_planned_finished"):
            if vals.get("duration_expected") < 0:
                raise UserError(_("Please, select a valid expected duration"))

            if vals.get("duration_expected") == 0:
                if self.date_planned_start:
                    if vals.get("date_planned_start") is not False:
                        raise UserError(_("Please, select a valid expected duration"))
                else:
                    if vals.get("date_planned_start"):
                        raise UserError(_("Please, select a valid expected duration"))
            start = vals.get("date_planned_start")
            if not start:
                start = self.date_planned_start
                if start:
                    dur = vals.get("duration_expected")
                    i, dec = divmod(dur, 1)
                    dec = (dec / 100 * 60) * 100
                    vals["date_planned_finished"] = start + timedelta(
                        hours=i, minutes=dec
                    )
                    vals["date_planned_finished"] = vals[
                        "date_planned_finished"
                    ].strftime("%Y-%m-%d, %H:%M:%S")

        if vals.get("date_planned_start"):
            if not vals.get("duration_expected") and not self.duration_expected:
                raise UserError(_("Please, select a valid expected duration"))
            elif "duration_expected" in keys:
                if vals.get("duration_expected") <= 0:
                    raise UserError(_("Please, select a valid expected duration"))

        return super(WorkOrder, self).write(vals)

    def unlink(self):
        for record in self:
            if record.state not in ("draft", "cancel"):
                raise UserError(
                    _("You can not delete a work order! You can archieve it.")
                )
        return super(WorkOrder, self).unlink()

    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            if "company_id" in vals:
                vals["name"] = self.env["ir.sequence"].with_context(
                    force_company=vals["company_id"]
                ).next_by_code("work.order") or _("New")
            else:
                vals["name"] = self.env["ir.sequence"].next_by_code("work.order") or _(
                    "New"
                )
        irDefault = self.env["ir.default"].sudo()
        work_order_analytic_method = irDefault.get(
            "res.config.settings", "work_order_analytic_method"
        )
        if work_order_analytic_method == "new_by_partner":
            partner_id = self.env['res.partner'].search([('id', '=', vals.get('partner_id'))])
            if "analytic_account_id" not in vals or not vals.get("analytic_account_id"):
                if not partner_id.analytic_account_id:
                    analytic_account = self.env['account.analytic.account'].create({
                        'name': partner_id.name,
                        'company_id': vals.get('company_id', self.env.user.company_id.id),
                        'partner_id': vals.get('partner_id'),
                        'active': True,
                    })
                    vals['analytic_account_id'] = analytic_account.id
                    partner_id.analytic_account_id = analytic_account.id
                else:
                    vals['analytic_account_id'] = partner_id.analytic_account_id.id

        if "duration_expected" in vals:
            if vals.get("duration_expected") == 0.0 and vals["date_planned_start"]:
                raise UserError(_("Select a expected duration."))

        if vals.get("date_planned_start"):
            # vals["planned_start_date"] = vals["date_planned_start"].split()[0]
            if not vals.get("duration_expected") or vals.get("duration_expected") <= 0:
                raise UserError(_("Please, select a valid expected duration"))
            else:
                dur = vals.get("duration_expected")
                i, dec = divmod(dur, 1)
                dec = (dec / 100 * 60) * 100
                vals["date_planned_finished"] = datetime.strptime(
                    vals.get("date_planned_start"), "%Y-%m-%d %H:%M:%S"
                ) + timedelta(hours=i, minutes=dec)
                vals["date_planned_finished"] = vals["date_planned_finished"].strftime(
                    "%Y-%m-%d, %H:%M:%S"
                )

        return super(WorkOrder, self).create(vals)

    @api.depends("time_ids.date_start")
    def _compute_date_start(self):
        for record in self:
            if record.time_ids:
                date_list = [x for x in record.time_ids.mapped("date_start") if x]
                record.date_start = min(date_list)

    @api.depends("time_ids.date_end")
    def _compute_date_finished(self):
        for record in self:
            flag = False
            for time_id in record.time_ids:
                if time_id.date_end:
                    flag = True
            if flag:
                record.date_finished = max(
                    record.time_ids.filtered(
                        lambda time_tracking_id: time_tracking_id.date_end
                    ).mapped("date_end")
                )

    @api.depends("time_ids.unit_amount")
    def _compute_duration(self):
        for record in self:
            unit_amount = sum(record.time_ids.mapped("unit_amount"))
            record.duration = unit_amount
            irDefault = self.env["ir.default"].sudo()
            operation_id_default = irDefault.get(
                "res.config.settings", "operation_id_default"
            )
            operation_by_default = irDefault.get(
                "res.config.settings", "operation_by_default"
            )
            if record.id:
                if not record.time_ids:
                    if record.service_lines:
                        line = record.service_lines.filtered(
                            lambda r: r.product_id and r.product_id.id == operation_id_default
                        )
                        if line:
                            line.unlink()
                else:
                    if (
                            operation_id_default
                            and operation_by_default
                            and record.invoice_status != "invoiced" and record.state != "done"
                    ):
                        operation = self.env["product.product"].search(
                            [("id", "=", operation_id_default)]
                        )
                        line = record.service_lines.filtered(
                            lambda r: r.product_id.id == operation_id_default
                        )
                        if line:
                            line.write({"product_uom_qty": unit_amount})
                        else:
                            service = self.env["work.order.service"].create(
                                {
                                    "work_order_id": self.id,
                                    "product_id": operation.id,
                                    "name": operation.name,
                                    "price_unit": operation.list_price,
                                    "tax_id": [(6, 0, operation.taxes_id.ids)],
                                    "product_uom": operation.uom_id.id,
                                    "product_uom_qty": unit_amount,
                                }
                            )
                        record._amount_untaxed()
                        record._amount_tax()
                        record._amount_total()

    @api.onchange("category_id")
    def _onchange_category_id(self):
        for record in self:
            # ids = []
            # teams = self.env["work.order.team"].search([])
            # for team in teams:
            #     if record.category_id in team.category_ids:
            #         ids.append(team.id)
            # record.work_order_team_ids = [(6, 0, ids)]

            if record.user_has_groups('work_order.group_work_order_category_invoice') \
                    and record.category_id and not record.work_order_lines.invoice_lines:
                if record.category_id.invoice_method:
                    # If work order is already invoiced
                    # it is not posible to change the
                    # invoice method.
                    record.invoice_method = record.category_id.invoice_method
                else:
                    record.invoice_method = 'none'

    @api.multi
    @api.onchange("category_id", "work_order_team_id", "resp")
    def _onchange_domains(self):
        if self.category_id:
            if self.work_order_team_id:
                if self.category_id not in self.work_order_team_id.category_ids:
                    self.update({"work_order_team_id": False, "resp": False})
                    return {
                        "domain": {
                            "work_order_team_id": [
                                ("id", "in", self.work_order_team_ids.ids)
                            ],
                            "resp": [
                                (
                                    "id",
                                    "in",
                                    self.work_order_team_ids.mapped("member_ids").ids,
                                )
                            ],
                        }
                    }
                else:
                    return {
                        "domain": {
                            "work_order_team_id": [
                                ("id", "in", self.work_order_team_ids.ids)
                            ],
                            "resp": [
                                ("id", "in", self.work_order_team_id.member_ids.ids)
                            ],
                        }
                    }
            else:
                if self.resp not in self.work_order_team_ids.mapped("member_ids"):
                    self.update({"resp": False})
                return {
                    "domain": {
                        "category_id": [],
                        "work_order_team_id": [("id", "in", self.work_order_team_ids.ids)],
                        "resp": [
                            ("id", "in", self.work_order_team_ids.mapped("member_ids").ids)
                        ],
                    }
                }
        else:
            if self.work_order_team_id:
                if self.resp not in self.work_order_team_id.member_ids:
                    self.update({"resp": False})
                return {
                    "domain": {
                        "work_order_team_id": [],
                        "resp": [("id", "in", self.work_order_team_id.member_ids.ids)]
                    }
                }
            else:
                return {
                    "domain": {"category_id": [], "work_order_team_id": [], "resp": []}
                }

    @api.depends("work_order_team_id")
    def _compute_work_order_member_ids(self):
        for record in self:
            if not record.work_order_team_id:
                if not record.category_id:
                    record.work_order_member_ids = [(6, 0, self.env['res.users'].search([]).ids)]
                else:
                    ids = []
                    for team in record.category_id.team_ids:
                        ids += team.member_ids.ids
                    record.work_order_member_ids = [(6, 0, ids)]
            else:
                record.work_order_member_ids = [(6, 0, record.work_order_team_id.member_ids.ids)]

    @api.depends("category_id")
    def _compute_work_order_team_ids(self):
        for record in self:
            teams = self.env["work.order.team"].search([])
            if not record.category_id:
                record.work_order_team_ids = [(6, 0, teams.ids)]
            else:
                ids = []
                for team in teams:
                    if record.category_id in team.category_ids:
                        ids.append(team.id)
                record.work_order_team_ids = [(6, 0, ids)]
