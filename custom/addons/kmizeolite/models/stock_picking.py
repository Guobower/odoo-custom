# -*- coding: utf-8 -*-


from openerp import api, fields, models, _







class StockPicking(models.Model):
    _inherit = "stock.picking"


    pick_type = fields.Selection(string='Picking Type', related='picking_type_id.code', copy=False)



    @api.multi
    def action_freight_vendor_quotation_send(self):
        '''
        This function opens a window to compose an email for freight vendor,
        with the freight vendor template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference('kmizeolite', 'quote_email_template_freight_vendor_picking')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('kmizeolite', 'email_compose_freight_vendor_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update({
            'default_model': 'stock.picking',
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
        if self._context.get('vendor_quote', False):
            return {'partner': message.partner_ids, 'user': []}
        return super(StockPicking, self)._notification_group_recipients(message, recipients, done_ids, group_data)


    @api.multi
    def write(self, vals):
        """
            while sending quote to shipping vendor,
            restrict adding them as followers
        """
        self.ensure_one()

        if self._context.get('vendor_quote', False):
            vals.pop('message_follower_ids', False)
        res = super(StockPicking, self).write(vals)
        return res










StockPicking()
