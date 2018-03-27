# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'kmizeolite',
    'version' : '1.0',
    'summary': 'Warehouse Management',
    'sequence': 60,
    'description': """
Warehouse Update
==================
    """,
    'category' : 'General',
    'author': 'Confianz Global',
    'website': 'http://confianzit.com',
    'depends' : ['stock', 'portal_sale', 'delivery', 'purchase', 'account', 'website_sale', 'sale_order_dates'],
    'data': [
            "views/report_sale_pickticket_view.xml",
            "kmi_reports.xml",
            "data/mail_template_data.xml",
            "wizard/inventory_update_view.xml",
            "wizard/mail_compose_message_view.xml",
            "wizard/sale_report_print_view.xml",
            "wizard/production_report_print_view.xml",
            "views/sale_report_view.xml",
            "views/partner_view.xml",
            "views/sale_view.xml",
            "views/stock_picking_view.xml",
            "views/report_delivery_document_view.xml",
            "views/account_view.xml",
            "views/product_category_view.xml",
            "views/print_report_sale.xml",
            "views/print_report_production.xml",
            "views/product_view.xml",
            ],
    'installable': True,
    'application': False,
    'auto_install': False,

}
