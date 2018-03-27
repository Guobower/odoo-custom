# -*- coding: utf-8 -*-


from openerp import api, fields, models, _







class ResCompany(models.Model):
    _inherit = "res.company"



    def get_base_url(self, key='web.base.url'):
        return self.env['ir.config_parameter'].get_param(key)


ResCompany()
