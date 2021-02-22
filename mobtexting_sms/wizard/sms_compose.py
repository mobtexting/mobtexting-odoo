# -*- coding: utf-8 -*-
import base64
import re
import logging
from odoo.exceptions import except_orm, UserError, Warning
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.tools.translate import _
from odoo import tools
from odoo.tools.safe_eval import safe_eval as eval

_logger = logging.getLogger(__name__)

class SMSComposer(models.TransientModel):
    _name = 'mob_sms.compose'
    _description = 'SMS composition wizard'
    _log_access = True

    @api.onchange('template_id')
    def _get_body_text(self):
        self.body_text= self.template_id.sms_html
        self.sms_to_lead = self.template_id.sms_to
        self.gatewayurl_id = self.template_id.gateway_id
        active_ids = self.env.context.get('active_ids')
        for ids in active_ids:
            my_model = self._context['active_model']
            if (len(active_ids)) == 1:
                message = self.env['mob_send_sms'].render_template(self.body_text, my_model, ids)
                number = self.env['mob_send_sms'].render_template(self.sms_to_lead, my_model, ids)

            elif (len(active_ids) > 1):
                message = self.template_id.sms_html
                number = self.template_id.sms_to

            self.body_text = message
            self.sms_to_lead = number

    template_id = fields.Many2one('mob_send_sms', 'SMS Template')
    body_text = fields.Text('Body')
    sms_to_lead = fields.Char(string='To (Mobile)')
    gatewayurl_id = fields.Many2one('mob_gateway_setup','SMS Gateway')


    def send_sms_action(self):
        active_ids = self.env.context.get('active_ids')
        for ids in active_ids:
            my_model = self._context['active_model']
            message = self.env['mob_send_sms'].render_template(self.body_text, my_model, ids)
            mobile_no = self.env['mob_send_sms'].render_template(self.sms_to_lead, my_model, ids)
            self.env['mob_send_sms'].send_sms_link(message, mobile_no,ids,my_model,self.gatewayurl_id)
            # raise Warning(response)
        return True
