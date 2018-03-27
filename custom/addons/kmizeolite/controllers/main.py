# -*- encoding: utf-8 -*-

import openerp
import openerp.http as http
import base64
import openerp
from openerp.http import request


class GetCompanyimageController(http.Controller):

    @http.route('/odoo/get_company_logo', type='http', auth='public')
    def get_logo(self, company_id):
        env = request.env(user=request.uid)
        image_data = env['res.company'].sudo().browse(int(company_id)).logo

#        image_data = openerp.tools.image_resize_image(base64_source=image_data, size=(240, 80), encoding='base64', filetype='PNG')
        image_data = base64.b64decode(image_data)
        return request.make_response(image_data, [
            ('Content-Type', 'image/png'),
            ('Content-Length', len(image_data)),
        ])


GetCompanyimageController()

