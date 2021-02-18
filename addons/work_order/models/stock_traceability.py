from odoo import models, api


class WorkOrderStockReport(models.TransientModel):
    _inherit = "stock.traceability.report"

    @api.model
    def get_links(self, move_line):
        res_model, res_id, ref = super(WorkOrderStockReport, self).get_links(move_line)
        if move_line.move_id.work_order_id:
            res_model = "work.order"
            res_id = move_line.move_id.work_order_id.id
            ref = move_line.move_id.work_order_id.name
        return res_model, res_id, ref
