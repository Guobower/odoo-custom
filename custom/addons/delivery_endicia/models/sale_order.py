# -*- coding: utf-8 -*-


from openerp.osv import orm, fields
from openerp import SUPERUSER_ID
from openerp.tools.translate import _



class SaleOrder(orm.Model):
    _inherit = 'sale.order'

    def _get_delivery_methods(self, cr, uid, order, context=None):


        available_carrier_ids = super(SaleOrder, self)._get_delivery_methods(cr, uid, order, context=context)

        for carrier in self.pool.get('delivery.carrier').browse(cr, SUPERUSER_ID, available_carrier_ids, context=context):

            if carrier.delivery_type == 'endicia':

                if order.partner_shipping_id and order.partner_shipping_id.country_id and order.partner_shipping_id.country_id.code.lower() in ('us', 'usa'):

                    if order.weight_order <= 5 and carrier.endicia_service_type not in ['Priority Mail Flat Rate Padded Envelope', 'Priority Mail Express Flat Rate Padded Envelope',]:
                        available_carrier_ids.remove(carrier.id)

#                    if order.weight_order > 2 and order.weight_order <= 5 and carrier.endicia_service_type not in ['Priority Mail Small Flat Rate Box',]:
#                        available_carrier_ids.remove(carrier.id)

                    if order.weight_order > 5 and order.weight_order <= 10 and carrier.endicia_service_type not in ['Priority Mail Medium Flat Rate Box',]:
                        available_carrier_ids.remove(carrier.id)

                    if order.weight_order > 10 and order.weight_order <= 20 and carrier.endicia_service_type not in ['Priority Mail Large Flat Rate Box',]:
                        available_carrier_ids.remove(carrier.id)

                    if order.weight_order > 20 and carrier.endicia_service_type not in ['Parcel Select Ground',]:
                        available_carrier_ids.remove(carrier.id)

                if order.partner_shipping_id and order.partner_shipping_id.country_id and order.partner_shipping_id.country_id.code.lower() not in ('us', 'usa'):

                    if carrier.endicia_service_type not in ['Priority Mail International',]:
                        available_carrier_ids.remove(carrier.id)

        return available_carrier_ids

SaleOrder()
