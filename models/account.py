    # -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

from datetime import datetime
import base64
from lxml import etree
import requests
import re

#from import XMLSigner

import logging

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    firma_fel = fields.Char('Firma FEL', copy=False)
    serie_fel = fields.Char('Serie FEL', copy=False)
    numero_fel = fields.Char('Numero FEL', copy=False)
    pdf_fel = fields.Char('PDF FEL', copy=False)
    factura_original_id = fields.Many2one('account.invoice', string="Factura original FEL")

    def invoice_validate(self):
        detalles = []
        subtotal = 0
        for factura in self:
            if factura.journal_id.usuario_fel and not factura.firma_fel:
                attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")

                NSMAP = {
                    "ds": "http://www.w3.org/2000/09/xmldsig#",
                    "dte": "http://www.sat.gob.gt/dte/fel/0.1.0",
                }

                NSMAP_REF = {
                    "cno": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0",
                }

                NSMAP_ABONO = {
                    "cfc": "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0",
                }
                
                NSMAP_EXP = {
                    "cex": "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0",
                }

                DTE_NS = "{http://www.sat.gob.gt/dte/fel/0.1.0}"
                DS_NS = "{http://www.w3.org/2000/09/xmldsig#}"
                CNO_NS = "{http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0}"
                CFC_NS = "{http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0}"
                CEX_NS = "{http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0}"

                # GTDocumento = etree.Element(DTE_NS+"GTDocumento", {attr_qname: "http://www.sat.gob.gt/dte/fel/0.1.0"}, Version="0.4", nsmap=NSMAP)
                GTDocumento = etree.Element(DTE_NS+"GTDocumento", {}, Version="0.4", nsmap=NSMAP)
                SAT = etree.SubElement(GTDocumento, DTE_NS+"SAT", ClaseDocumento="dte")
                DTE = etree.SubElement(SAT, DTE_NS+"DTE", ID="DatosCertificados")
                DatosEmision = etree.SubElement(DTE, DTE_NS+"DatosEmision", ID="DatosEmision")
                
                moneda = "GTQ"
                if factura.currency_id.id != factura.company_id.currency_id.id:
                    moneda = "USD"

                DatosGenerales = etree.SubElement(DatosEmision, DTE_NS+"DatosGenerales", CodigoMoneda=moneda, FechaHoraEmision=fields.Date.from_string(factura.date_invoice).strftime('%Y-%m-%dT%H:%M:%S'), Tipo=factura.journal_id.tipo_documento_fel)
                if factura.tipo_gasto == 'importacion':
                    DatosGenerales.attrib['Exp'] = "SI"

                Emisor = etree.SubElement(DatosEmision, DTE_NS+"Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=factura.journal_id.codigo_establecimiento_fel, CorreoEmisor="", NITEmisor=factura.company_id.vat.replace('-',''), NombreComercial=factura.journal_id.direccion.name, NombreEmisor=factura.company_id.name)
                DireccionEmisor = etree.SubElement(Emisor, DTE_NS+"DireccionEmisor")
                Direccion = etree.SubElement(DireccionEmisor, DTE_NS+"Direccion")
                Direccion.text = factura.journal_id.direccion.street or 'Ciudad'
                CodigoPostal = etree.SubElement(DireccionEmisor, DTE_NS+"CodigoPostal")
                CodigoPostal.text = factura.journal_id.direccion.zip or '01001'
                Municipio = etree.SubElement(DireccionEmisor, DTE_NS+"Municipio")
                Municipio.text = factura.journal_id.direccion.city or 'Guatemala'
                Departamento = etree.SubElement(DireccionEmisor, DTE_NS+"Departamento")
                Departamento.text = factura.journal_id.direccion.state_id.name if factura.journal_id.direccion.state_id else ''
                Pais = etree.SubElement(DireccionEmisor, DTE_NS+"Pais")
                Pais.text = factura.journal_id.direccion.country_id.code or 'GT'

                Receptor = etree.SubElement(DatosEmision, DTE_NS+"Receptor", CorreoReceptor=factura.partner_id.email, IDReceptor=factura.partner_id.vat.replace('-',''), NombreReceptor=factura.partner_id.name)
                DireccionReceptor = etree.SubElement(Receptor, DTE_NS+"DireccionReceptor")
                Direccion = etree.SubElement(DireccionReceptor, DTE_NS+"Direccion")
                Direccion.text = factura.partner_id.street or 'Ciudad'
                CodigoPostal = etree.SubElement(DireccionReceptor, DTE_NS+"CodigoPostal")
                CodigoPostal.text = factura.partner_id.zip or '01001'
                Municipio = etree.SubElement(DireccionReceptor, DTE_NS+"Municipio")
                Municipio.text = factura.partner_id.city or 'Guatemala'
                Departamento = etree.SubElement(DireccionReceptor, DTE_NS+"Departamento")
                Departamento.text = factura.partner_id.state_id.name if factura.partner_id.state_id else ''
                Pais = etree.SubElement(DireccionReceptor, DTE_NS+"Pais")
                Pais.text = factura.partner_id.country_id.code or 'GT'

                # Frases = etree.SubElement(DatosEmision, DTE_NS+"Frases")
                # Frase = etree.SubElement(Frases, DTE_NS+"Frase", CodigoEscenario="1", TipoFrase="1")

                if factura.journal_id.tipo_documento_fel not in ['NDEB', 'NCRE']:
                    ElementoFrases = etree.fromstring(factura.company_id.frases_fel)
                    if factura.tipo_gasto == 'importacion':
                        Frase = etree.SubElement(ElementoFrases, DTE_NS+"Frase", CodigoEscenario="1", TipoFrase="4")
                    DatosEmision.append(ElementoFrases)

                Items = etree.SubElement(DatosEmision, DTE_NS+"Items")

                linea_num = 0
                gran_subtotal = 0
                gran_total = 0
                gran_total_impuestos = 0
                for linea in factura.invoice_line_ids:

                    linea_num += 1

                    tipo_producto = "B"
                    if linea.product_id.type != 'product':
                        tipo_producto = "S"
                    precio_unitario = linea.price_unit * (100-linea.discount) / 100
                    precio_sin_descuento = linea.price_unit
                    descuento = precio_sin_descuento * linea.quantity - precio_unitario * linea.quantity
                    precio_unitario_base = linea.price_subtotal / linea.quantity
                    total_linea = precio_unitario * linea.quantity
                    total_linea_base = precio_unitario_base * linea.quantity
                    total_impuestos = total_linea - total_linea_base

                    Item = etree.SubElement(Items, DTE_NS+"Item", BienOServicio=tipo_producto, NumeroLinea=str(linea_num))
                    Cantidad = etree.SubElement(Item, DTE_NS+"Cantidad")
                    Cantidad.text = str(linea.quantity)
                    UnidadMedida = etree.SubElement(Item, DTE_NS+"UnidadMedida")
                    UnidadMedida.text = "UNI"
                    Descripcion = etree.SubElement(Item, DTE_NS+"Descripcion")
                    Descripcion.text = linea.name
                    PrecioUnitario = etree.SubElement(Item, DTE_NS+"PrecioUnitario")
                    PrecioUnitario.text = '{:.6f}'.format(precio_sin_descuento)
                    Precio = etree.SubElement(Item, DTE_NS+"Precio")
                    Precio.text = '{:.6f}'.format(precio_sin_descuento * linea.quantity)
                    Descuento = etree.SubElement(Item, DTE_NS+"Descuento")
                    Descuento.text = '{:.6f}'.format(descuento)
                    Impuestos = etree.SubElement(Item, DTE_NS+"Impuestos")
                    Impuesto = etree.SubElement(Impuestos, DTE_NS+"Impuesto")
                    NombreCorto = etree.SubElement(Impuesto, DTE_NS+"NombreCorto")
                    NombreCorto.text = "IVA"
                    CodigoUnidadGravable = etree.SubElement(Impuesto, DTE_NS+"CodigoUnidadGravable")
                    CodigoUnidadGravable.text = "1"
                    if factura.tipo_gasto == 'importacion':
                        CodigoUnidadGravable.text = "2"
                    MontoGravable = etree.SubElement(Impuesto, DTE_NS+"MontoGravable")
                    MontoGravable.text = '{:.2f}'.format(factura.currency_id.round(total_linea_base))
                    MontoImpuesto = etree.SubElement(Impuesto, DTE_NS+"MontoImpuesto")
                    MontoImpuesto.text = '{:.2f}'.format(factura.currency_id.round(total_impuestos))
                    Total = etree.SubElement(Item, DTE_NS+"Total")
                    Total.text = '{:.2f}'.format(factura.currency_id.round(total_linea))

                    gran_total += factura.currency_id.round(total_linea)
                    gran_subtotal += factura.currency_id.round(total_linea_base)
                    gran_total_impuestos += factura.currency_id.round(total_impuestos)

                Totales = etree.SubElement(DatosEmision, DTE_NS+"Totales")
                TotalImpuestos = etree.SubElement(Totales, DTE_NS+"TotalImpuestos")
                TotalImpuesto = etree.SubElement(TotalImpuestos, DTE_NS+"TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto='{:.2f}'.format(factura.currency_id.round(gran_total_impuestos)))
                GranTotal = etree.SubElement(Totales, DTE_NS+"GranTotal")
                GranTotal.text = '{:.2f}'.format(factura.currency_id.round(gran_total))

                if factura.company_id.adenda_fel:
                    Adenda = etree.SubElement(SAT, DTE_NS+"Adenda")
                    exec(factura.company_id.adenda_fel, {'etree': etree, 'Adenda': Adenda, 'factura': factura})

                if factura.journal_id.tipo_documento_fel in ['NDEB', 'NCRE']:
                    Complementos = etree.SubElement(DatosEmision, DTE_NS+"Complementos")
                    Complemento = etree.SubElement(Complementos, DTE_NS+"Complemento", IDComplemento="ReferenciasNota", NombreComplemento="Nota de Credito" if factura.journal_id.tipo_documento_fel == 'NCRE' else "Nota de Debito", URIComplemento="text")
                    if factura.factura_original_id.numero_fel:
                        ReferenciasNota = etree.SubElement(Complemento, CNO_NS+"ReferenciasNota", FechaEmisionDocumentoOrigen=str(factura.factura_original_id.date_invoice), MotivoAjuste="-", NumeroAutorizacionDocumentoOrigen=factura.factura_original_id.firma_fel, NumeroDocumentoOrigen=factura.factura_original_id.numero_fel, SerieDocumentoOrigen=factura.factura_original_id.serie_fel, Version="0.0", nsmap=NSMAP_REF)
                    else:
                        ReferenciasNota = etree.SubElement(Complemento, CNO_NS+"ReferenciasNota", RegimenAntiguo="Antiguo", FechaEmisionDocumentoOrigen=str(factura.factura_original_id.date_invoice), MotivoAjuste="-", NumeroAutorizacionDocumentoOrigen=factura.factura_original_id.firma_fel, NumeroDocumentoOrigen=factura.factura_original_id.name.split("-")[1], SerieDocumentoOrigen=factura.factura_original_id.name.split("-")[0], Version="0.0", nsmap=NSMAP_REF)

                if factura.journal_id.tipo_documento_fel in ['FCAM'] or factura.tipo_gasto == 'importacion':
                    Complementos = etree.SubElement(DatosEmision, DTE_NS+"Complementos")
    
                    if factura.journal_id.tipo_documento_fel in ['FCAM']:
                        Complemento = etree.SubElement(Complementos, DTE_NS+"Complemento", IDComplemento="FCAM", NombreComplemento="AbonosFacturaCambiaria", URIComplemento="#AbonosFacturaCambiaria")
                        AbonosFacturaCambiaria = etree.SubElement(Complemento, CFC_NS+"AbonosFacturaCambiaria", Version="1", nsmap=NSMAP_ABONO)
                        Abono = etree.SubElement(AbonosFacturaCambiaria, CFC_NS+"Abono")
                        NumeroAbono = etree.SubElement(Abono, CFC_NS+"NumeroAbono")
                        NumeroAbono.text = "1"
                        FechaVencimiento = etree.SubElement(Abono, CFC_NS+"FechaVencimiento")
                        FechaVencimiento.text = str(factura.date_due)
                        MontoAbono = etree.SubElement(Abono, CFC_NS+"MontoAbono")
                        MontoAbono.text = '{:.2f}'.format(factura.currency_id.round(gran_total))
                    
                    if factura.tipo_gasto == 'importacion':
                        Complemento = etree.SubElement(Complementos, DTE_NS+"Complemento", IDComplemento="text", NombreComplemento="text", URIComplemento="text")
                        Exportacion = etree.SubElement(Complemento, CEX_NS+"Exportacion", Version="1", nsmap=NSMAP_EXP)
                        NombreConsignatarioODestinatario = etree.SubElement(Exportacion, CEX_NS+"NombreConsignatarioODestinatario")
                        NombreConsignatarioODestinatario.text = "-"
                        DireccionConsignatarioODestinatario = etree.SubElement(Exportacion, CEX_NS+"DireccionConsignatarioODestinatario")
                        DireccionConsignatarioODestinatario.text = "-"
                        NombreComprador = etree.SubElement(Exportacion, CEX_NS+"NombreComprador")
                        NombreComprador.text = "-"
                        DireccionComprador = etree.SubElement(Exportacion, CEX_NS+"DireccionComprador")
                        DireccionComprador.text = "-"
                        INCOTERM = etree.SubElement(Exportacion, CEX_NS+"INCOTERM")
                        INCOTERM.text = "FOB"
                        NombreExportador = etree.SubElement(Exportacion, CEX_NS+"NombreExportador")
                        NombreExportador.text = factura.company_id.name
                        CodigoExportador = etree.SubElement(Exportacion, CEX_NS+"CodigoExportador")
                        CodigoExportador.text = "-"

                xmls = etree.tostring(GTDocumento, encoding="UTF-8")
                xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
                xmls_base64 = base64.b64encode(xmls)
                logging.warn(xmls)

                # cert = open("/home/odoo/100056865-cert.pem").read().encode('ascii')
                # key = open("/home/odoo/100056865.key").read().encode('ascii')
                #
                # signer = XMLSigner(c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315#WithComments')
                # signed_root = signer.sign(GTDocumento, key=key, cert=cert)
                #
                # signed_text = etree.tostring(signed_root, xml_declaration=True, encoding="UTF-8")
                # logging.warn(signed_text)
                #
                # signed_text_b64 = base64.b64encode(signed_text)
                # logging.warn(signed_text_b64)

                headers = { "Content-Type": "application/json" }
                data = {
                    "llave": factura.journal_id.token_firma_fel,
                    "archivo": xmls_base64.decode("utf-8"),
                    "codigo": factura.company_id.vat.replace('-',''),
                    "alias": factura.journal_id.usuario_fel,
                    "es_anulacion": "N"
                }
                r = requests.post('https://signer-emisores.feel.com.gt/sign_solicitud_firmas/firma_xml', json=data, headers=headers)
                logging.warn(r.json())
                firma_json = r.json()
                if firma_json["resultado"]:
                    logging.warn(base64.b64decode(firma_json["archivo"]))

                    headers = {
                        "USUARIO": factura.journal_id.usuario_fel,
                        "LLAVE": factura.journal_id.clave_fel,
                        "IDENTIFICADOR": str(100000000+factura.id),
                        "Content-Type": "application/json",
                    }
                    data = {
                        "nit_emisor": factura.company_id.vat.replace('-',''),
                        "correo_copia": factura.company_id.email,
                        "xml_dte": firma_json["archivo"]
                    }
                    r = requests.post("https://certificador.feel.com.gt/fel/certificacion/dte/", json=data, headers=headers)
                    logging.warn(r.json())
                    certificacion_json = r.json()
                    if certificacion_json["resultado"]:
                        factura.firma_fel = certificacion_json["uuid"]
                        factura.name = str(certificacion_json["serie"])+"-"+str(certificacion_json["numero"])
                        factura.serie_fel = certificacion_json["serie"]
                        factura.numero_fel = certificacion_json["numero"]
                        factura.pdf_fel =" https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid="+certificacion_json["uuid"]
                    else:
                        raise UserError(str(certificacion_json["descripcion_errores"]))
                else:
                    raise UserError(str(r))

        return super(AccountInvoice,self).invoice_validate()

class AccountJournal(models.Model):
    _inherit = "account.journal"

    usuario_fel = fields.Char('Usuario FEL', copy=False)
    clave_fel = fields.Char('Clave FEL', copy=False)
    token_firma_fel = fields.Char('Token Firma FEL', copy=False)
    codigo_establecimiento_fel = fields.Char('Codigo Establecimiento FEL', copy=False)
    tipo_documento_fel = fields.Selection([('FACT', 'FACT'), ('FCAM', 'FCAM'), ('FPEQ', 'FPEQ'), ('FCAP', 'FCAP'), ('FESP', 'FESP'), ('NABN', 'NABN'), ('RDON', 'RDON'), ('RECI', 'RECI'), ('NDEB', 'NDEB'), ('NCRE', 'NCRE')], 'Tipo de Documento FEL', copy=False)

class ResCompany(models.Model):
    _inherit = "res.company"

    frases_fel = fields.Text('Frases FEL')
    adenda_fel = fields.Text('Adenda FEL')
