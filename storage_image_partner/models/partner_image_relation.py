# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class PartnerImageRelation(models.Model):
    _name = "partner.image.relation"
    _inherit = "image.relation.abstract"
    _description = "Partner Image Relation"

    partner_id = fields.Many2one("res.partner")
