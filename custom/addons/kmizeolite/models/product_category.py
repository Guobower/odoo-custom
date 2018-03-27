# -*- coding: utf-8 -*-


from openerp import api, fields, models, _







class ProductCategory(models.Model):
    _inherit = "product.category"




    product_type = fields.Selection([('granular', 'Granular Product'),
                                     ('powder', 'Powder Products'),
                                     ('service', 'Freight/Services'),
                                     ('package', 'Packaging Products'),
                                     ('sample', 'Sample'),
                                     ('other', 'Other')], string="Product Type")



ProductCategory()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
