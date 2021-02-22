import logging
from odoo import http
from odoo.exceptions import except_orm, UserError, Warning
from odoo.http import request, serialize_exception as _serialize_exception, content_disposition
from odoo import api, fields, models, tools, _
import datetime
from urllib.parse import urlencode, quote as quote
import urllib.parse
import requests
import re
import json
from functools import reduce

_logger = logging.getLogger(__name__)
try:
    from jinja2.sandbox import SandboxedEnvironment
    mako_template_env = SandboxedEnvironment(
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="${",
        variable_end_string="}",
        comment_start_string="<%doc>",
        comment_end_string="</%doc>",
        line_statement_prefix="%",
        line_comment_prefix="##",
        trim_blocks=True,               # do not output newline after blocks
        autoescape=True,                # XML/HTML automatic escaping
    )
    mako_template_env.globals.update({
        'str': str,
        'quote': quote,
        'urlencode': urlencode,
        'datetime': datetime,
        'len': len,
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'filter': filter,
        'reduce': reduce,
        'map': map,
        'round': round,

        'relativedelta': lambda *a, **kw : relativedelta.relativedelta(*a, **kw),
    })
except ImportError:
    _logger.warning("jinja2 not available, templating features will not work!")
class SendSMS(models.Model):
    _name = "mob_send_sms"
    _description = "Send SMS"

    name = fields.Char(required=True, string='Template Name')
    gateway_id = fields.Many2one('mob_gateway_setup',required=True,string='SMS Gateway')
    model_id = fields.Many2one('ir.model', string='Applies to', help="The kind of document with with this template can be used")
    sms_to = fields.Char(string='To (Phone)', help="To mobile number (placeholders may be used here)")
    sms_html = fields.Text('Body')
    ref_ir_act_window = fields.Many2one('ir.actions.act_window', 'Sidebar action', readonly=True, copy=False,help="Sidebar action to make this template available on records " "of the related document model")

    def send_sms(self, template_id, record_id):
        sms_rendered_content = self.env['mob_send_sms'].render_template(template_id.sms_html, template_id.model_id.model, record_id)
        rendered_sms_to = self.env['mob_send_sms'].render_template(template_id.sms_to, template_id.model_id.model, record_id)
        self.send_sms_link(sms_rendered_content,rendered_sms_to,record_id,template_id.model_id.model,template_id.gateway_id)

    def send_sms_link(self,sms_rendered_content,rendered_sms_to,record_id,model,gateway_url_id):
        sms_rendered_content = sms_rendered_content
        sms_rendered_content_msg = urllib.parse.quote_plus(sms_rendered_content)
       
        if rendered_sms_to:
            rendered_sms_to = re.sub(r'\s+', '', rendered_sms_to)
            if '+' in rendered_sms_to:
                rendered_sms_to = rendered_sms_to.replace('+', '')

            if '-' in rendered_sms_to:
                rendered_sms_to = rendered_sms_to.replace('-', '')

            if '(' in rendered_sms_to:
                rendered_sms_to = rendered_sms_to.replace('(', '')

            if ')' in rendered_sms_to:
                rendered_sms_to = rendered_sms_to.replace(')', '')

        
        if rendered_sms_to:
            send_url = gateway_url_id.gateway_url
            para = {"access_token": gateway_url_id.accesstoken,
                    "service": gateway_url_id.service,
                    "sender": gateway_url_id.sender,
                    "message": sms_rendered_content_msg,
                    "to": rendered_sms_to}
            activecheck = gateway_url_id.active
            if activecheck == 1:
                try:
                    response = requests.post(url=send_url, params=para).text
                    resultRes = ""
                    checkval = ""
                    if "https://portal.mobtexting.com/login" in response:
                        response = "Access Token Invalid"
                        resultRes = response
                    else:
                        response = json.loads(response)
                        checkval = response['status']

                    if checkval == "ERROR":
                        response  = response['message']
                        resultRes = response

                    if checkval == 200:
                        response  = "Message Send"
                        resultRes = response
                    result = self.env['mob_sms_track'].sms_track_create(sms_rendered_content, rendered_sms_to,
                                                                    resultRes,
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

    def render_template(self, template, model, res_id):
        """Render the given template text, replace mako expressions ``${expr}``
           with the result of evaluating these expressions with
           an evaluation context containing:

                * ``user``: browse_record of the current user
                * ``object``: browse_record of the document record this sms is
                              related to
                * ``context``: the context passed to the sms composition wizard

           :param str template: the template text to render
           :param str model: model name of the document record this sms is related to.
           :param int res_id: id of document records those sms are related to.
        """
        template = mako_template_env.from_string(tools.ustr(template))
        user = self.env.user
        record = self.env[model].browse(res_id)

        variables = {
            'user': user
        }
        variables['object'] = record
        try:
            render_result = template.render(variables)
        except Exception:
            _logger.error("Failed to render template %r using values %r" % (template, variables))
            render_result = u""
        if render_result == u"False":
            render_result = u""

        return render_result

    def create_action(self):
        action_obj = self.env['ir.actions.act_window']
        data_obj = self.env['ir.model.data']
        view = self.env.ref('mobtexting_sms.sms_compose_wizard_form')
        src_obj = self.model_id.model
        button_name = _('SMS Send (%s)') % self.name
        action = action_obj.create({
            'name': button_name,
            'type': 'ir.actions.act_window',
            'res_model': 'mob_sms.compose',
            'context': "{'default_template_id' : %d, 'default_use_template': True}" % (self.id),
            'view_mode': 'tree,form',
            'view_id': view.id,
            'target': 'new',
            'binding_model_id': self.model_id.id,
        })

        self.write({
            'ref_ir_act_window': action.id,
        })
        return True

    def unlink_action(self):
        for template in self:
            if template.ref_ir_act_window:
                template.ref_ir_act_window.sudo().unlink()

        return True
