# -*- coding: utf-8 -*-


from openerp import api, fields, models, _
import openerp.addons.decimal_precision as dp






class SaleOrder(models.Model):
    _inherit = "sale.order"

    weight_report = fields.Float(compute="_calc_weight_and_amount", string='Powder and Granular Weight')
    amount_report = fields.Float(compute="_calc_weight_and_amount", string='Powder and Granular Amount')

    weight_order = fields.Float(compute="_calc_weight", digits=dp.get_precision('Stock Weight'), string="Total Order Weight")
    state = fields.Selection([
            ('draft', 'Quotation'),
            ('sent', 'Quotation Sent'),
            ('sale', 'Incomplete'),
            ('done', 'Complete'),
            ('cancel', 'Cancelled'),
            ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    production_date = fields.Date(string="Production Date")
    requested_date = fields.Datetime(String='Requested Date', copy=False, readonly=False,
            help="Date by which the customer has requested the items to be "
                 "delivered.\n"
                 "When this Order gets confirmed, the Delivery Order's "
                 "expected date will be computed based on this date and the "
                 "Company's Security Delay.\n"
                 "Leave this field empty if you want the Delivery Order to be "
                 "processed as soon as possible. In that case the expected "
                 "date will be computed using the default method: based on "
                 "the Product Lead Times and the Company's Security Delay.")
    invoiced_date = fields.Date(compute="_get_invoiced_date", store=True, string="Invoiced Date")


    @api.depends('invoice_ids')
    def _get_invoiced_date(self):
        for order in self:
            if order.invoice_ids:
                valid_invoices = order.invoice_ids.filtered(lambda invoice:invoice.state not in ['draft', 'cancel',])
                if valid_invoices:
                    order.invoiced_date = valid_invoices and valid_invoices[0].date_invoice




    @api.depends('order_line', 'order_line.product_id')
    def _calc_weight_and_amount(self):
        for order in self:
            weight = 0.0
            amount = 0.0
            for line in order.order_line:
                if line.product_id and line.product_id.categ_id and line.product_id.categ_id.product_type in ['granular', 'powder']:
                    weight += line.product_id and line.product_id.weight * line.product_uom_qty
                    amount += line.product_id and line.price_subtotal
            order.weight_report = weight
            order.amount_report = amount


    @api.depends('order_line')
    def _calc_weight(self):
        for order in self:
            weight = 0.0
            for line in order.order_line:
                weight += line.product_id and line.product_id.weight * line.product_uom_qty
            order.weight_order = weight



    @api.multi
    def action_freight_vendor_quotation_send(self):
        '''
        This function opens a window to compose an email for freight vendor,
        with the freight vendor template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference('kmizeolite', 'quote_email_template_freight_vendor')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('kmizeolite', 'email_compose_freight_vendor_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update({
            'default_model': 'sale.order',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'vendor_quote': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def _notification_group_recipients(self, message, recipients, done_ids, group_data):
        """
        freight vendor email is sent to customer also while sent
        using mail.compose.message. overriden to not send to customer
        """
        if self._context.get('vendor_quote', False):
            return {'partner': message.partner_ids, 'user': []}
        return super(SaleOrder, self)._notification_group_recipients(message, recipients, done_ids, group_data)


    @api.multi
    def action_reset_done(self):
        self.write({'state': 'sale'})

    @api.multi
    def write(self, vals):
        """
            while sending quote to shipping vendor,
            restrict adding them as followers
        """
        freight_vendors = self.env['res.partner'].search([('is_freight_vendor', '=', True)])
        vendor_ids = [vendor.id for vendor in freight_vendors]
        updated_followers = []

        for follower in vals.get('message_follower_ids', []):
            if follower[2].get('partner_id', False) not in vendor_ids:
                updated_followers.append(follower)
        vals.update({'message_follower_ids': updated_followers})

        if self._context.get('vendor_quote', False):
            vals.pop('message_follower_ids', False)

        res = super(SaleOrder, self).write(vals)
        return res

    @api.v7
    def _cart_update(self, cr, uid, ids, product_id=None, line_id=None, add_qty=0, set_qty=0, context=None, **kwargs):
        """
        this method originally defined in website_sale
        used to add taxes on sale line based on zip code
        of customer delvery address.
        """
        res = super(SaleOrder, self)._cart_update(cr, uid, ids, product_id=product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, context=context, **kwargs)
        if res and res.get('quantity', 0):
            sale_line = self.pool.get('sale.order.line').browse(cr, uid, res.get('line_id', False), context=context)
            sale_line.set_delivery_taxes()
        return res





SaleOrder()

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    #Overrided to set product Tax based on Customer Zip Code
    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        res = super(SaleOrderLine, self).product_id_change()
        for sale_line in self:
            sale_line.set_delivery_taxes()
        return res


    @api.multi
    def set_delivery_taxes(self):
        """
        this method sets the taxes for sale lines based on city
        name or the zip codes of delivery address. Tax is applied
        based on city name or zip codes
        """
        tax = []
        if self.product_id:
            if self.order_id.partner_shipping_id and (self.order_id.partner_shipping_id.zip or self.order_id.partner_shipping_id.city):
                for taxes in self.env['account.tax'].search([('type_tax_use', '=', 'sale')]):

                    if taxes.zip_codes and taxes.zip_codes.split(','):
                        zip_codes = [code.strip() for code in taxes.zip_codes.split(',')]
                        if zip_codes and self.order_id.partner_shipping_id.zip and self.order_id.partner_shipping_id.zip.strip() in zip_codes:
                            tax.append(taxes.id)
                            break

                    if taxes.cities and taxes.cities.split(','):
                        cities = [code.strip().lower() for code in taxes.cities.split(',')]
                        if cities and self.order_id.partner_shipping_id.city and self.order_id.partner_shipping_id.city.strip().lower() in cities and (taxes not in tax) and self.order_id.partner_shipping_id.state_id and self.order_id.partner_shipping_id.state_id == taxes.state_id:
                            tax.append(taxes.id)
                            break
                if not tax:
                    for tax_id in self.product_id.taxes_id:
                        tax.append(tax_id.id)
            else:
                for tax_id in self.product_id.taxes_id:
                    tax.append(tax_id.id)
        self.tax_id = [[6, False, tax]]
        fpos = self.order_id.fiscal_position_id or self.order_id.partner_id.property_account_position_id
        # If company_id is set, always filter taxes by the company
        taxes = self.tax_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
        self.tax_id = fpos.map_tax(taxes, self.product_id, self.order_id.partner_id) if fpos else taxes






SaleOrderLine()









# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
