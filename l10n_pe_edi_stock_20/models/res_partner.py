from odoo import fields, models
from .l10n_pe_edi_vehicle import ISSUING_ENTITY

class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_pe_edi_operator_license = fields.Char(string="Operator License")
    l10n_pe_edi_mtc_number = fields.Char(string="MTC Registration Number")
    l10n_pe_edi_authorization_issuing_entity = fields.Selection(
        selection=ISSUING_ENTITY,
        string="Authorization Issuing Entity"
    )
    l10n_pe_edi_authorization_number = fields.Char(string="Authorization Number")
