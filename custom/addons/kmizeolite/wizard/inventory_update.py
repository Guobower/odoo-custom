# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp import models, fields, api,_
from openerp.exceptions import UserError
import csv
import StringIO
import base64

class import_inventory(models.TransientModel):
    _name="import.inventory"



    @api.model
    def _default_stock_location(self):
        try:
            warehouse = self.env.ref('stock.warehouse0')
            return warehouse.lot_stock_id.id
        except:
            return False



    name = fields.Char(required=True, string='Import Reference')
    parent_location_id = fields.Many2one('stock.location', required=True, default=_default_stock_location, string='Inventoried Location')
    upload_file = fields.Binary(string='File', help="File to check and/or import, raw binary (not base64)")
    file_name = fields.Char(string='File name')
    line_ids = fields.One2many('import.inventory.line', 'parent_id', required=True, string='Lines')




    @api.multi
    @api.onchange('upload_file')
    def onchange_load_data(self):
        """
        When a new csv file is uploaded, this method checks
        the file type, and integrity and loads product data
        in the file into the lines. if no file, it resets 
        the lines.
        """
        for data in self:
            if not data.upload_file:
                data.line_ids = []
                continue
            # check if valid csv file
            upld_file = base64.decodestring(data.upload_file)
            file_stream = StringIO.StringIO(upld_file)
            if not data.file_name.endswith('.csv'):
                data.upload_file=''
                data.file_name=''
                return {'warning': {'title': 'Error!', 'message': 'Invalid File Type, Please import a csv file.'}}
            reader = csv.reader(file_stream, delimiter=',')
            count = 0
            result = []
            for row in reader:
                # check file integrity in first iteration
                if count == 0:
                    count += 1
                    if not (row[0].lower().strip() in ('product', 'sku') or row[1].lower().strip() in ('quantity', 'qty')):
                        data.upload_file = ''
                        data.file_name = ''
                        return {'warning': {'title': 'Error!', 'message': 'Incompatiable csv file!\nThe column headers should be \'Location, Product, Quantity\' and should also follow the same order.'}}

                else:
                    product_id = self.env['product.product'].search([('default_code', '=', row[0].strip() or 0)], limit=1)
                    qty = float(row[1].strip())

                    if not product_id:
                        message = "The Product SKU '%s' is not a valid SKU present in the system, please check!" %(row[0].strip())
                        data.upload_file = ''
                        data.file_name = ''
                        data.line_ids = []
                        return {'warning': {'title': 'Error!', 'message': message}}
                    result.append({'product_id': product_id.id,
                                   'product_qty': qty,
                                   'location_id': data.parent_location_id and data.parent_location_id.id or False,
                                  })
            data.line_ids = result



    @api.multi
    def import_data(self):
        """
        Upon clicking import button, a stock.inventory
        record is created and confirmed. This updates 
        the current inventory with values in csv file.
        """
        for data in self:
            if not bool(data.line_ids):
                raise UserError(_('No product lines added to import.'))
            res = {
                   'name': data.name,
                   'location_id': data.parent_location_id and data.parent_location_id.id,
                   'filter': 'partial',
                  }
            lines = []
            for line in data.line_ids:
                vals = {}
                vals.update({'product_id': line.product_id and line.product_id.id,
                             'location_id': line.location_id and line.location_id.id,
                             'product_qty': line.product_qty,
                           })
                lines.append((0, False, vals))
            res.update({'line_ids': lines})
            rec = self.env['stock.inventory'].create(res)
            rec.prepare_inventory()
            rec.action_done()



import_inventory()

class import_inventory_line(models.TransientModel):
    _name = "import.inventory.line"


    @api.model
    def _default_stock_location(self):
        try:
            return self._context.get('location_id', False)
        except:
            return False


    parent_id = fields.Many2one('import.inventory', string='Import Line')
    location_id = fields.Many2one('stock.location', required=True, default=_default_stock_location, string='Location')
    product_id = fields.Many2one('product.product', required=True, string='Product')
    product_qty = fields.Float(string='Quantity')



import_inventory_line()



