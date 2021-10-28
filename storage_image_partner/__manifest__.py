# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Storage Image Partner",
    "summary": "Link images to partners",
    "version": "13.0.1.0.0",
    "category": "Storage",
    "website": "https://github.com/OCA/storage",
    "author": " ForgeFlow, Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "installable": True,
    "depends": ["storage_image"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner.xml",
        "views/partner_image_relation.xml",
    ],
}
