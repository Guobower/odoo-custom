# -*- encoding: utf-8 -*-

{
    'name': 'Endicia Shipping',
    'version': '1.0',
    'category': 'Warehouse',
    'description': "Odoo Integration with Endicia.",
    'author': 'Confianz Global',
    'website': 'https://confianzit.com',
    'depends': ['sale','stock','delivery','website_sale_delivery'],
    'init_xml': [],
    'data': [
                'data/endicia_shipping_data.xml',
                'views/delivery_endecia_ecomm_view.xml',

            ],
    'demo_xml': [],
    'test': [],
    'installable': True,
    'application':False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
