# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": """Peruvian - Electronic Delivery Note 2.0""",
    'version': '0.1',
    'summary': 'Electronic Delivery Note for Peru (REST API method)',
    'category': 'Accounting/Localizations/EDI',
    'author': 'Vauxoo',
    'license': 'OEEL-1',
    'description': """
    The delivery guide (Guía de Remisión) is needed as a proof
    that you are sending goods between A and B.

    It is only when a delivery order is validated that you can create the delivery
    guide.
    """,
    'depends': [
        'l10n_pe_edi_stock',
    ],
    "demo": [
        "demo/res_partner.xml",
    ],
    "data": [
        "data/edi_delivery_guide.xml",
        "views/res_partner_view.xml",
        "views/stock_picking_views.xml",
        "views/report_deliveryslip.xml",
        "views/res_config_settings_views.xml",
        "views/product_template_view.xml",
        "views/vehicle_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "application": False,
}
