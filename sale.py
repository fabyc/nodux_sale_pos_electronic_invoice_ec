# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from datetime import datetime
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval, Or
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)
from trytond.modules.company import CompanyReport

__all__ = ['WizardSalePayment']
__metaclass__ = PoolMeta

class WizardSalePayment:
    __name__ = 'sale.payment'
    print_ = StateAction('sale_pos.report_sale_ticket')
    
    def transition_pay_(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        active_id = Transaction().context.get('active_id', False)
        sale = Sale(active_id)
        result = super(WizardSalePayment, self).transition_pay_()
        Invoices = pool.get('account.invoice')
        invoices = Invoices.search([('description','=',sale.reference)])
        for i in invoices:
            invoice= i
        invoice.get_invoice_element()
        invoice.get_tax_element()
        invoice.generate_xml_invoice()
        invoice.get_detail_element()
        invoice.action_generate_invoice()  
        invoice.connect_db()
        
        
        Sale.print_ticket([sale])
        if result == 'end':
            return 'print_'
        return result
        
    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data
