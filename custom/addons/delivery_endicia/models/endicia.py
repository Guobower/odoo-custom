# -*- encoding: utf-8 -*-

import logging
import re
from urllib2 import Request, urlopen, URLError, quote
import base64
import xml.etree.ElementTree as etree
import threading, Queue
import suds
from suds.client import Client
from suds.sax.element import Element
from openerp.exceptions import ValidationError, UserError
_logger = logging.getLogger(__name__)

def get_country_code(country):
    lookup = {
        'us': 'US',
        'usa': 'US',
        'united states': 'US',
    }

    return lookup.get(country.lower(), country)


def _normalize_country(country):
    country_lookup = {
        'united states': 'United States',
        'us': 'United States',
        'usa': 'United States',
    }
    
    return country_lookup.get(country.lower(), False)


class Address(object):
    def __init__(self, name, address, city, state, zip, country, address2='', phone='', email='', is_residence=True,
                 company_name=''):
        self.company_name = company_name or ''
        self.name = name or ''
        self.address1 = address or ''
        self.address2 = address2 or ''
        self.city = city or ''
        self.state = state or ''
        self.zip = str(zip).split('-')[0] if zip else ''
        self.country = country or ''
        self.phone = re.sub('[^0-9]*', '', str(phone)) if phone else ''
        self.email = email or ''
        self.is_residence = is_residence or False

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __repr__(self):
        street = self.address1
        if self.address2:
            street += '\n' + self.address2
        return '%s\n%s\n%s, %s %s %s' % (self.name, street, self.city, self.state, self.zip, self.country)


class EndiciaError(Exception):
    pass

class EndiciaWebError(EndiciaError):
    def __init__(self, fault, document):
        self.fault = fault
        self.document = document
        
        error_text = 'Endicia error {}: {}'.format(fault.faultcode, fault.faultstring)
        super(EndiciaWebError, self).__init__(error_text)


class Customs(object):
    def __init__(self, description, quantity, weight, value, country):
        self._description = description
        self._quantity = quantity
        self._weight = weight
        self._value = value
        self._country = country
    
    @property
    def description(self):
        return self._description
    
    @property
    def quantity(self):
        return self._quantity
    
    @property
    def weight(self):
        return self._weight
    
    @property
    def value(self):
        return self._value
    
    @property
    def country(self):
        return self._country


