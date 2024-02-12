import base64
import hashlib
import json
import requests
import urllib.parse
from lxml import etree
from json.decoder import JSONDecodeError
from markupsafe import Markup

from odoo import _, _lt, fields, models

PE_RELATED_DOCUMENT = [
    ('01', 'Factura'),
    ('03', 'Boleta de Venta'),
    ('04', 'Liquidación de Compra'),
    ('09', 'Guía de Remisión Remitente'),
    ('12', 'Ticket o cinta emitido por máquina registradora'),
    ('31', 'Guía de Remisión Transportista'),
    ('48', 'Comprobante de Operaciones - Ley N° 29972'),
    ('49', 'Constancia de Depósito - IVAP (Ley 28211)'),
    ('50', 'Declaración Aduanera de Mercancías'),
    ('52', 'Declaración Simplificada (DS)'),
    ('65', 'Autorización de Circulación para transportar MATPEL - Callao'),
    ('66', 'Autorización de Circulación para transporte de carga y mercancías en Lima Metropolitana'),
    ('67', 'Permiso de Operación Especial para el servicio de transporte de MATPEL - MTC'),
    ('68', 'Habilitación Sanitaria de Transporte Terrestre de Productos Pesqueros y Acuícolas'),
    ('69', 'Permiso / Autorización de operación de transporte de mercancías'),
    ('71', 'Resolución de Adjudicación de bienes - SUNAT'),
    ('72', 'Resolución de Comiso de bienes - SUNAT'),
    ('73', 'Guía de Transporte Forestal o de Fauna - SERFOR'),
    ('74', 'Guía de Tránsito - SUCAMEC'),
    ('75', 'Autorización para operar como empresa de Saneamiento Ambiental - MINSA'),
    ('76', 'Autorización para manejo y recojo de residuos sólidos peligrosos y no peligrosos'),
    ('77', 'Certificado fitosanitario la movilización de plantas, productos vegetales, y otros artículos reglamentados'),
    ('78', 'Registro Único de Usuarios y Transportistas de Alcohol Etílico'),
    ('80', 'Constancia de Depósito - Detracción'),
    ('81', 'Código de autorización emitida por el SCOP'),
    ('82', 'Declaración jurada de mudanza'),
]


ERROR_MESSAGES = {
    "request": _lt("There was an error communicating with the SUNAT service.") + " " + _lt("Details:"),
    "json_decode": _lt("Could not decode the response received from SUNAT.") + " " + _lt("Details:"),
    "unzip": _lt("Could not decompress the ZIP file received from SUNAT."),
    "processing": _lt("The delivery guide is being processed by SUNAT. Click on 'Retry' to refresh the state."),
    "duplicate": _lt("A delivery guide with this number is already registered with SUNAT. Click on 'Retry' to try sending with a new number."),
    "response_code": _lt("SUNAT returned an error code.") + " " + _lt("Details:"),
    "response_unknown": _lt("Could not identify content in the response retrieved from SUNAT.") + " " + _lt("Details:"),
}

