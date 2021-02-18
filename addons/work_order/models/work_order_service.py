from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_is_zero, float_compare


class WorkOrderService(models.Model):
    _name = "work.order.service"
    _description = "Work Order Services Line"

    work_order_id = fields.Many2one(
        "work.order",
        "Work Order Reference",
        index=True,
        ondelete="cascade",
        required=True,
    )

    name = fields.Char("Description", index=True, required=True)

    product_id = fields.Many2one("product.product", "Product")

    product_uom_qty = fields.Float(
        "Quantity",
        digits=dp.get_precision('Product Unit of Measure'),
        required=True,
        default=1.0,
    )

    price_unit = fields.Float("Unit Price", required=True, digits=dp.get_precision('Product Price'))

    product_uom = fields.Many2one("uom.uom", "Product Unit of Measure")

    price_subtotal = fields.Float(
        "Subtotal", compute="_compute_price_subtotal",
    )

    tax_id = fields.Many2many(
        "account.tax",
        "work_order_service_line_tax",
        "work_order_service_line_id",
        "tax_id",
        "Taxes",
    )

    invoiced = fields.Boolean("Invoiced", copy=False, readonly=True)

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
        "Status",
        related="work_order_id.state",
        default="draft",
        store=True,
        copy=False,
        readonly=True,
        required=True,
        help="The status of a work order line is set automatically to the one \
             of the linked work order.",
    )

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.user.company_id.id,
        index=1,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.user.company_id.currency_id.id,
        required=True,
    )

    sequence = fields.Integer(string='Sequence', default=10)

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")

    _sql_constraints = [
        ('accountable_required_fields',
            "CHECK(display_type IS NOT NULL OR (product_id IS NOT NULL AND product_uom IS NOT NULL))",
            "Missing required fields on accountable work order line."),
        ('non_accountable_null_fields',
            "CHECK(display_type IS NULL OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0 AND product_uom IS NULL))",
            "Forbidden values on non-accountable work order line"),
    ]

    invoice_lines = fields.Many2many(
        'account.invoice.line',
        'work_order_service_invoice_rel',
        'work_order_service_id',
        'invoice_line_id',
        string='Invoice Lines',
        copy=False
    )

    invoice_status = fields.Selection([
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ],
        string='Invoice Status',
        compute='_compute_invoice_status',
        store=True,
        readonly=True,
        default='no'
    )

    qty_to_invoice = fields.Float(
        compute='_get_to_invoice_qty', string='To Invoice Quantity', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))
    qty_invoiced = fields.Float(
        compute='_get_invoice_qty', string='Invoiced Quantity', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'))

    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', readonly=True, default=True)

    @api.depends('product_id', 'work_order_id.state', 'qty_invoiced')
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ['done', 'cancel'] or (line.state == 'sale' and line.qty_invoiced > 0):
                line.product_updatable = False
            else:
                line.product_updatable = True

    @api.depends('state', 'product_uom_qty', 'qty_to_invoice', 'qty_invoiced', 'invoice_lines', 'invoice_lines.quantity')
    def _compute_invoice_status(self):
        """
        Compute the invoice status of a WO line. Possible statuses:
        - no: if the WO is not in status '2binvoiced', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: we refer to the quantity to invoice of the line. Refer to method
          `_get_to_invoice_qty()` for more information on how this quantity is calculated.
        - invoiced: the quantity invoiced is larger or equal to the quantity of the line.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if line.work_order_id.invoice_method == 'none':
                line.invoice_status = 'no'
            elif line.work_order_id.invoice_method == 'b4start' and line.state not in ['draft', 'cancel', 'in_process']:
                if float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                    line.invoice_status = 'invoiced'
                elif line.state != "2binvoiced" or not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    line.invoice_status = 'to invoice'
            elif line.work_order_id.invoice_method == 'after_work_order' and line.state not in ['draft', 'cancel', 'confirmed', 'in_process']:
                if float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                    line.invoice_status = 'invoiced'
                elif line.state != "2binvoiced" or not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    line.invoice_status = 'to invoice'
            else:
                line.invoice_status = 'no'

    @api.depends('qty_invoiced', 'product_uom_qty', 'work_order_id.state')
    def _get_to_invoice_qty(self):
        """
        Compute the quantity to invoice.
        """
        for line in self:
            if line.work_order_id.state in ['2binvoiced', 'done']:
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
            else:
                line.qty_to_invoice = 0

    @api.depends('invoice_lines.invoice_id.state', 'invoice_lines.quantity')
    def _get_invoice_qty(self):
        """
        Compute the quantity invoiced. If case of a refund, the quantity invoiced is decreased. Note
        that this is the case only if the refund is generated from the SO and that is intentional: if
        a refund made would automatically decrease the invoiced quantity, then there is a risk of reinvoicing
        it automatically, which may not be wanted at all. That's why the refund has to be created from the SO
        """
        for line in self:
            qty_invoiced = 0.0
            for invoice_line in line.invoice_lines:
                if invoice_line.invoice_id.state != 'cancel':
                    if invoice_line.invoice_id.type == 'out_invoice':
                        qty_invoiced += invoice_line.uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
                    elif invoice_line.invoice_id.type == 'out_refund':
                        qty_invoiced -= invoice_line.uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
            line.qty_invoiced = qty_invoiced

    @api.depends("price_unit", "work_order_id", "product_uom_qty", "product_id")
    def _compute_price_subtotal(self):
        for record in self:
            taxes = record.tax_id.compute_all(
                record.price_unit,
                record.work_order_id.pricelist_id.currency_id,
                record.product_uom_qty,
                record.product_id,
                record.work_order_id.partner_id,
            )
            record.price_subtotal = taxes["total_excluded"]

    @api.onchange("work_order_id", "product_id", "product_uom_qty")
    def onchange_product_id(self):
        """ On change of product it sets product quantity, tax account, name,
        uom of product, unit price and price subtotal. """
        if not self.product_id:
            return

        partner = self.work_order_id.partner_id
        pricelist = self.work_order_id.pricelist_id

        if partner and self.product_id:
            self.tax_id = partner.property_account_position_id.map_tax(
                self.product_id.taxes_id, self.product_id, partner
            ).ids
        if self.product_id:
            self.name = self.product_id.display_name
            self.product_uom = self.product_id.uom_id.id

        warning = False
        if not pricelist:
            warning = {
                "title": _("No Pricelist!"),
                "message": _(
                    "You have to select a pricelist in the Work Order \
                      form !\n Please set one before choosing a product."
                ),
            }
        else:
            price = pricelist.get_product_price(
                self.product_id, self.product_uom_qty, partner
            )
            if price is False:
                warning = {
                    "title": _("No valid pricelist line found !"),
                    "message": _(
                        "Couldn't find a pricelist line matching this \
                          product and quantity.\nYou have to change either\
                           the product, the quantity or the pricelist."
                    ),
                }
            else:
                self.price_unit = price
        if warning:
            return {"warning": warning}

    def write(self, vals):
        if 'display_type' in vals and self.filtered(lambda line: line.display_type != vals.get('display_type')):
            raise UserError(_("You cannot change the type of a work order line. Instead you should delete the current line and create a new line of the proper type."))
        return super(WorkOrderService, self).write(vals)

    @api.model
    def _prepare_add_missing_fields(self, values):
        """ Deduce missing required fields from the onchange """
        res = {}
        onchange_fields = ['name', 'price_unit', 'product_uom', 'tax_id']
        if values.get('work_order_id') and values.get('product_id') and any(f not in values for f in onchange_fields):
            line = self.new(values)
            line.onchange_product_id()
            for field in onchange_fields:
                if field not in values:
                    res[field] = line._fields[field].convert_to_write(line[field], line)
        return res

    @api.model_create_multi
    def create(self, vals):
        for values in vals:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, product_uom_qty=0, product_uom=False)

            values.update(self._prepare_add_missing_fields(values))
        new_id = super(WorkOrderService, self).create(vals)
        return new_id

    def _prepare_invoice_line(self):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        product = self.product_id.with_context(force_company=self.company_id.id)
        account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        if not account and self.product_id:
            raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') %
                (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))
        fpos = self.work_order_id.fiscal_position_id or self.work_order_id.partner_id.property_account_position_id
        if fpos and account:
            account = fpos.map_account(account)
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'account_id': account.id,
            'product_id': self.product_id.id,
            'uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            # 'discount': self.discount,
            'price_unit': self.price_unit,
            'invoice_line_tax_ids': [(6, 0, self.tax_id.ids)],
            'account_analytic_id': self.work_order_id.analytic_account_id.id,
            # 'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'work_order_service_ids': [(4, self.id)],
        }

        # if self.display_type:
        #     res['account_id'] = False
        return res