class Package(object):
        # Used for input from shipping info form - refer stock.py for dict keys
        domestic_shipment_types = {
            'Priority Mail': 'Priority',
            'Express Mail': 'Express',
            'First-Class Mail': 'First',
            'Library Mail': 'LibraryMail',
            'Media Mail': 'MediaMail',
            'Parcel Post': 'ParcelPost',
            'Parcel Select': 'ParcelSelect',
            'Standard Mail Class': 'StandardMailClass',
            'Priority Mail Express': 'Express',
            'Standard Post': 'StandardPost',
            # added
            'Parcel Select Barcoded Nonpresorted': 'ParcelSelect',
            'Priority Mail Flat Rate Envelope': 'Priority',
            'Priority Mail Express Flat Rate Envelope': 'Express',
            'Priority Mail Flat Rate Padded Envelope': 'Priority',
            'Priority Mail Express Flat Rate Padded Envelope': 'Express',
            'Priority Mail Flat Rate Legal Envelope': 'Priority',
            'Priority Mail Express Flat Rate Legal Envelope': 'Express',
            'Priority Small Flat Rate Envelope': 'Priority',
            'Priority Mail Flat Rate Window Envelope': 'Priority',
            'Priority Mail Flat Rate Gift Card Envelope': 'Priority',
            'Priority Mail Flat Rate Cardboard Envelope': 'Priority',
            'Priority Mail Small Flat Rate Box': 'Priority',
            'Priority Mail Medium Flat Rate Box': 'Priority',
            'Priority Mail Express Flat Rate Box': 'Express',
            'Priority Mail Large Flat Rate Box': 'Priority',
            'Priority Mail Regional Rate Box B': 'Priority',
            'Priority Mail Regional Rate Box A': 'Priority',
        }

        international_shipment_types = {
            'ExpressMailInternational': 'ExpressMailInternational',
            'FirstClassMailInternational': 'FirstClassMailInternational',
            'PriorityMailInternational': 'PriorityMailInternational',
            'Priority Mail International':'PriorityMailInternational',
            'Priority Mail International Flat Rate Padded Envelope': 'Priority Mail International Flat Rate Padded Envelope',
            'Priority Mail International Small Flat Rate Box': 'Priority Mail International Small Flat Rate Box',
            'Priority Mail International Medium Flat Rate Box': 'Priority Mail International Medium Flat Rate Box',
            'Priority Mail International Large Flat Rate Box': 'Priority Mail International Large Flat Rate Box',
        }

        shapes = {
            'Null': 'Null',
            'Parcel': 'Parcel',
            'Card': 'Card',
            'Letter': 'Letter',
            'Flat': 'Flat',
            'Large Parcel': 'LargeParcel',
            'Irregular Parcel': 'IrregularParcel',
            'Oversized Parcel': 'OversizedParcel',
            'Flat Rate Envelope': 'FlatRateEnvelope',
            'Legal Flat Rate Envelope': 'FlatRateLegalEnvelope',
            'Padded Flat Rate Envelope': 'FlatRatePaddedEnvelope',
            'Gift Card Flat Rate Envelope': 'FlatRateGiftCardEnvelope',
            'Window Flat Rate Envelope': 'FlatRateWindowEnvelope',
            'Cardboard Flat Rate Envelope': 'FlatRateCardboardEnvelope',
            'SM Flat Rate Envelope': 'SmallFlatRateEnvelope',
            'SM Flat Rate Box': 'SmallFlatRateBox',
            'MD Flat Rate Box': 'MediumFlatRateBox',
            'LG Flat Rate Box': 'LargeFlatRateBox',
            'RegionalRateBoxA': 'RegionalRateBoxA',
            'RegionalRateBoxB': 'RegionalRateBoxB',
        }

        def __init__(self, mail_class, weight_in_ozs, shape, length, width, height, description='', value=0, require_signature=False,
                     reference=u''):
            self.mail_class = self.domestic_shipment_types.get(mail_class) and self.domestic_shipment_types[
                mail_class] or self.international_shipment_types.get(mail_class) and self.international_shipment_types[
                mail_class] or mail_class.replace(" ", "")
            self.weight_oz = str(weight_in_ozs) if float(weight_in_ozs) >= 1.0 else str(1.0)
            self.length = length
            self.width = width
            self.height = height
            self.value = str(value)
            self.require_signature = require_signature
            self.reference = reference
            self.shape = shape
            self.dimensions = (str(length), str(width), str(height))
            self.description = description

        @property
        def weight_in_ozs(self):
            return self.weight_oz

        @property
        def weight_in_lbs(self):
            return self.weight_oz / 16


# class Package(object):
#     domestic_shipment_types = {
#         'Priority Mail': 'Priority',
#         'Express Mail': 'Express',
#         'First-Class Mail': 'First',
#         'Library Mail': 'LibraryMail',
#         'Media Mail': 'MediaMail',
#         'Parcel Post': 'ParcelPost',
#         'Parcel Select': 'ParcelSelect',
#         'Standard Mail Class': 'StandardMailClass',
#         'Priority Mail Express':'Express',
#         'Standard Post':'StandardPost',
#         # added
#         'Parcel Select Barcoded Nonpresorted': 'ParcelSelect',
#         'Priority Mail Flat Rate Envelope':'Priority',
#         'Priority Mail Express Flat Rate Envelope':'Express',
#         'Priority Mail Flat Rate Padded Envelope':'Priority',
#         'Priority Mail Express Flat Rate Padded Envelope': 'Express',
#         'Priority Mail Flat Rate Legal Envelope':'Priority',
#         'Priority Mail Express Flat Rate Legal Envelope':'Express',
#         'Priority Small Flat Rate Envelope':'Priority',
#         'Priority Mail Flat Rate Window Envelope':'Priority',
#         'Priority Mail Flat Rate Gift Card Envelope':'Priority',
#         'Priority Mail Flat Rate Cardboard Envelope':'Priority',
#         'Priority Mail Small Flat Rate Box':'Priority',
#         'Priority Mail Medium Flat Rate Box':'Priority',
#         'Priority Mail Express Flat Rate Box':'Express',
#         'Priority Mail Large Flat Rate Box':'Priority',
#         'Priority Mail Regional Rate Box B':'Priority',
#         'Priority Mail Regional Rate Box A':'Priority',
#     }
#
#     international_shipment_types = {
#         'Express Mail International': 'ExpressMailInternational',
#         'First Class Mail International': 'FirstClassMailInternational',
#         'Priority Mail International': 'PriorityMailInternational',
#     }
#
#     shapes = {
#         'Parcel':'Parcel',
#         'Card': 'Card',
#         'Letter': 'Letter',
#         'Flat': 'Flat',
#         'Large Parcel': 'LargeParcel',
#         'Irregular Parcel': 'IrregularParcel',
#         'Oversized Parcel': 'OversizedParcel',
#         'Flat Rate Envelope': 'FlatRateEnvelope',
#         'Legal Flat Rate Envelope': 'FlatRateLegalEnvelope',
#         'Padded Flat Rate Envelope': 'FlatRatePaddedEnvelope',
#         'Gift Card Flat Rate Envelope': 'FlatRateGiftCardEnvelope',
#         'Window Flat Rate Envelope': 'FlatRateWindowEnvelope',
#         'Cardboard Flat Rate Envelope': 'FlatRateCardboardEnvelope',
#         'SM Flat Rate Envelope': 'SmallFlatRateEnvelope',
#         'SM Flat Rate Box': 'SmallFlatRateBox',
#         'MD Flat Rate Box': 'MediumFlatRateBox',
#         'LG Flat Rate Box': 'LargeFlatRateBox',
#         'RegionalRateBoxA': 'RegionalRateBoxA',
#         'RegionalRateBoxB': 'RegionalRateBoxB',
#     }
#
#     def __init__(self, mail_class, weight_oz, shape, length, width, height, description='', value=0, require_signature=0, reference='a12302b',**kwargs):
#         print "inside package in it"
#         self.mail_class = self.domestic_shipment_types.get(mail_class) and self.domestic_shipment_types[mail_class] or self.international_shipment_types.get(mail_class) and self.international_shipment_types[mail_class] or mail_class
#         self.weight_oz = str(weight_oz) if float(weight_oz) >= 1.0 else str(1.0)
#         self.shape = shape
#         self.dimensions = ( str(length), str(width), str(height) )
#         self.description = description
#         self.value = str(value)
        
