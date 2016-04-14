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
from trytond.report import Report

__all__ = ['WizardSalePayment', 'InvoiceReportPos']
__metaclass__ = PoolMeta

class WizardSalePayment:
    __name__ = 'sale.payment'
    print_ = StateAction('nodux_sale_payment.report_invoice_pos')
    
    def transition_pay_(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Sale = pool.get('sale.sale')
        Statement = pool.get('account.statement')
        StatementLine = pool.get('account.statement.line')
        form = self.start
        statements = Statement.search([
                ('journal', '=', form.journal),
                ('state', '=', 'draft'),
                ], order=[('date', 'DESC')])
        if not statements:
            self.raise_user_error('not_draft_statement', (form.journal.name,))

        active_id = Transaction().context.get('active_id', False)
        sale = Sale(active_id)
        
        if form.tipo_p == 'cheque':
            sale.tipo_p = form.tipo_p
            sale.banco = form.banco
            sale.numero_cuenta = form.numero_cuenta
            sale.fecha_deposito= form.fecha_deposito
            sale.titular = form.titular
            sale.numero_cheque = form.numero_cheque
            sale.save()
            
        if form.tipo_p == 'deposito':
            sale.tipo_p = form.tipo_p
            sale.banco_deposito = form.banco_deposito
            sale.numero_cuenta_deposito = form.numero_cuenta_deposito
            sale.fecha_deposito = form.fecha_deposito
            sale.numero_deposito= form.numero_deposito
         
        if form.tipo_p == 'tarjeta':
            sale.tipo_p = form.tipo_p
            sale.numero_tarjeta = form.numero_tarjeta
            sale.lote = form.lote
            sale.tipo_tarjeta = form.tipo_tarjeta
        
        if form.tipo_p == 'efectivo':
            sale.recibido = form.recibido
            sale.cambio = form.cambio_cliente
            
        if not sale.reference:
            Sale.set_reference([sale])

        account = (sale.party.account_receivable
            and sale.party.account_receivable.id
            or self.raise_user_error('party_without_account_receivable',
                error_args=(sale.party.name,)))

        if form.payment_amount:
            payment = StatementLine(
                statement=statements[0].id,
                date=Date.today(),
                amount=form.payment_amount,
                party=sale.party.id,
                account=account,
                description=sale.reference,
                sale=active_id
                )
            payment.save()
        if sale.acumulativo != True:
            sale.description = sale.reference
            sale.save()
            Sale.workflow_to_end([sale])
            Invoice = Pool().get('account.invoice')
            invoices = Invoice.search([('description','=',sale.reference)])
            for i in invoices:
                invoice= i
            invoice.get_invoice_element()
            invoice.get_tax_element()
            invoice.generate_xml_invoice()
            invoice.get_detail_element()
            invoice.action_generate_invoice()  
            invoice.connect_db()
        
            if sale.total_amount == sale.paid_amount:
                return 'print_'
                return 'end'
                
            if sale.total_amount != sale.paid_amount:
                return 'print_'
                return 'end'
                
            if sale.state != 'draft':
                return 'print_'
                return 'end'
        else:
            if sale.total_amount != sale.paid_amount:
                return 'start'
            if sale.state != 'draft':
                return 'end'
            sale.description = sale.reference
            sale.save()

            Sale.workflow_to_end([sale])
        
        return 'end'
        
class InvoiceReportPos(Report):
    __name__ = 'nodux_sale_payment.invoice_pos'
            
    @classmethod
    def parse(cls, report, records, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        sale = records[0]
        
        invoices = Invoice.search([('description', '=', sale.description)])
        if invoices:
            for i in invoices:
                invoice = i
                invoice_e = 'true'
        else:
            invoice_e = 'false'
            invoice = sale

        user = User(Transaction().user)
        localcontext['user'] = user
        localcontext['company'] = user.company
        localcontext['invoice'] = invoice
        localcontext['invoice_e'] = invoice_e
        localcontext['subtotal_0'] = cls._get_subtotal_0(Sale, sale)
        localcontext['subtotal_12'] = cls._get_subtotal_12(Sale, sale)
        localcontext['descuento'] = cls._get_descuento(Sale, sale)
        localcontext['barcode_img']=cls._get_barcode_img(Invoice, invoice)
        #localcontext['fecha_de_emision']=cls._get_fecha_de_emision(Invoice, invoice)
        return super(InvoiceReportPos, cls).parse(report, records, data,
                localcontext=localcontext)   

    @classmethod
    def _get_barcode_img(cls, Invoice, invoice):
        from barras import CodigoBarra
        from cStringIO import StringIO as StringIO
        # create the helper:
        codigobarra = CodigoBarra()
        output = StringIO()
        bars= invoice.numero_autorizacion
        codigobarra.GenerarImagen(bars, output, basewidth=3, width=380, height=50, extension="PNG")
        image = buffer(output.getvalue())
        output.close()
        return image
        
        
