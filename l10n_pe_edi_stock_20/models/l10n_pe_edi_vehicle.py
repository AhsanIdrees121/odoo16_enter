# -*- coding: utf-8 -*-

from odoo import models, fields

ISSUING_ENTITY = [
    ('01', 'National Superintendency for the Control of Security Services, Weapons, Ammunition and Explosives for Civil Use'),
    ('02', 'General Directorate of Medicines Supplies and Drugs'),
    ('03', 'General Directorate of Environmental Health'),
    ('04', 'National Agrarian Health Service'),
    ('05', 'National Forest and Wildlife Service'),
    ('06', 'Ministry of Transport and Communications'),
    ('07', 'Ministry of Production'),
    ('08', 'Ministry of the Environment'),
    ('09', 'National Agency for Fisheries Health'),
    ('10', 'Municipality of Lima'),
    ('11', 'Ministry of Health'),
    ('12', 'Regional government'),
]


class L10nPeEdiVehicle(models.Model):
    _inherit = "l10n_pe_edi.vehicle"

    is_m1l = fields.Boolean(
        string="Is M1 or L?",
        help="Motor vehicles with less than four wheels and motor vehicles for transporting "
        "passengers with no more than 8 seats."
    )
    authorization_issuing_entity = fields.Selection(selection=ISSUING_ENTITY)
    authorization_issuing_entity_number = fields.Char(string="Authorization Issuing Entity Number")
