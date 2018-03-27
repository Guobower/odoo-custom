# -*- coding: utf-8 -*-


from openerp import api, fields, models, _







class AccountTax(models.Model):
    _inherit = "account.tax"

    state_id = fields.Many2one('res.country.state', string='State Applicable On')
    zip_codes = fields.Text(string='Tax Applicable Zip Codes')
    cities = fields.Text(string='Tax Applicable Cities')


AccountTax()


