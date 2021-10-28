# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    image_ids = fields.One2many(
        comodel_name="partner.image.relation",
        inverse_name="partner_id",
        string="Images",
    )
