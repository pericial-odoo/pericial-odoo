from odoo import fields, models


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    work_order_ids = fields.Many2many(
        comodel_name='work.order',
        relation='invoice_work_order',
        column1='invoice_id',
        column2='work_order_id',
        string='Work Orders')

    def action_invoice_cancel(self):
        for record in self:
            if record.work_order_ids:
                record.work_order_ids[0].state = "2binvoiced"
        return super(AccountInvoice, self).action_invoice_cancel()

    def action_invoice_open(self):
        for record in self:
            if record.work_order_ids:
                if record.work_order_ids[0].invoice_method == "b4start":
                    record.work_order_ids[0].state = "confirmed"

                elif record.work_order_ids[0].invoice_method == "after_work_order":
                    record.work_order_ids[0].state = "done"

        return super(AccountInvoice, self).action_invoice_open()

    def action_invoice_draft(self):
        for record in self:
            if record.work_order_ids:
                if record.work_order_ids[0].invoice_method == "b4start":
                    record.work_order_ids[0].state = "confirmed"
                elif record.work_order_ids[0].invoice_method == "after_work_order":
                    record.work_order_ids[0].state = "done"

        return super(AccountInvoice, self).action_invoice_draft()

    def unlink(self):
        for record in self:
            if record.work_order_ids:
                record.work_order_ids[0].state = "2binvoiced"
                record.invoice_ids = None
        return super(AccountInvoice, self).unlink()
