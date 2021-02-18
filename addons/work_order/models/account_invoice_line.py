from odoo import api, fields, models, _


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'
    _order = 'invoice_id, sequence, id'

    work_order_line_ids = fields.Many2many(
        'work.order.line',
        'work_order_line_invoice_rel',
        'invoice_line_id', 'work_order_line_id',
        string='Work Order Lines', readonly=True, copy=False)

    work_order_service_ids = fields.Many2many(
        'work.order.service',
        'work_order_service_invoice_rel',
        'invoice_line_id', 'work_order_service_id',
        string='Work Order Services', readonly=True, copy=False)
