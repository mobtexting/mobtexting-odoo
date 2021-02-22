# -*- coding: utf-8 -*-
from odoo import api, fields, models

class IrActionsServer(models.Model):

    _inherit = 'ir.actions.server'

    sms_template_id = fields.Many2one('mob_send_sms',string="SMS Template")

    def _get_states(self):
        res = super(IrActionsServer, self)._get_states()
        res.insert(0, ('sms', 'Send SMS'))
        return res

    def run_action_sms(self, action, eval_context=None):
        if not action.sms_template_id:
            return False
        self.env['mob_send_sms'].send_sms(action.sms_template_id, self.env.context.get('active_id'))
        return False