class Endicia(object):
    def __init__(self, credentials, debug=True):
        self.wsdl_url = 'https://elstestserver.endicia.com/LabelService/EwsLabelService.asmx?WSDL' if debug else 'https://LabelServer.Endicia.com/LabelService/EwsLabelService.asmx?WSDL'
        self.credentials = credentials
        self.debug = debug
        self.client = Client(self.wsdl_url)        
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger('suds.client').setLevel(logging.ERROR)
        logging.getLogger('suds.transport').setLevel(logging.ERROR)
        logging.getLogger('suds.xsd.schema').setLevel(logging.ERROR)
        logging.getLogger('suds.wsdl').setLevel(logging.ERROR)

    def rate(self, packages, packaging_type, shipper, recipient, insurance='OFF', insurance_amount=0, delivery_confirmation=False, signature_confirmation=False):
        q = Queue.Queue()
        self._rate_action(q, packages, packaging_type, shipper, recipient, insurance, insurance_amount, delivery_confirmation, signature_confirmation)
        # threaded_calculation = threading.Thread(target=self._rate_action, args=(q, packages, packaging_type, shipper, recipient, insurance, insurance_amount, delivery_confirmation, signature_confirmation))
        # threaded_calculation.start()
        response = q.get()        
        return response

    def _rate_action(self, q, packages, packaging_type, shipper, recipient, insurance='OFF', insurance_amount=0, delivery_confirmation=False, signature_confirmation=False):
        to_country_code = get_country_code(recipient.country)
        request = self.client.factory.create('PostageRatesRequest')
        request.RequesterID = self.credentials['partner_id']
        request.CertifiedIntermediary.AccountID = self.credentials['account_id']
        request.CertifiedIntermediary.PassPhrase = self.credentials['passphrase']
        request.MailClass = 'Domestic' if (to_country_code.upper() == 'US' or to_country_code.upper() == 'PR') else 'International'
        if hasattr(packages[0], 'weight_oz'):
            request.WeightOz = packages[0].weight_oz
        if hasattr(packages[0], 'weight_in_ozs'):
            request.WeightOz = packages[0].weight_in_ozs        
        request.MailpieceShape = packaging_type
        request.Machinable = True
        request.FromPostalCode = shipper.zip
        request.ToPostalCode = recipient.zip
        request.ToCountryCode = to_country_code        
        request.CODAmount = 0
        request.InsuredValue = insurance_amount
        request.RegisteredMailValue = packages[0].value
        request.Services._InsuredMail = insurance
        request.Services._DeliveryConfirmation = 'ON' if delivery_confirmation else 'OFF'
        request.Services._SignatureConfirmation = 'ON' if signature_confirmation else 'OFF'
        # logging.error(request)
        try:
            reply = self.client.service.CalculatePostageRates(request)
            _logger.info(reply)
            if reply.Status != 0:                
                raise ValidationError("Endicia Error\n\t %s"%reply.ErrorMessage)
            response = {'status': reply.Status, 'info': list()}
            for details in reply.PostagePrice:
                response['info'].append({
                    'service': details.Postage.MailService,
                    'package': details.MailClass,
                    'delivery_day': '',
                    'cost': details._TotalAmount
                })
            q.put(response)
        except suds.WebFault as e:
            raise ValidationError("Endicia Error\n\t %s\n%s"%(e.fault, e.document))


