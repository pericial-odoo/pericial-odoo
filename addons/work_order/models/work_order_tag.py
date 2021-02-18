from odoo import fields, models


class WorkOrderTag(models.Model):
    _name = "work.order.tag"
    _description = "Work Order Tags"

    name = fields.Char(string="Name")
    color = fields.Integer(string="Color Index")
