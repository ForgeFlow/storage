# Copyright 2018 Akretion (http://www.akretion.com).
# Author: Sylvain Calador (<https://www.akretion.com>)
# Author: Saritha Sahadevan (<https://www.cybrosys.com>)
# Copyright 2020 Camptocamp (http://www.camptocamp.com)
# @author Simone Orsi <simone.orsi@camptocamp.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


import base64
import csv
import io
import logging
import os
import sys
from contextlib import closing
from urllib.request import urlopen
from zipfile import ZipFile

from odoo import _, api, exceptions, fields, models
from odoo.tools import date_utils

_logger = logging.getLogger(__name__)

try:
    import magic
    import validators
except (ImportError, IOError) as err:
    _logger.debug(err)


def gen_chunks(iterable, chunksize=10):
    """Chunk generator.

    Take an iterable and yield `chunksize` sized slices.
    "Borrowed" from connector_importer.
    """
    chunk = []
    last_chunk = False
    for i, line in enumerate(iterable):
        if i % chunksize == 0 and i > 0:
            yield chunk, last_chunk
            del chunk[:]
        chunk.append(line)
    last_chunk = True
    yield chunk, last_chunk


class StorageMediaImport(models.Model):

    _name = "storage.media.import"
    _description = "Handle import of storage media"

    @api.model
    def _default_csv_header(self):
        flds = ["name", "media_type", "path"]
        return ",".join(flds)

    storage_backend_id = fields.Many2one(
        "storage.backend", "Storage Backend", required=True
    )
    source_type = fields.Selection(
        [
            ("url", "URL"),
            ("zip_file", "Zip file"),
            ("external_storage", "External storage"),
        ],
        string="Source type",
        required=True,
        default="url",
    )
    filename = fields.Char()
    filename_zip = fields.Char()
    file_csv = fields.Binary(string="CSV file", required=True)
    csv_delimiter = fields.Char(
        string="CSV file delimiter", default=",", required=True,
    )
    csv_column_name = fields.Char(
        string="Product Reference column",
        help="The CSV File column name that holds the media name.",
        default="name",
        required=True,
    )
    csv_column_media_type = fields.Char(
        string="Media media_type Name column",
        help="The CSV File column name that holds the media media_type name.",
        default="media_type",
        required=True,
    )
    csv_column_file_path = fields.Char(
        string="Media file path column",
        help="The CSV File column name that holds the media file path or url.",
        default="path",
        required=True,
    )
    csv_delimiter = fields.Char(string="CSV file delimiter", default=",", required=True)
    source_zipfile = fields.Binary("ZIP with medias", required=False)
    source_storage_backend_id = fields.Many2one(
        "storage.backend", "Storage Backend with medias"
    )
    external_csv_path = fields.Char(
        string="Path to CSV file",
        help="Relative path of the CSV file located in the external storage",
    )
    options = fields.Serialized(readonly=True)
    overwrite = fields.Boolean(
        "Overwrite media with same name", sparse="options", default=False
    )
    create_missing_media_types = fields.Boolean(sparse="options", default=False)
    chunk_size = fields.Integer(
        sparse="options",
        default=10,
        help="How many lines will be handled in each job.",
    )
    report = fields.Serialized(readonly=True)
    report_html = fields.Html(readonly=True, compute="_compute_report_html")
    state = fields.Selection(
        [("new", "New"), ("scheduled", "Scheduled"), ("done", "Done")],
        string="Import state",
        default="new",
    )
    done_on = fields.Datetime()

    @api.depends("report")
    def _compute_report_html(self):
        tmpl = self.env.ref("storage_media_import_advanced.report_html")
        for record in self:
            if not record.report:
                record.report_html = ""
                continue
            report_html = tmpl.render({"record": record})
            record.report_html = report_html

    @api.model
    def _get_base64(self, file_path):
        res = {}
        binary = None
        mimetype = None
        binary = getattr(self, "_read_from_" + self.source_type)(file_path)
        if binary:
            mimetype = magic.from_buffer(binary, mime=True)
            res = {"mimetype": mimetype, "b64": base64.encodestring(binary)}
        return res

    def _read_from_url(self, file_path):
        if validators.url(file_path):
            return urlopen(file_path).read()
        return None

    def _read_from_zip_file(self, file_path):
        if not self.source_zipfile:
            raise exceptions.UserError(_("No zip file provided!"))
        file_content = base64.b64decode(self.source_zipfile)
        with closing(io.BytesIO(file_content)) as zip_file:
            with ZipFile(zip_file, "r") as z:
                try:
                    return z.read(file_path)
                except KeyError:
                    # File missing
                    return None

    def _read_from_external_storage(self, file_path):
        if not self.source_storage_backend_id:
            raise exceptions.UserError(_("No storage backend provided!"))
        return self.source_storage_backend_id._get_bin_data(file_path)

    def _read_csv(self):
        if self.file_csv:
            return base64.b64decode(self.file_csv)
        elif self.external_csv_path:
            return self.source_storage_backend_id._get_bin_data(self.external_csv_path)

    def _get_lines(self):
        lines = []
        mapping = {
            "name": self.csv_column_name,
            "media_type": self.csv_column_media_type,
            "file_path": self.csv_column_file_path,
        }
        with closing(io.BytesIO(self._read_csv())) as binary_file:
            csv_file = (line.decode("utf8") for line in binary_file)
            reader = csv.DictReader(csv_file, delimiter=self.csv_delimiter)
            csv.field_size_limit(sys.maxsize)
            for row in reader:
                try:
                    line = {key: row[column] for key, column in mapping.items()}
                except KeyError as e:
                    _logger.error(e)
                    raise exceptions.UserError(_("CSV Schema Incompatible"))
                lines.append(line)
        return lines

    def _get_options(self):
        return self.options or {}

    def action_import(self):
        self.report = self.report_html = False
        self.state = "scheduled"
        # Generate N chunks to split in several jobs.
        chunks = gen_chunks(
            self._get_lines(), chunksize=self._get_options().get("chunk_size")
        )
        for i, (chunk, is_last_chunk) in enumerate(chunks, 1):
            self.with_delay().do_import(lines=chunk, last_chunk=is_last_chunk)
            _logger.info(
                "Generated job for chunk nr %d. Is last: %s.",
                i,
                "yes" if is_last_chunk else "no",
            )

    def do_import(self, lines=None, last_chunk=False):
        lines = lines or self._get_lines()
        report = self._do_import(lines, options=self._get_options())
        # Refresh report
        extendable_keys = [
            "created",
            "file_not_found",
            "missing",
            "missing_media_types",
        ]
        prev_report = self.report or {}
        for k, v in report.items():
            if k in extendable_keys and prev_report.get(k):
                report[k] = sorted(set(prev_report[k] + v))

        # Lock as writing can come from several jobs
        sql = "SELECT id FROM %s WHERE ID IN %%s FOR UPDATE" % self._table
        self.env.cr.execute(sql, (tuple(self.ids),), log_exceptions=False)
        self.write(
            {
                "report": report,
                "state": "done" if last_chunk else self.state,
                "done_on": fields.Datetime.now() if last_chunk else False,
            }
        )
        return report

    def _do_import(self, lines, options=None):
        media_obj = self.env["storage.media"]
        media_type_obj = self.env["storage.media.type"]

        report = {
            "created": set(),
            "file_not_found": set(),
            "missing": [],
            "missing_media_types": [],
        }
        options = options or {}

        all_media_types = [x["media_type"] for x in lines if x["media_type"]]
        media_types = media_type_obj.search_read(
            [("name", "in", all_media_types)], ["name"]
        )
        media_type_by_name = {x["name"]: x["id"] for x in media_types}
        missing_media_types = set(all_media_types).difference(
            set(media_type_by_name.keys())
        )
        if missing_media_types:
            if options.get("create_missing_media_types"):
                for media_type in missing_media_types:
                    media_type_by_name[media_type] = media_type_obj.create(
                        {"name": media_type}
                    ).id
            else:
                report["missing_media_types"] = sorted(missing_media_types)

        for line in lines:
            file_path = line["file_path"]
            file_vals = self._prepare_file_values(file_path)
            if not file_vals:
                report["file_not_found"].add(line["name"])
                continue
            media_type_id = media_type_by_name.get(line["media_type"])
            file_vals.update(
                {"name": file_vals["name"], "media_type_id": media_type_id}
            )
            # storage_file = file_obj.create(file_vals)
            if options.get("overwrite"):
                domain = [
                    ("name", "=", line["name"]),
                    ("media_type_id", "=", media_type_id),
                ]
                media_obj.search(domain).unlink()
            media_obj.create(file_vals)
            report["created"].add(line["name"])
        report["created"] = sorted(report["created"])
        report["file_not_found"] = sorted(report["file_not_found"])
        return report

    def _prepare_file_values(self, file_path, filetype="media"):
        name = os.path.basename(file_path)
        file_data = self._get_base64(file_path)
        if not file_data:
            return {}
        vals = {
            "data": file_data["b64"],
            "name": name,
            "file_type": filetype,
            "mimetype": file_data["mimetype"],
            "backend_id": self.storage_backend_id.id,
        }
        return vals

    @api.model
    def _cron_cleanup_obsolete(self, days=7):
        from_date = fields.Datetime.now().replace(hour=23, minute=59, second=59)
        limit_date = date_utils.subtract(from_date, days)
        records = self.search([("state", "=", "done"), ("done_on", "<=", limit_date)])
        records.unlink()
        _logger.info("Cleanup obsolete media import. %d records found.", len(records))

    def _report_label_for(self, key):
        labels = {
            "created": _("Created"),
            "file_not_found": _("Media file not found"),
            "missing_media_types": _("media_types not found"),
        }
        return labels.get(key, key)