class EndiciaRequest(object):
    def __init__(self, url, api, debug=False):
        self.debug = debug
        self.url = url
        self.api = api
        
    def send(self):        
        q = Queue.Queue()
        target=self._send_action(q)
        response = q.get()        
        return response

    def send_scan(self):
        root = self._get_xml()        
        request_text = etree.tostring(root)        
        try:
            url_base = u'https://www.endicia.com/ELS/ELSServices.cfc?wsdl'
            full_url = u'%s&method=%s' % (url_base, self.url)
            data = '&XMLInput=%s' % (quote(request_text))
            request = Request(full_url, data)
            response_text = urlopen(request).read()
            response_text = etree.fromstring(response_text)
            response = self._parse_response_body(root, response_text)
        except URLError, e :
            if hasattr(e, 'reason'):
                raise ValidationError( 'Could not reach the server, reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                raise ValidationError( 'Could not fulfill the request, code: %d' % e.code)
            raise
        return response
    
    def _send_action(self, q):
        root = self._get_xml()
        request_text = etree.tostring(root)
        try:
            url_base = u'https://elstestserver.endicia.com/LabelService/EwsLabelService.asmx' if self.debug  else u'https://LabelServer.Endicia.com/LabelService/EwsLabelService.asmx'
            full_url = u'%s/%s' % (url_base, self.url)
            data = '%s=%s' % (self.api, quote(request_text))
            request = Request(full_url, data)
            response_text = urlopen(request).read()
            response = self.__parse_response(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                raise ValidationError( 'Could not reach the server, reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                raise ValidationError( 'Could not fulfill the request, code: %d' % e.code)
            raise
        q.put(response)
        
    def __parse_response(self, response_text):
        """Parses the text from an Endicia web service call"""        
        root = etree.fromstring(response_text)        
        namespace = re.search('{(.*)}', root.tag).group(1)        
        status_path = '{%s}Status' % namespace
        status = int(root.findtext(status_path))
        response = None
        if status != 0:
            error_path = '{%s}ErrorMessage' % namespace
            message = root.findtext(error_path).encode('UTF-8')            
            raise UserError(message)
        else:
            response = self._parse_response_body(root, namespace)
        return response


class Error(object):
    def __init__(self, status, root, namespace):
        self.status = status
        error_path = '{%s}ErrorMessage' % namespace
        self.message = root.findtext(error_path).encode('UTF-8')
        
    def __repr__(self):
        return 'Endicia error %d: %s' % (self.status, self.message)

class SCANReportRequest(EndiciaRequest):
    def __init__(self, account_id, passphrase, form_type, from_name, from_address, from_city, from_state, from_zip, submission_id,
                image_format, cost_center, reference_id, dpi, scan_list, debug=False):#
        url = u'SCANRequest'
        api = u'SCANRequest'        
        super(SCANReportRequest, self).__init__(url, api, debug)
        self.account_id = account_id
        self.passphrase = passphrase
        self.form_type = form_type        
        self.from_name = from_name
        self.from_address = from_address
        self.from_city = from_city
        self.from_state = from_state
        self.from_zip = from_zip
        self.submission_id = submission_id
        self.image_format = image_format
        self.cost_center = cost_center
        self.reference_id = reference_id
        self.dpi = dpi
        self.scan_list = scan_list

    def _parse_response_body(self, root, response_data):
        return SCANReportResponse(root, response_data)

    def _get_xml(self):
        test = ''
        root = etree.Element('SCANRequest')               
        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase                       
        if self.debug:
            etree.SubElement(root, u'Test').text = 'Y'
        else:
            etree.SubElement(root, u'Test').text = 'N'
        etree.SubElement(root, u'DPI').text = self.dpi
        scanlist_val = self.scan_list.values()                
        for pic in scanlist_val:            
            scanlist = etree.SubElement(root, u'SCANList')            
            etree.SubElement(scanlist, u'PICNumber').text = pic['pic_number']
            etree.SubElement(scanlist, u'PieceID').text = pic['custom_id']
            etree.SubElement(scanlist, u'CustomsID').text = pic['piece_id']                
        return root

class SCANReportResponse(object):
    def __init__(self, root ,response_text):        
        for each_response in response_text :
            if each_response.tag == 'SCANForm' and each_response.text:
                self.label = base64.b64decode(each_response.text)                
            if each_response.tag == 'SubmissionID' and each_response.text:
                self.submission_id = each_response.text

    def __repr__(self):
        return 'Tracking: %s, Submission id: $%s, Label: %s' % (self.submission_id, self.label)

    def _get_value(self):
        response = {'submission':self.submission_id, 'label': self.label}
        return response


class LabelRequest(EndiciaRequest):    
    def __init__(self, partner_id, account_id, passphrase, label_type, label_size, image_format, image_rotation, package, shipper, recipient,debug=False,
                       stealth=True, value=0, insurance='OFF', insurance_amount=0,
                       customs_form='None', customs_info=list(),
                       contents_type='', contents_explanation='', nondelivery='Return',
                       date_advance=0,
                       delivery_confirmation=False, signature_confirmation=False, destination_confirm=False,
                       customs_signer=None):               
        url = u'GetPostageLabelXML'
        api = u'LabelRequestXML'        
        super(LabelRequest, self).__init__(url, api, debug)        
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        self.label_type = label_type
        self.label_size = label_size
        self.image_format = image_format
        self.image_rotation = image_rotation        
        self.package = package
        self.shipper = shipper
        self.recipient = recipient
        self.stealth = 'TRUE' if stealth else 'FALSE'
        self.value = value
        self.insurance = insurance
        self.insurance_amount = insurance_amount        
        self.customs_form = customs_form
        self.customs_info = customs_info
        self.contents_type = contents_type
        self.contents_explanation = contents_explanation
        self.nondelivery = nondelivery
        self.date_advance = date_advance
        self.delivery_confirmation = u'ON' if delivery_confirmation else u'OFF'
        self.signature_confirmation = u'ON' if signature_confirmation else u'OFF'
        self.destination_confirm = destination_confirm
        self.label_type = 'International' if package.mail_class in Package.international_shipment_types.keys() else label_type
        self.customs_signer = customs_signer
        
    def _parse_response_body(self, root, namespace):
        return LabelResponse(root, namespace)
        
    def _get_xml(self):        
        root = etree.Element('LabelRequest')
        root.set('LabelType', self.label_type if not self.destination_confirm else 'DestinationConfirm')
        root.set('LabelSubtype', 'Integrated' if self.label_type in ('Domestic','International') else 'None')
#        root.set('LabelSubtype', 'Integrated' if self.label_type in ('International') else 'None')
        if self.label_type != 'International':
            root.set('LabelSize', self.label_size if not self.destination_confirm else '6X4')            
            root.set('ImageFormat', self.image_format)
            root.set('ImageRotation', self.image_rotation if not self.destination_confirm else 'None')                
        if self.debug:
            root.set('Test', 'YES')        
        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase
        mail_class = ''                    
        if self.package.mail_class == 'Priority Mail Express International':
            mail_class = 'ExpressMailInternational'        

        if self.package.mail_class == 'ParcelSelectGround':
            mail_class = 'ParcelSelect'

        else:
            mail_class = self.package.mail_class
        etree.SubElement(root, u'MailClass').text = mail_class
        etree.SubElement(root, u'WeightOz').text = self.package.weight_oz
        etree.SubElement(root, u'MailpieceShape').text = self.package.shape
        etree.SubElement(root, u'Stealth').text = self.stealth
        etree.SubElement(root, u'Value').text = self.package.value        
        etree.SubElement(root, u'Description').text = self.package.description        
        etree.SubElement(root, u'PartnerCustomerID').text = 'SomeCustomerID'
        etree.SubElement(root, u'PartnerTransactionID').text = 'SomeTransactionID'        
        etree.SubElement(root, u'ResponseOptions').set('PostagePrice', 'TRUE')        
        self.__add_address(self.shipper, 'From', root)
        self.__add_address(self.recipient, 'To', root)        
        etree.SubElement(root, u'InsuredValue').text = str(self.insurance_amount)        
        etree.SubElement(root, u'NonDeliveryOption').text = self.nondelivery
        etree.SubElement(root, u'DateAdvance').text = str(self.date_advance)
        if self.label_type in ('Domestic','International'):
            if self.recipient.city in ('APO','FPO','DPO'): 
                etree.SubElement(root, u'IntegratedFormType').text = 'Form2976'
            elif self.package.mail_class in ('FirstClassMailInternational', 'PriorityMailInternational'):
                etree.SubElement(root, u'IntegratedFormType').text = 'Form2976'
            else:
                etree.SubElement(root, u'IntegratedFormType').text = 'Form2976A' 
        # added for Parcel Select Barcoded Nonpresorted
        if self.package.mail_class in ['ParcelSelect', 'ParcelSelectGround']:
            etree.SubElement(root, u'SortType').text = 'Nonpresorted'
            etree.SubElement(root, u'EntryFacility').text = 'Other'
        services = etree.SubElement(root, u'Services')
        services.set(u'DeliveryConfirmation', self.delivery_confirmation)
        services.set(u'SignatureConfirmation', self.signature_confirmation)
        services.set(u'InsuredMail', self.insurance)
        if self.customs_info:
            customsinfo = etree.SubElement(root, u'CustomsInfo')
            etree.SubElement(customsinfo, u'ContentsType').text = 'Merchandise'
            customsitems = etree.SubElement(customsinfo, u'CustomsItems')
            for i, info in enumerate(self.customs_info):    
                customsitem = etree.SubElement(customsitems, u'CustomsItem')
                etree.SubElement(customsitem, u'Description').text = info.description[:50]
                etree.SubElement(customsitem, u'Quantity ').text = str(info.quantity)
                etree.SubElement(customsitem, u'Weight').text = str(info.weight)
                etree.SubElement(customsitem, u'Value').text = str(info.value) 
                etree.SubElement(customsitem, u'CountryOfOrigin').text = str(info.country)
        if len(self.customs_info) and self.customs_signer:
            etree.SubElement(root, u'CustomsCertify').text = 'TRUE'
            etree.SubElement(root, u'CustomsSigner').text = self.customs_signer
        return root
        
    def __add_address(self, address, type, root):
        info = dict()
        info['Company'] = address.company_name
        info['Name'] = address.name
        info['Address1'] = address.address1
        info['City'] = address.city
        info['State'] = address.state
        info['PostalCode'] = address.zip
        info['Country'] = _normalize_country(address.country.upper()) or address.country
        if address.country.upper() != 'US' and address.country.upper() != 'USA':
            info['CountryCode'] = address.country.upper()
        if address.phone:
            info['Phone'] = address.phone
        if address.address2:
            info['Address2'] = address.address2
        for key, value in info.items():
            # Endicia expects ReturnAddressX instead of FromAddressX
            if type == 'From' and 'Address' in key:
                element_key = 'Return%s' % key
            else:
                element_key = '%s%s' % (type, key)
            etree.SubElement(root, element_key).text = value
            
class LabelResponse(object):
    def __init__(self, root, namespace):
        self.root = root        
        self.tracking = root.findtext('{%s}TrackingNumber' % namespace)
        self.postage = root.findtext('{%s}FinalPostage' % namespace)
        encoded_image = root.findtext('{%s}Base64LabelImage' % namespace)                
        if not encoded_image:
            encoded_image = root.findtext('{%s}Label/{%s}Image' % (namespace,namespace))
        self.label = base64.b64decode(encoded_image)
        
    def __repr__(self):
        return 'Tracking: %s, cost: $%s, Label: %s' % (self.tracking, self.postage, self.label)

    def _get_value(self):
        response = {'tracking': self.tracking, 'cost':self.postage, 'label': self.label}
        return response
        
class RecreditRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, amount, debug=False):
        url = u'BuyPostageXML'
        api = u'recreditRequestXML'
        super(RecreditRequest, self).__init__(url, api, debug)
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase        
        self.amount = str(amount)

    def _parse_response_body(self, root, namespace):
        return RecreditResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element('RecreditRequest')        
        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'Recredit %s for %s' % (self.partner_id, self.amount)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase        
        etree.SubElement(root, u'RecreditAmount').text = self.amount
        return root

class RecreditResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.account_status = root.findtext('{%s}CertifiedIntermediary/{%s}AccountStatus' % (namespace, namespace))
        self.postage_balance = root.findtext('{%s}CertifiedIntermediary/{%s}PostageBalance' % (namespace, namespace))
        self.postage_printed = root.findtext('{%s}CertifiedIntermediary/{%s}AscendingBalance' % (namespace, namespace))

    def __repr__(self):
        return 'Status: %s, Balance: $%s, Total Printed: $%s' % (self.account_status, self.postage_balance, self.postage_printed)

    def _get_value(self):
        response = {'status': self.account_status, 'postage_balance':self.postage_balance, 'postage_printed': self.postage_printed}
        return response
        
class ChangePasswordRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, new_passphrase, debug=False):
        url = u'ChangePassPhraseXML'
        api = u'changePassPhraseRequestXML'
        super(ChangePasswordRequest, self).__init__(url, api, debug)
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        self.new_passphrase = new_passphrase

    def _parse_response_body(self, root, namespace):
        return ChangePasswordResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element('ChangePassPhraseRequest')
        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'ChangePassPhrase %s' % (self.partner_id)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase
        etree.SubElement(root, u'NewPassPhrase').text = self.new_passphrase
        return root

class ChangePasswordResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.status = root.findtext('{%s}Status' % namespace)

    def __repr__(self):
        return 'Password Change: %s' % ('OK' if int(self.status) == 0 else 'Error')

    def _get_value(self):
        response = {'status': self.status}
        return response
        
class RateRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, package, shipper, recipient, debug=False):
        url = u'CalculatePostageRateXML'
        api = u'postageRateRequestXML'
        super(RateRequest, self).__init__(url, api, debug)
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase
        self.package = package
        self.shipper = shipper
        self.recipient = recipient

    def _parse_response_body(self, root, namespace):
        return RateResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element('PostageRateRequest')
        etree.SubElement(root, u'RequesterID').text = self.partner_id
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase        
        etree.SubElement(root, u'MailClass').text = self.package.mail_class        
        etree.SubElement(root, u'WeightOz').text = self.package.weight_oz
        etree.SubElement(root, u'MailpieceShape').text = self.package.shape
        etree.SubElement(root, u'Value').text = self.package.value        
        etree.SubElement(root, u'FromPostalCode').text = self.shipper.zip
        etree.SubElement(root, u'ToPostalCode').text = self.recipient.zip        
        etree.SubElement(root, u'ResponseOptions').set('PostagePrice', 'TRUE')
        return root

class RateResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.postage_price = root.find('{%s}PostagePrice' % namespace).get('TotalAmount')

    def __repr__(self):
        return 'Estimated Cost: $%s' % self.postage_price
        
class AccountStatusRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, debug=False):
        url = u'GetAccountStatusXML'
        api = u'accountStatusRequestXML'
        super(AccountStatusRequest, self).__init__(url, api, debug)
        self.partner_id = partner_id
        self.account_id = account_id
        self.passphrase = passphrase

    def _parse_response_body(self, root, namespace):
        return AccountStatusResponse(root, namespace)

    def _get_xml(self):
        root = etree.Element('AccountStatusRequest')
        etree.SubElement(root, u'RequesterID').text = self.partner_id
        etree.SubElement(root, u'RequestID').text = 'AccountStatusRequest %s' % (self.partner_id)
        ci = etree.SubElement(root, u'CertifiedIntermediary')
        etree.SubElement(ci, u'AccountID').text = self.account_id
        etree.SubElement(ci, u'PassPhrase').text = self.passphrase
        return root

class AccountStatusResponse(object):
    def __init__(self, root, namespace):
        self.root = root
        self.serial_number = root.findtext('{%s}CertifiedIntermediary/{%s}SerialNumber' % (namespace, namespace))
        self.postage_balance = root.findtext('{%s}CertifiedIntermediary/{%s}PostageBalance' % (namespace, namespace))
        self.postage_printed = root.findtext('{%s}CertifiedIntermediary/{%s}AscendingBalance' % (namespace, namespace))
        self.account_status = root.findtext('{%s}CertifiedIntermediary/{%s}AccountStatus' % (namespace, namespace))
        self.device_id = root.findtext('{%s}CertifiedIntermediary/{%s}DeviceID' % (namespace, namespace))

    def __repr__(self):
        return 'Status: %s, Balance: $%s, Total Printed: $%s' % (self.account_status, self.postage_balance, self.postage_printed)

    def _get_value(self):
        response = {'serial_number': self.serial_number,
                    'postage_balance': self.postage_balance,
                    'postage_printed': self.postage_printed,
                    'account_status': self.account_status,
                    'device_id': self.device_id }
                    
        return response

