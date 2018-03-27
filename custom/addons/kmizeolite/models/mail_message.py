# -*- coding: utf-8 -*-


from openerp import api, fields, models, _







class Message(models.Model):
    _inherit = "mail.message"


    @api.model
    def _get_reply_to(self, values):
        """
        set reply_to address as the sender email instead
        of the default system param values 'catchall@kmizeolite.com'
        """
        model, res_id, email_from = values.get('model', self._context.get('default_model')), values.get('res_id', self._context.get('default_res_id')), values.get('email_from')
        if model not in ['sale.order', 'stock.picking', 'account.invoice', 'purchase.order']:
            return super(Message, self)._get_reply_to(values)
        return email_from


    @api.multi
    def write(self, values):
        """
        while sending freight vendor emails , remove
        customers from the needaction_partner list.
        """
        if values.get('needaction_partner_ids', False):
            ven_list = []
            freight_vendors = self.env['res.partner'].search([('is_freight_vendor', '=', True)])

            for vendor in freight_vendors.ids:
                if vendor in self.mapped('partner_ids').ids:
                    ven_list.append(vendor)
            if ven_list:
                values.update({'needaction_partner_ids': [(6, 0, ven_list)]})
        res = super(Message, self).write(values)

        return res



    @api.model
    def create(self, values):
        """
        if the incoming mail server fetched emails
        belong to the freight vendor, do not proceed
        with sending them as emails to partners.
        """
        substring = 'Please provide a freight quote for order'
        freight_vendors = self.env['res.partner'].search([('is_freight_vendor', '=', True)])
        vendor_ids = [vendor.id for vendor in freight_vendors]
        if (values.get('subject', False) and substring in values.get('subject', '')) or (values.get('author_id', False) in vendor_ids):
            values.update({'message_type':'comment'})
            note_subtype = self.env.ref('mail.mt_note')
            values.update({'subtype_id': note_subtype.id})
        message = super(Message, self).create(values)
        return message



Message()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
