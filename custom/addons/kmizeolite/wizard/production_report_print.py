# -*- coding: utf-8 -*-

from openerp import models, fields, api,_


class ProductionPrintReport(models.TransientModel):

    _name = "production.print.report"
    _description = "Production Report"

    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)


    @api.multi
    def get_data(self):
        return {
                    'from_date': self.from_date,
                    'to_date': self.to_date,
               }



    @api.multi
    def print_report(self, data):
        data = self.get_data()
        return self.env['report'].get_action(self, 'kmizeolite.print_report_production', data=data)

ProductionPrintReport()
