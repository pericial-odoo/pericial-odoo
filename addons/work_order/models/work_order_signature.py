import base64
from odoo import api, fields, models
from datetime import datetime


class WorkOrderSignature(models.Model):
    _name = "work.order.signature"
    _description = "Time tracking signature"
    _rec_name = "signed_by"

    signature = fields.Binary(string="Signature")

    signed_by = fields.Text(string="Signed by")

    account_analytic_line_ids = fields.One2many(
        comodel_name='account.analytic.line',
        inverse_name='signature_id',
        string='Account analytic lines',
        required=False)
