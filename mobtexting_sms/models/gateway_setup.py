from odoo import models, fields, api
from odoo.exceptions import except_orm, UserError, Warning,ValidationError
import requests
import urllib
import re
import json
from odoo import http
import datetime

import logging

_logger = logging.getLogger(__name__)

class GatewaySetup(models.Model):
    _name = "mob_gateway_setup"
    _description = "GateWay Setup"

    name = fields.Char(required=True, string='Name',readonly='true',default='MOBtexting')
    gateway_url = fields.Char(required=True, string='GateWay Url',readonly='true',
                              default='https://portal.mobtexting.com/api/v2/sms/send/')
    message = fields.Text('Message')
    mobile = fields.Char('Mobile')
    accesstoken = fields.Char(string="Access Token", required=True)
    service = fields.Selection(
        [('T', 'T'), ('P', 'P'), ('S', 'S'),
         ('G', 'G')], required=True, default="T")
    sender = fields.Char(string="Sender", required=True)
    active = fields.Boolean(string="Active", required=True)

    def send_sms_link(self,sms_rendered_content,rendered_sms_to,record_id,model,gateway_url_id):

        sms_rendered_content = sms_rendered_content
        sms_rendered_content_msg = urllib.parse.quote_plus(sms_rendered_content)

        rule =re.compile("(0/91)?[7-9][0-9]{9}")
        if not rule.search(rendered_sms_to):
            msg = u"Invalid number format."
            raise ValidationError(msg)

        if rendered_sms_to:
            rendered_sms_to = re.sub(r'\s+', '', rendered_sms_to)
            if '+' in rendered_sms_to:
                rendered_sms_to = rendered_sms_to.replace('+', '')

            if '-' in rendered_sms_to:
                rendered_sms_to = rendered_sms_to.replace('-', '')

        if rendered_sms_to:
            send_url = gateway_url_id.gateway_url
            para = {"access_token":self.accesstoken,
                    "service": self.service,
                    "sender": self.sender,
                    "message":sms_rendered_content_msg,
                    "to":rendered_sms_to}
            activecheck = self.active
            if activecheck == 1:
                try:
                    response = requests.post(url = send_url,params=para).text
                    resultRes = ""
                    checkval = ""
                    if "https://portal.mobtexting.com/login" in response:
                        response = "Access Token Invalid"
                        resultRes = response
                    else:
                        response = json.loads(response)
                        checkval = response['status']

                    if checkval == "ERROR":
                        response = response['message']
                        resultRes = response
                    if checkval == 200:
                        response = "Message Send"
                        resultRes = response



                    self.env['mob_sms_track'].sms_track_create(sms_rendered_content, rendered_sms_to, resultRes,
                                                                    model, gateway_url_id.id)

                    if model != 'mob_gateway_setup':
                        self.env['mail.message'].create({
                            'author_id': http.request.env.user.partner_id.id,
                            'date': datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                            'model': model,
                            'res_id': record_id,
                            'message_type': 'email',
                            'body': '<b>SMS: </b>' + sms_rendered_content,
                        })
                    return response
                except Exception as e:
                    return e
            else:
                return "Enable Active"

    def sms_test_action(self):
        active_model = 'mob_gateway_setup'
        message = self.message
        mobile_no = self.mobile
        self.send_sms_link(message, mobile_no, self.id, active_model, self)
        # raise Warning(response)
        return True
