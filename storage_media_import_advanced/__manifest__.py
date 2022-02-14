# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Storage media import",
    "version": "13.0.1.0.0",
    "summary": "Import storage media using CSV",
    "author": "ForgeFlow, Odoo Community Association (OCA)",
    "company": "ForgeFlow",
    "maintainer": "HviorForgeFlow",
    "website": "https://github.com/OCA/storage",
    "category": "Storage",
    "depends": ["storage_media", "queue_job"],
    "external_dependencies": {
        "python": ["python-magic", "validators"],
        "deb": ["libmagic1"],
    },
    "data": [
        "data/ir_cron.xml",
        "data/queue_job_channel_data.xml",
        "data/queue_job_function_data.xml",
        "security/ir_model_access.xml",
        "views/storage_media_import_view.xml",
        "views/report_html.xml",
    ],
    "license": "AGPL-3",
    "installable": True,
}
