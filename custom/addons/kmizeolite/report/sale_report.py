# -*- coding: utf-8 -*-


from openerp import models, fields, api,_


class ReportSale(models.AbstractModel):
    _name = 'report.kmizeolite.print_report_sale'


    @api.model
    def update_price_per_ton(self, res):
        for row in res:
            if row.get('weight', False):
                weight_in_us_tons = round(row.get('weight')*0.0005, 1) # converts US pound weight to USton weight
                price_per_ton = weight_in_us_tons and round((row.get('untaxed_total')/weight_in_us_tons), 2)
                row.update({'weight': weight_in_us_tons, 'price_per_ton': price_per_ton})
            else:
                row.update({'price_per_ton': 0.00})
        return res



    @api.model
    def search_orders(self, domain):
        res = []
        orders = self.env['sale.order'].search(domain, order='partner_id')

        for order in orders:
            if res and res[-1].get('partner_id', False) == order.partner_id.id:
                current_untaxed_total = res[-1].get('untaxed_total', False)
                current_weight = res[-1].get('weight', False)
                res[-1].update({'untaxed_total': current_untaxed_total + order.amount_report, 'weight': current_weight + order.weight_report})
            else:
                vals = {'partner_id': order.partner_id.id, 'partner_name': order.partner_id.name, 'untaxed_total':order.amount_report, 'weight': order.weight_report}
                res.append(vals)
        res = self.update_price_per_ton(res)
        res = self.append_total(res)
        return res




    @api.model
    def _get_product_types(self, data, use_domain):

        granular = {'type':'Granular','sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        powder = {'type':'Powder', 'sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        service = {'type':'Freight/Service', 'sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        packaging = {'type':'Packaging', 'sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        samples = {'type':'Samples', 'sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        total_granular_powder = {'type':'Total Granular + Powder', 'sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        other = {'type':'other', 'sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        total_sales = {'type':'Total Sales (excluding freight)', 'sales_price':0.00, 'total_weight':0.00, 'average_price':0.00}
        domain = []
        if use_domain == 1:
            domain = [('state', 'in', ['sale', 'done']), ('invoice_status', 'in' , ['to invoice', 'invoiced']), ('effective_date', '>', data.get('from_date')), ('effective_date', '<', data.get('to_date'))]
        elif use_domain == 2:
            domain = [('state', '=', 'done'), ('invoice_status', '=' , 'invoiced'), ('effective_date', '>', data.get('from_date')), ('effective_date', '<', data.get('to_date'))]



        for order in self.env['sale.order'].search(domain):
            for line in order.order_line:

                if line.product_id and line.product_id.categ_id and line.product_id.categ_id.product_type == 'granular':
                    granular['sales_price'] = granular['sales_price'] + line.price_subtotal
                    granular['total_weight'] = granular['total_weight'] + (line.product_id.weight * line.product_uom_qty)

                elif line.product_id and line.product_id.categ_id and line.product_id.categ_id.product_type == 'powder':
                    powder['sales_price'] = powder['sales_price'] + line.price_subtotal
                    powder['total_weight'] = powder['total_weight'] + (line.product_id.weight * line.product_uom_qty)

                elif line.product_id and line.product_id.categ_id and line.product_id.categ_id.product_type == 'service':
                    service['sales_price'] = service['sales_price'] + line.price_subtotal

                elif line.product_id and line.product_id.categ_id and line.product_id.categ_id.product_type == 'package':
                    packaging['sales_price'] = packaging['sales_price'] + line.price_subtotal

                elif line.product_id and line.product_id.categ_id and line.product_id.categ_id.product_type == 'sample':
                    samples['sales_price'] = samples['sales_price'] + line.price_subtotal

                elif line.product_id and line.product_id.categ_id and line.product_id.categ_id.product_type == 'other':
                    other['sales_price'] = other['sales_price'] + line.price_subtotal

        granular['total_weight'] = round(granular['total_weight'] * 0.0005, 1) # converts US pound weight to USton weight
        powder['total_weight'] = round(powder['total_weight'] * 0.0005, 1) # converts US pound weight to USton weight
        granular['average_price'] = granular['total_weight'] and (granular['sales_price']/granular['total_weight'])
        powder['average_price'] = powder['total_weight'] and (powder['sales_price']/powder['total_weight'])
        total_granular_powder['total_weight'] = granular['total_weight'] + powder['total_weight']
        total_granular_powder['sales_price'] = granular['sales_price'] + powder['sales_price']
        total_granular_powder['average_price'] = total_granular_powder['total_weight'] and total_granular_powder['sales_price']/total_granular_powder['total_weight']

        total_sales['total_weight'] = granular['total_weight'] + powder['total_weight']
        total_sales['sales_price'] = granular['sales_price'] + powder['sales_price'] + packaging['sales_price'] + other['sales_price'] + samples['sales_price']
        total_sales['average_price'] = total_sales['total_weight'] and (granular['sales_price'] + powder['sales_price'])/total_sales['total_weight']


        return [granular, powder, service, packaging, samples, total_granular_powder, other, total_sales]




    def _get_orders(self, data):

        if self._context.get('type', False)=='lines_inv_com':
            domain = [('state', '=', 'done'), ('invoice_status', '=' , 'invoiced'), ('effective_date', '>', data.get('from_date')), ('effective_date', '<', data.get('to_date'))]
            res = self.search_orders(domain)

            return res

        if self._context.get('type', False)=='lines_inv_inc':
            domain = [('state', '=', 'sale'), ('invoice_status', '=' , 'invoiced'), ('effective_date', '>', data.get('from_date')), ('effective_date', '<', data.get('to_date'))]
            res = self.search_orders(domain)

            return res

        if self._context.get('type', False)=='lines_not_inv_com':
            domain = [('state', '=', 'done'), ('invoice_status', '=' , 'to invoice'), ('effective_date', '>', data.get('from_date')), ('effective_date', '<', data.get('to_date'))]
            res = self.search_orders(domain)

            return res

        if self._context.get('type', False)=='lines_not_inv_inc':
            domain = [('state', '=', 'sale'), ('invoice_status', '=' , 'to invoice'), ('effective_date', '>', data.get('from_date')), ('effective_date', '<', data.get('to_date'))]
            res = self.search_orders(domain)
            return res




    def append_total(self, res):
        total = {'total_price_per_ton': 0.00,
                 'total_untaxed_total': 0.00,
                 'total_weight': 0.00,
                }

        for row in res:
            total['total_price_per_ton'] += row['price_per_ton']
            total['total_untaxed_total'] += row['untaxed_total']
            total['total_weight'] += row['weight']
        total['total_price_per_ton'] = len(res) and round(total['total_price_per_ton']/len(res), 2)
        data = [res, total]
        return data








    @api.model
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': self._ids,
            'doc_model': self._model,
            'data': data,
            'docs': self.env['sale.order'],
            'lines_inv_com': self.with_context({'type':'lines_inv_com'})._get_orders(data),
            'lines_inv_inc': self.with_context({'type':'lines_inv_inc'})._get_orders(data),
            'lines_not_inv_com': self.with_context({'type':'lines_not_inv_com'})._get_orders(data),
            'lines_not_inv_inc': self.with_context({'type':'lines_not_inv_inc'})._get_orders(data),
            'lines_prod_types': self._get_product_types(data, 1),
            'lines_prod_types_shipped': self._get_product_types(data, 2),
        }



        return self.env['report'].render('kmizeolite.print_report_sale', docargs)
