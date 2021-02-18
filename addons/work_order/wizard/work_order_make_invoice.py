from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MakeInvoice(models.TransientModel):
    _name = "work.order.make_invoice"
    _description = "Make Invoice"

    group = fields.Boolean("Group by partner invoice address")

    @api.multi
    def make_invoices(self):
        if not self._context.get("active_ids"):
            return {"type": "ir.actions.act_window_close"}
        new_invoice = {}
        for wizard in self:
            work_orders = self.env["work.order"].browse(self._context["active_ids"])
            new_invoice = work_orders.action_invoice_create(group=wizard.group)

            # We have to udpate the state of the given work_orders,
            # otherwise they remain 'to be invoiced'.
            # Note that this will trigger another call to the method
            # 'action_invoice_create',
            # but that second call will not do anything, since the work_orders
            # are already invoiced.
            work_orders.action_work_order_invoice_create()
        if not new_invoice:
            raise UserError(_('None of the selected work orders are invoiceable.'))
        return {
            "domain": [("id", "in", new_invoice.ids)],
            "name": "Invoices",
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "account.invoice",
            "view_id": False,
            "views": [
                (self.env.ref("account.invoice_tree").id, "tree"),
                (self.env.ref("account.invoice_form").id, "form"),
            ],
            "context": "{'type':'out_invoice'}",
            "type": "ir.actions.act_window",
        }