class RefundRequest(EndiciaRequest):
    def __init__(self, partner_id, account_id, passphrase, tracking_number, debug=False):
        url = u'RefundRequestXML'
        api = u'refundRequestXML'
        super(RefundRequest, self).__init__(url, api, debug)        
        self.account_id = account_id
        self.passphrase = passphrase
        self.tracking_number = tracking_number
        self.debug = debug
    
    def send(self):        
        root = self._get_xml()
        request_text = etree.tostring(root)        
        try:
            url_base = u'https://www.endicia.com/ELS/ELSServices.cfc?wsdl'
            full_url = u'%s&method=RefundRequest' % url_base
            data = 'XMLInput=%s' % quote(request_text)            
            request = Request(full_url, data)
            response_text = urlopen(request).read()            
            response = self.__parse_response(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                raise ValidationError(_('Could not reach the server, reason: %s' % e.reason))
            elif hasattr(e, 'code'):
                raise ValidationError(_('Could not fulfill the request, code: %d' % e.code))
        return response

    def __parse_response(self, response_text):
        """Parses the text from an Endicia web service call"""
        root = etree.fromstring(response_text)
        error_msg = root.findtext('ErrorMsg')        
        response = None
        if error_msg:
            raise ValidationError(error_msg)
        else:
            response = self._parse_response_body(root)
        return response
    
    def _parse_response_body(self, root):
        return RefundResponse(root)
    
    def _get_xml(self):
        root = etree.Element('RefundRequest')
        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase
        etree.SubElement(root, u'Test').text = 'Y' if self.debug else 'N'
        refund_list = etree.SubElement(root, u'RefundList')
        for track_no in self.tracking_number:
            etree.SubElement(refund_list, u'PICNumber').text = track_no
        return root

class RefundResponse(object):
    def __init__(self, root):
        self.root = root
        refund_list = root.find('RefundList')
        self.tracking_no = refund_list.findall('PICNumber')
        self.is_approved = []
        self.error_msg = []
        for each_no in self.tracking_no:
            self.is_approved.append(each_no.find('IsApproved'))
            self.error_msg.append(each_no.find('ErrorMsg'))
            
    def _get_value(self):
        return {'tracking_no': self.tracking_no, 'is_approved':self.is_approved, 'error_msg':self.error_msg}


class StatusRequest(EndiciaRequest):
    def __init__(self, account_id, passphrase, tracking_number, debug=False):
        url = u'StatusRequest'
        api = u'StatusRequest'
        super(StatusRequest, self).__init__(url, api, debug)
        self.account_id = account_id
        self.passphrase = passphrase
        self.tracking_number = tracking_number
        self.debug = debug

    def send(self):
        root = self._get_xml()
        request_text = etree.tostring(root)
        try:
            url_base = u'https://www.endicia.com/ELS/ELSServices.cfc?wsdl'
            full_url = u'%s&method=StatusRequest' % url_base
            data = 'XMLInput=%s' % quote(request_text)
            request = Request(full_url, data)
            response_text = urlopen(request).read()
            response = self.__parse_response(response_text)
        except URLError, e:
            if hasattr(e, 'reason'):
                raise ValidationError ('Could not reach the server, reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                raise ValidationError('Could not fulfill the request, code: %d' % e.code)
            raise
        return response

    def __parse_response(self, response_text):
        """Parses the text from an Endicia web service call"""
        root = etree.fromstring(response_text)
        error_msg = root.findtext('ErrorMsg')
        response = None
        if error_msg:
#            raise Exception(error_msg)
            raise ValidationError(error_msg)
        else:
            response = self._parse_response_body(root)
        return response

    def _parse_response_body(self, root):
        return StatusResponse(root)

    def _get_xml(self):
        root = etree.Element('StatusRequest')
        etree.SubElement(root, u'AccountID').text = self.account_id
        etree.SubElement(root, u'PassPhrase').text = self.passphrase
        etree.SubElement(root, u'Test').text = 'Y' if self.debug else 'N'
        etree.SubElement(root, u'FullStatus').text = 'YES'
        refund_list = etree.SubElement(root, u'StatusList')
        for track_no in self.tracking_number:
            etree.SubElement(refund_list, u'PICNumber').text = track_no
        return root

class StatusResponse(object):
    def __init__(self, root):
        self.root = root
        status_list = root.find('StatusList')
        self.tracking_no = status_list.findall('PICNumber')
        self.status = []
        self.status_code = []
        for each_no in self.tracking_no:
            self.status.append(each_no.find('Status'))
            self.status_code.append(each_no.find('StatusCode'))

    def _get_value(self):
        return {'tracking_no': self.tracking_no, 'status':self.status, 'status_code':self.status_code}