class Picking(models.Model):
    _inherit = 'stock.picking'

    l10n_pe_edi_ticket_number = fields.Char(
        string="Ticket Number",
        readonly=True, tracking=True, copy=False,
        help="Saves the folio asigned to when post the EDI document",
    )
    l10n_pe_edi_document_number = fields.Char(
        string="Related Document Number",
        copy=False,
    )
    l10n_pe_edi_related_document_type = fields.Selection(
        selection=PE_RELATED_DOCUMENT,
        string="Related Document Type",
        copy=False,
    )

    def _l10n_pe_edi_get_delivery_guide_values(self):
        """ Gather the values needed by the delivery guide QWeb template. """
        # OVERRIDE
        result = super()._l10n_pe_edi_get_delivery_guide_values()
        result.update({
            'related_document': dict(PE_RELATED_DOCUMENT)[self.l10n_pe_edi_related_document_type] if self.l10n_pe_edi_related_document_type else False,
        })
        return result

    def _l10n_pe_edi_create_delivery_guide(self):
        """ Generate the delivery guide XML. """
        # OVERRIDE
        values = self._l10n_pe_edi_get_delivery_guide_values()
        return self.env['ir.qweb']._render('l10n_pe_edi_stock_20.sunat_guiaremision', values).encode()

    def _l10n_pe_edi_get_sunat_guia_credentials(self):
        """ Returns the credentials to be used with the SUNAT authentication service. """
        company = self.company_id.sudo()
        if not company.l10n_pe_edi_stock_client_id:
            return {"error": _("No Client ID found for company %s.", company.display_name)}
        credentials = {
            "access_id": company.l10n_pe_edi_stock_client_id,
            "access_key": company.l10n_pe_edi_stock_client_secret,
            "client_id": company.l10n_pe_edi_stock_client_username,
            "password": company.l10n_pe_edi_stock_client_password,
            "login_url": "https://api-seguridad.sunat.gob.pe/v1/clientessol/%s/oauth2/token/",
        }
        return credentials

    def _l10n_pe_edi_request_token(self, credentials):
        """ Request an authentication token from the SUNAT authentication service.
            The token can then be used in requests to the endpoints for sending the
            delivery guide and for requesting the CDR. """
        headers = {
            "Accept": "application/json",
        }
        data = {
            "grant_type": "password",
            "scope": "https://api-cpe.sunat.gob.pe/",
            "client_id": credentials["access_id"],
            "client_secret": credentials["access_key"],
            "username": credentials["client_id"],
            "password": credentials["password"],
        }
        try:
            response = requests.post(credentials["login_url"] % urllib.parse.quote(credentials["access_id"], safe=''), data=data, headers=headers, timeout=20)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["request"], e))}

        try:
            response_json = response.json()
        except JSONDecodeError as e:
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["json_decode"], e))}

        if "error" in response_json or "error_description" in response_json:
            error_msg = str(Markup("%s<br/>%s: %s") % (ERROR_MESSAGES["response_code "], response_json.get("error", ""), response_json.get("error_description", "")))
            return {"error": error_msg}
        if not response_json.get("access_token"):
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["response_unknown"], response_json))}

        token = response_json["access_token"]
        return {"token": token}

    def _l10n_pe_edi_get_token(self, force_request=False):
        """ Return the authentication token for the SUNAT delivery guide service.

            The token is cached in `company.l10n_pe_edi_stock_token`.

            :param force_request: if True, will request a new token. """
        existing_token = self.sudo().company_id.l10n_pe_edi_stock_token
        if not force_request and existing_token:
            return {"token": existing_token}

        credentials = self._l10n_pe_edi_get_sunat_guia_credentials()
        if "error" in credentials:
            return credentials
        res_request_token = self._l10n_pe_edi_request_token(credentials)
        if "error" in res_request_token:
            return res_request_token

        token = res_request_token.get("token")
        self.sudo().company_id.l10n_pe_edi_stock_token = token
        return res_request_token

    def _l10n_pe_edi_sign(self, edi_filename, edi_str):
        """ Send a delivery guide to SUNAT, and retrieve the CDR.

            The method uses the cached authentication token returned by
            _l10n_pe_edi_get_token. If either the sending or the retrieving fails due
            to an expired token, a new token is requested and we retry.

            :param edi_filename: the name of the XML file containing the delivery guide
            :param edi_str: the content of the XML file containing the delivery guide """
        # OVERRIDE
        res_get_token = self._l10n_pe_edi_get_token()
        if "error" in res_get_token:
            return res_get_token
        token = res_get_token.get("token")
        result = self._l10n_pe_edi_sign_steps(edi_filename, edi_str, token)

        # If the token has expired, the error returned is 401 Client Error, clear the token and retry again.
        if result.get("error_reason") == "unauthorized":
            res_get_token = self._l10n_pe_edi_get_token(force_request=True)
            if "error" in res_get_token:
                return res_get_token
            token = res_get_token.get("token")
            return self._l10n_pe_edi_sign_steps(edi_filename, edi_str, token)
        return result

    def _l10n_pe_edi_sign_steps(self, edi_filename, edi_str, token):
        """ Send the delivery guide to SUNAT, then retrieve the CDR.

            :param edi_filename: the name of the XML file containing the delivery guide
            :param edi_str: the content of the XML file containing the delivery guide
            :param token: the SUNAT authentication token """
        # Step 1: send the delivery guide, unless we already sent it and are still waiting for a response.
        if not self.l10n_pe_edi_ticket_number:
            res_send_delivery_guide = self._l10n_pe_edi_send_delivery_guide(edi_filename, edi_str, token)
            if "error" in res_send_delivery_guide:
                return res_send_delivery_guide
            else:
                self.l10n_pe_edi_ticket_number = res_send_delivery_guide["ticket_number"]

        # Step 2: retrieve the CDR using the ticket number.
        res_get_cdr = self._l10n_pe_edi_get_cdr(self.l10n_pe_edi_ticket_number, token)
        if "error" in res_get_cdr:
            # If the error is that the CDR is still being processed, keep the ticket number. Otherwise, we set it to False.
            if res_get_cdr.get("error_reason") not in ("processing", "unauthorized"):
                self.l10n_pe_edi_ticket_number = False
            if res_get_cdr.get("error_reason") == "duplicate":
                self.l10n_latam_document_number = False
            return res_get_cdr

        return {"xml_document": edi_str, "cdr": res_get_cdr["cdr"]}

    def _l10n_pe_edi_send_delivery_guide(self, edi_filename, edi_str, token):
        """ Send a delivery guide to SUNAT via the REST API.

            SUNAT provides a ticket number in its response, which can be used to
            retrieve the CDR once the SUNAT service has finished processing the
            delivery guide.

            :param edi_filename: the name of the XML file containing the delivery guide
            :param edi_str: the content of the XML file containing the delivery guide
            :param token: the SUNAT authentication token """
        self.ensure_one()
        headers = {
            'Authorization': "Bearer " + token,
            'Content-Type': "Application/json",
        }
        ruc = self.company_id.vat
        serie_folio = self._l10n_pe_edi_get_serie_folio()
        serie = serie_folio["serie"]
        folio = serie_folio["folio"]
        url = "https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/%s-09-%s-%s" % (
            urllib.parse.quote(ruc, safe=''), urllib.parse.quote(serie, safe=''), urllib.parse.quote(folio, safe=''))
        zip_file = self._l10n_pe_edi_zip(edi_str, edi_filename)
        data = {
            "archivo": {
                "nomArchivo": "%s-09-%s-%s.zip" % (ruc, serie, folio),
                "arcGreZip": base64.b64encode(zip_file).decode(),
                "hashZip": hashlib.sha256(zip_file).hexdigest(),
            }
        }
        payload = json.dumps(data)
        try:
            response = requests.post(url, data=payload, headers=headers, verify=True, timeout=20)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            to_return = {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["request"], e))}
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                to_return.update({"error_reason": "unauthorized"})
            return to_return
        try:
            response_json = response.json()
        except JSONDecodeError as e:
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["json_decode"], e))}

        if isinstance(response_json.get("errors"), list) and len(response_json["errors"]) > 0 and isinstance(response_json["errors"][0], dict):
            code = response_json["errors"][0].get("cod", "")
            msg = response_json["errors"][0].get("msg", "")
            return {"error": str(Markup("%s<br/>%s: %s") % (ERROR_MESSAGES["response_code"], code, msg))}
        if not response_json.get("numTicket"):
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["response_unknown"], response_json))}

        return {"ticket_number": response_json["numTicket"]}

    def _l10n_pe_edi_zip(self, edi_str, edi_filename):
        """ Transform the delivery guide XML into a ZIP file to be transmitted over the network.
            SUNAT expects the unzipped XML to be encoded using ISO-8859-1. """
        edi_tree = etree.fromstring(edi_str)
        edi_str = etree.tostring(edi_tree, xml_declaration=True, encoding='ISO-8859-1')

        pe_edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
        zip_edi_str = pe_edi_format._l10n_pe_edi_zip_edi_document([('%s.xml' % edi_filename, edi_str)])
        return zip_edi_str

    def _l10n_pe_edi_get_cdr(self, ticket_number, token):
        """ Retrieve the CDR (confirmation of receipt) for a delivery guide that was sent.

            :param ticket_number: the ticket number obtained when sending the delivery guide
            :param token: the SUNAT authentication token """
        headers = {
            'Authorization': "Bearer " + token,
            'Content-Type': "Application/json",
        }
        url = 'https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/envios/%s' % urllib.parse.quote(ticket_number, safe='')
        try:
            response = requests.get(url, params={'numTicket': ticket_number}, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            to_return = {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["request"], e))}
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                to_return.update({"error_reason": "unauthorized"})
            return to_return
        try:
            response_json = response.json()
        except JSONDecodeError as e:
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["json_decode"], e))}

        if response_json.get("codRespuesta") == "98":
            error_msg = ERROR_MESSAGES["processing"]
            return {"error": error_msg, "error_reason": "processing"}
        if response_json.get("error"):
            code = response_json["error"].get("numError", "")
            msg = response_json["error"].get("desError", "")
            if code == "1033":
                error_msg = ERROR_MESSAGES["duplicate"]
                return {"error": error_msg, "error_reason": "duplicate"}
            else:
                return {"error": str(Markup("%s %s: %s") % (ERROR_MESSAGES["response_code"], code, msg))}
        if not response_json.get("arcCdr") or response_json.get("codRespuesta") != "0":
            if "codRespuesta" in response_json:
                return {"error": str(Markup("%s %s") % (ERROR_MESSAGES["request"], response_json["codRespuesta"]))}
            else:
                return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["response_unknown"], response_json))}

        cdr_zip = response_json["arcCdr"]

        try:
            cdr = self.env["account.edi.format"]._l10n_pe_edi_unzip_edi_document(base64.b64decode(cdr_zip))
        except Exception as e:
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["unzip"], e))}

        return {"cdr": cdr}

    def _l10n_pe_edi_get_qr(self):
        """ Retrieve the CDR's QR code. """
        self.ensure_one()
        edi_filename = 'cdr-%s-09-%s.xml' % (
            self.company_id.vat,
            (self.l10n_latam_document_number or '').replace(' ', ''),
        )
        attachment = self.env['ir.attachment'].search([
            ('name', '=', edi_filename),
            ('res_id', '=', self.id),
            ('res_model', '=', self._name)])
        if not attachment:
            return ''
        edi_attachment_str = attachment.raw
        edi_tree = etree.fromstring(edi_attachment_str)
        element = edi_tree.xpath('//cbc:DocumentDescription',
                                 namespaces={'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'})
        if not element:
            return ''
        return element[0].text

    def _l10n_pe_edi_generate_missing_data_error_list(self):
        """ Check that all the required data is present before generating the delivery guide.
            Based on SUNAT resolution 000123-2022 (published 2022-07-12), pages 48-54,
            and on the list of checks published at
            https://cpe.sunat.gob.pe/sites/default/files/inline-files/ValidacionesGREv20221020_publicacion.xlsx
        """
        # OVERRIDE
        errors = super()._l10n_pe_edi_generate_missing_data_error_list()
        if self.company_id.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code != "6":
            errors.append(_("The company's ID type must be set to RUC on the company contact page."))
        if (self.l10n_pe_edi_transport_type == '02' and not self.l10n_pe_edi_operator_id and not self.l10n_pe_edi_vehicle_id.is_m1l
            or self.l10n_pe_edi_transport_type == '01' and not self.l10n_pe_edi_operator_id):
            errors.append(_("You must choose the transfer operator."))
        return errors
