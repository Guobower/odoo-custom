# -*- coding: utf-8 -*-
from openerp import api, fields, models, _
from openerp.exceptions import ValidationError, UserError
import openerp.addons.decimal_precision as dp
import endicia


class ProviderEndicia(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('endicia', "Endicia")])

    endicia_weight_package = fields.Float('Package Weight', digits_compute=dp.get_precision('Stock Weight')
                                       ,help="Package weight which comes from weighing machine in pounds")
    endicia_weight_unit = fields.Selection([('LB', 'LBS'), ('KG', 'KGS'), ('OUNCE', 'OUNCES')], 'WeightUnits')
    endicia_service_type = fields.Selection([
                ('First-Class Mail', 'First-Class Mail'),
                ('First Class HFP Commercial', 'First Class HFP Commercial'),
                ('FirstClassMailInternational', 'First Class Mail International'),
                ('Priority Mail', 'Priority Mail'),
                ('Priority Mail Express', 'Priority Mail Express'),
                ('Priority Commercial', 'Priority Commercial'),
                ('Priority HFP Commercial', 'Priority HFP Commercial'),
                ('Priority Mail International', 'Priority Mail International'),
                ('Express', 'Express'),
                ('Express Commercial', 'Express Commercial'),
                ('Express SH', 'Express SH'),
                ('Express SH Commercial', 'Express SH Commercial'),
                ('Express HFP', 'Express HFP'),
                ('Express HFP Commercial', 'Express HFP Commercial'),
                ('ExpressMailInternational', 'Express Mail International'),
                ('ParcelPost', 'Parcel Post'),
                ('Parcel Select Ground', 'Parcel Select Ground'),
                ('StandardMail', 'Standard Mail'),
                ('CriticalMail', 'Critical Mail'),
                ('Media Mail', 'Media Mail'),
                ('Library Mail', 'Library Mail'),

                ('Priority Mail Flat Rate Padded Envelope', 'Priority Mail Flat Rate Padded Envelope'),
                ('Priority Mail Small Flat Rate Box', 'Priority Mail Small Flat Rate Box'),
                ('Priority Mail Medium Flat Rate Box', 'Priority Mail Medium Flat Rate Box'),
                ('Priority Mail Large Flat Rate Box', 'Priority Mail Large Flat Rate Box'),

                ('Priority Mail International Flat Rate Padded Envelope', 'Priority Mail International Flat Rate Padded Envelope'),
                ('Priority Mail International Small Flat Rate Box', 'Priority Mail International Small Flat Rate Box'),
                ('Priority Mail International Medium Flat Rate Box', 'Priority Mail International Medium Flat Rate Box'),
                ('Priority Mail International Large Flat Rate Box', 'Priority Mail International Large Flat Rate Box'),

            ], 'Service Type')
    endicia_first_class_mail_type = fields.Selection([
                ('Letter', 'Letter'),
                ('Flat', 'Flat'),
                ('Parcel', 'Parcel'),
                ('Postcard', 'Postcard'),
            ], 'First Class Mail Type')
    endicia_container = fields.Selection([
                ('Letter', 'Letter'),
                ('Flat', 'Flat'),
                ('Parcel', 'Parcel'),
                ('Large Parcel', 'Large Parcel'),
                ('Irregular Parcel', 'Irregular Parcel'),
                ('Card', 'Card'),
                ('Oversized Parcel', 'Oversized Parcel'),

                ('SM Flat Rate Envelope', 'SmallFlatRateEnvelope'),
                ('Padded Flat Rate Envelope', 'Padded Flat Rate Envelope'),
                ('SM Flat Rate Box', 'Small Flat Rate Box'),
                ('MD Flat Rate Box', 'Medium Flat Rate Box'),
                ('LG Flat Rate Box', 'Large Flat Rate Box'),

             ], 'Container', default='Parcel')
    endicia_size = fields.Selection([('REGULAR', 'Regular'), ('LARGE', 'Large')], 'Size', defaults='REGULAR')
    endicia_width = fields.Float('Width', digits_compute=dp.get_precision('Stock Weight'))
    endicia_length = fields.Float('Length', digits_compute=dp.get_precision('Stock Weight'))
    endicia_height = fields.Float('Height', digits_compute=dp.get_precision('Stock Weight'))
    endicia_girth = fields.Float('Girth', digits_compute=dp.get_precision('Stock Weight'))
    endicia_shipping_account = fields.Selection([('my_account', 'My Account'), ('customer_account', 'Customer Account')], 'Shipping Account', default='my_account')
    endicia_label_type =fields.Selection([
                ('Default','Default'),
                ('CertifiedMail','Certified Mail'),
                ('DestinationConfirm','Destination Confirm'),
                ('Domestic','Domestic'),
                ('International','International'),
            ],'Label Type', defaults='Default')
    endicia_label_size = fields.Selection([
                ('4X6','4X6'),
                ('4X5','4X5'),
                ('4X4.5','4X4.5'),
                ('DocTab','DocTab'),
                ('6X4','6X4'),
                ('7X3','7X3'),
                ('7X4','7X4'),
                ('8X3','8X3'),
                ('Dymo30384','Dymo 30384'),
                ('Booklet','Booklet'),
                ('EnvelopeSize10','Envelope Size 10'),
                ('Mailer7x5','Mailer 7x5'),
            ],'Label Size', default='4X6')
    endicia_image_format = fields.Selection([('jpeg','JPEG'), ('png','PNG'), ('gif','GIF')], 'Image Format', default='jpeg')
    endicia_image_rotation = fields.Selection([
                ('None','None'),
                ('Rotate90','Rotate 90'),
                ('Rotate180','Rotate 180'),
                ('Rotate270','Rotate 270'),
            ],'Image Rotation', default='None')
    endicia_requester_id = fields.Char(string=" Endicia Requester ID")
    endicia_account_id = fields.Char(string="Endicia Account ID")
    endicia_passphrase = fields.Char(string="Endicia Passphrase")
    endicia_test_mode = fields.Boolean(default=True, string="Test Mode", help="Uncheck this box to use production Endicia Web Services")

    def _convert_weight(self, weight, weight_unit):
        # Asssume weight in KG
        if weight_unit == "LB":
            return round(weight * 2.20462, 3)
        elif weight_unit == "OUNCE":
            return round(weight * 35.274)
        else:
            return round(weight, 3)

    @api.multi
    def endicia_get_shipping_price_from_so(self, orders):
        res = []
        for order in orders:
            if not order.order_line:
                raise ValidationError(_("Please provide at least one item to ship."))
            if order.order_line.filtered(
                    lambda line: not line.product_id.weight and not line.is_delivery and not line.product_id.type in [
                        'service', 'digital']):
                raise ValidationError(
                    _('The estimated price cannot be computed because the weight of your product is missing.'))
            # assume the weight in KG
            weight = sum([(line.product_id.weight * line.product_qty) for line in order.order_line])* 0.453592 #weight reversed back to kg since client decides put all product weights in pounds
            weight = self._convert_weight(weight, self.endicia_weight_unit)
            # weight_unit = saleorder.weight_unit
            if not weight:
                raise ValidationError(_('Package Weight Invalid!'))
            # added handling for maximum weight limitation.
            if self.endicia_weight_unit == 'KG' and weight > 31.75147:
                raise ValidationError(_('Package Weight should not exceed 31.75 kg!'))
            if self.endicia_weight_unit == 'LB' and weight > 70:
                raise ValidationError(_('Package Weight should not exceed 70 lb!'))
            if self.endicia_weight_unit == 'OUNCE' and weight > 1120:
                raise ValidationError(_('Package Weight should not exceed 1120 ounce!'))
            # added for weight conversion
            # Convert weight to ounce before creating package
            #1kg = 35.274 Ounce
            if self.endicia_weight_unit == 'KG':
                weight *= 35.274
            #1lb = 16 Ounce
            if self.endicia_weight_unit == 'LB':
                weight *= 16

            ### Sender
            shipper = order.company_id.partner_id
            if not shipper:
                raise ValidationError(_('Shop Address not defined!'))
            if str(shipper.zip).find("-") != -1:
                zip_code = str(shipper.zip).split("-")[0]
            else:
                zip_code = str(shipper.zip)
            shipper = endicia.Address(
                                    shipper.name,
                                    shipper.street,
                                    shipper.city,
                                    shipper.state_id and shipper.state_id.code,
                                    zip_code,
                                    shipper.country_id and shipper.country_id.code,
                                    shipper.street2,
                                    shipper.phone,
                                    shipper.email,
                                    shipper.name
                            )
            ### Recipient
            recipient = order.partner_shipping_id
            if str(recipient.zip).find("-") != -1:
                zip_code = str(recipient.zip).split("-")[0]
            else:
                zip_code = str(recipient.zip)
            recipient = endicia.Address(recipient.name,
                        recipient.street and recipient.street.rstrip(','),
                        recipient.city and recipient.city.rstrip(','),
                        recipient.state_id and recipient.state_id.code,
                        zip_code,
                        recipient.country_id and recipient.country_id.code,
                        recipient.street2 and (recipient.street != recipient.street2) and recipient.street2.rstrip(','),
                        recipient.phone or '',
                        recipient.email,
                        recipient.name or '')
            credentials = {
                            'partner_id': self.endicia_requester_id,
                            'account_id': self.endicia_account_id,
                            'passphrase': self.endicia_passphrase
                           }
            en = endicia.Endicia(credentials, self.endicia_test_mode)
            #creating packages
            packages = [endicia.Package(self.endicia_service_type,
                                        round(weight, 1),
                                        endicia.Package.shapes[self.endicia_container],
                                        self.endicia_length,
                                        self.endicia_width,
                                        self.endicia_height,
                                        value=1000)
                        ]
            response = en.rate(packages, endicia.Package.shapes[self.endicia_container], shipper, recipient)
            if response['status'] == 0:
                for resp in response["info"]:
                    if resp['service'] == self.endicia_service_type:
                        res += [resp['cost']]
        return res or [0]

    @api.multi
    def endicia_send_shipping(self, pickings):
        res = []
        for picking in pickings:
            # Sender
            international_label = False
            shipper_address = picking.company_id.partner_id
            if not shipper_address.name:
                raise ValidationError(_("You must enter Shipper Name."))
            if not (shipper_address.street or shipper_address.street2):
                raise ValidationError(_("You must enter Shipper Street."))
            if not shipper_address.city:
                raise ValidationError(_("You must enter Shipper City."))
            if not shipper_address.state_id:
                raise ValidationError(_("You must enter Shipper State."))
            if not shipper_address.state_id.code:
                raise ValidationError(_("You must enter Shipper State Code."))
            if not shipper_address.zip:
                raise ValidationError(_("You must enter Shipper Zip."))
            if not shipper_address.country_id.code:
                raise ValidationError(_("You must enter Shipper Country."))
            if not shipper_address.email:
                raise ValidationError(_("You must enter Shipper email."))

            # added handling because endicia api support zip5 format.
            if str(shipper_address.zip).find("-") != -1:
                zip_code = str(shipper_address.zip).split("-")[0]
            else:
                zip_code = str(shipper_address.zip)
            shipper = endicia.Address(shipper_address.name,
                            shipper_address.street or shipper_address.street2,
                            shipper_address.city,
                            shipper_address.state_id and shipper_address.state_id.code or '',
                            zip_code,
                            shipper_address.country_id.code,
                            shipper_address.street and shipper_address.street2 or '',
                            shipper_address.phone or '',
                            shipper_address.email,
                            True,
#                            shipper_address.name
                          )
            # Recipient
            cust_address = picking.partner_id
            if not cust_address.name:
                raise ValidationError(_("You must enter Recipient Name."))
            if not (cust_address.street or cust_address.street2):
                raise ValidationError(_("You must enter Recipient Street."))
            if not cust_address.city:
                raise ValidationError(_("You must enter Recipient City."))
            if not cust_address.state_id:
                raise ValidationError(_("You must enter Recipient State."))
            if not cust_address.state_id.code:
                raise ValidationError(_("You must enter Recipient State Code."))
            if not cust_address.zip:
                raise ValidationError(_("You must enter Recipient Zip."))
            if not cust_address.country_id.code:
                raise ValidationError(_("You must enter Recipient Country."))

            # added handling because usps api support zip5 format.
            if str(cust_address.zip).find("-") != -1:
                zip_code = str(cust_address.zip).split("-")[0]
            else:
                zip_code = str(cust_address.zip)
            recipient = endicia.Address(cust_address.name or '',
                            cust_address.street or cust_address.street2,
                            cust_address.city,
                            cust_address.state_id and cust_address.state_id.code or '',
                            zip_code,
                            cust_address.country_id and cust_address.country_id.code,
                            cust_address.street and cust_address.street2 or '',
                            cust_address.phone or '',
                            cust_address.email, ''
                        )
            package_value = picking.sale_id.amount_total
            prod_weight = 0.0
            weight = self._convert_weight(picking.weight_bulk*0.453592, self.endicia_weight_unit) #weight reversed back to kg since client decides put all product weights in pounds
            if self.endicia_weight_unit == 'LB':
                prod_weight = weight * 16
            elif self.endicia_weight_unit == 'KG':
                prod_weight = weight * 35.274
            elif self.endicia_weight_unit == 'OUNCE':
                prod_weight = weight
            else:
                prod_weight = weight
            package = endicia.Package(self.endicia_service_type,
                                      round(prod_weight or 1.0),
                                      endicia.Package.shapes[self.endicia_container],
                                      self.endicia_length,
                                      self.endicia_width,
                                      self.endicia_height,
                                      picking.name,
                                      package_value
                                      )
            if recipient.country.lower() != 'us' and recipient.country.lower() != 'usa' and recipient.country.lower() != 'pr':
                if self.endicia_service_type not in ['FirstClassMailInternational', 'Priority Mail International']:
                    raise ValidationError("Please select carrier First Class Mail or Priority Mail International for international delivery")
                # (self, mail_class, weight_in_ozs, shape, length, width, height,
                #  description = '', value = 0, require_signature = False,
                #                                                   reference = u'')
                package = endicia.Package(self.endicia_service_type,
                                          int(round(prod_weight or 1.0)),
                                          endicia.Package.shapes[self.endicia_container],
                                          self.endicia_length,
                                          self.endicia_width,
                                          self.endicia_height,
                                          picking.name,
                                          package_value
                                          )
                international_label = True
            customs = []
            if international_label or self.endicia_label_type == 'Domestic':
                for move in picking.move_lines:
                    # if not move.product_id.bom_ids:
                    prod_weight = 0
                    prod_weight_unit = move.product_id.uom_po_id and move.product_id.uom_po_id.name or ''
                    weight_net = move.product_id.weight * move.product_qty or 0.1
                    if prod_weight_unit == 'LB':
                        prod_weight = weight_net * 16
                    elif prod_weight_unit == 'KG':
                        prod_weight = weight_net * 35.274
                    elif prod_weight_unit == 'OUNCE':
                        prod_weight = weight_net
                    else:
                        prod_weight = weight_net
                    custom_value = move.product_id.list_price or 1.0
                    customs.append(endicia.Customs(move.product_id.name,
                                                   int(move.product_qty),
                                                   float(prod_weight) or 1.0,
                                                   float(custom_value * move.product_qty) or 1.0,
                                                   shipper_address.country_id.code
                                                   ))
                    # elif prod_info.get('subproducts', False):
                    #     for component in prod_info.get('subproducts', False):
                    #         prod_brw = product_obj.browse(cr, uid, component.get('product_id', False))
                    #         prod_weight_unit = prod_brw.weight_unit
                    #         weight_net = prod_brw.product_tmpl_id.weight and prod_brw.product_tmpl_id.weight * int(
                    #             component['product_qty'] or 0) or 0.1
                    #         if prod_weight_unit and prod_weight_unit == 'LB':
                    #             prod_weight = weight_net * 16
                    #         elif prod_weight_unit and prod_weight_unit == 'KG':
                    #             prod_weight = weight_net * 35.274
                    #         elif prod_weight_unit and prod_weight_unit == 'OUNCE':
                    #             prod_weight = weight_net
                    #         else:
                    #             prod_weight = weight_net
                    #         custome_value = float(prod_brw.list_price) or 1.0
                    #         comp_qty = component.get('product_qty', 1) * move_line.product_qty
                    #         customs.append(endicia.Customs(str(component['name']),
                    #                                        int(comp_qty or 1),
                    #                                        float(prod_weight * comp_qty) or 1.0,
                    #                                        float(custome_value * comp_qty) or 1.0,
                    #                                        shipper_address.country_id.code
                    #                                        ))
            if self.endicia_label_type == 'DestinationConfirm' and not (
                self.endicia_container in ['Flat', 'Letter'] and package.mail_class in ['First',
                                                                                     'FirstClassMailInternational',
                                                                                     'PriorityMailInternational',
                                                                                     'Priority Mail Express International']):
                raise ValidationError('Container should be "Flat or Letter" and Shipping Service should be \
                "First-Class Mail", "First Class Mail International","Priority Mail International","Priority Mail \
                Express International" for Label Type "Destination Confirm"!')
            if self.endicia_label_type == 'CertifiedMail' and not (
                    self.endicia_container in ['Flat', 'Letter', 'Parcel'] and package.mail_class in [
                'First', 'Priority', 'FirstClassMailInternational', 'PriorityMailInternational',
                'Priority Mail Express International']):
                raise ValidationError('Container should be "Flat or Letter or Parcel" and supported Shipping'
                      ' Service are "First-Class Mail","Priority Mail","Priority Mail International","Priority Mail\
                       Express International","First Class Mail International" for Label Type "Certified Mail"!')
            # sending request to endicia for label
            request = endicia.LabelRequest(self.endicia_requester_id,
                                           self.endicia_account_id,
                                           self.endicia_passphrase,
                                           self.endicia_label_type,
                                           self.endicia_label_size,
                                           self.endicia_image_format,
                                           self.endicia_image_rotation,
                                           package, shipper, recipient,
                                           debug=self.endicia_test_mode,
                                           destination_confirm=True if self.endicia_service_type == 'First-Class Mail' and self.endicia_container == 'Letter' else False,
                                           customs_info=customs)
            response = request.send()
            endicia_res = response._get_value()
            ## creating attachment for label
            # label_name = 'ShippingLabel' + picking.name + '.' + self.endicia_image_format
            carrier_tracking_ref = endicia_res.get('tracking', False)
            carrier_price = float(endicia_res.get('cost',0))
            logmessage = (_("Shipment created into Endicia <br/> <b>Tracking Number : </b>%s") % (carrier_tracking_ref))
            picking.message_post(body=logmessage,
                                 attachments=[('LabelEndicia-%s.%s' % (carrier_tracking_ref, self.endicia_image_format), str(endicia_res['label']))])
            shipping_data = {
                'exact_price': carrier_price,
                'tracking_number': carrier_tracking_ref
            }
            res = res + [shipping_data]
        return res

    @api.multi
    def endicia_get_tracking_link(self, pickings):
        pass

    @api.multi
    def endicia_cancel_shipment(self, picking):
        pass

ProviderEndicia()

