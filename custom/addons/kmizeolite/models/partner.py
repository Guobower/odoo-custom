# -*- coding: utf-8 -*-


from openerp import api, fields, models, _







class ResPartner(models.Model):
    _inherit = "res.partner"




    is_freight_vendor = fields.Boolean(string="Freight Vendor")



ResPartner()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
