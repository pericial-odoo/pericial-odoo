from odoo import models, fields


class WorkOrder(models.Model):
    _inherit = "work.order"

    asset = fields.Char(
        string='Activo')

    file_number = fields.Char(
        string='Expediente')
