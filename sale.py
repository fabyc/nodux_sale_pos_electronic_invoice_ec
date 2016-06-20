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

conversor = None
try:
    from numword import numword_es
    conversor = numword_es.NumWordES()
except:
    print("Warning: Does not possible import numword module!")
    print("Please install it...!")

__all__ = ['Sale', 'InvoiceReportPosE', 'WizardSalePayment']
__metaclass__ = PoolMeta


class Sale:
    __name__ ='sale.sale'
    motivo = fields.Char('Motivo de devolucion', states={
            'readonly': Eval('state') != 'draft',
    })

class WizardSalePayment:
    __name__ = 'sale.payment'
    print_ = StateAction('nodux_sale_pos_electronic_invoice_ec.report_invoice_pos_e')

    @classmethod
    def __setup__(cls):
        super(WizardSalePayment, cls).__setup__()
        
    def transition_pay_(self):
        print "Sale electronic ***"
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
            sale.description = sale.reference
            sale.save()

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
                return 'end'
            if (sale.total_amount == sale.paid_amount) | (sale.state != draft):
                Sale.workflow_to_end([sale])
                Invoice = Pool().get('account.invoice')
                invoices = Invoice.search([('description','=',sale.reference)])
                for i in invoices:
                    invoice= i
                print "**** ", invoice.get_invoice_element()

                invoice.get_tax_element()
                invoice.generate_xml_invoice()
                invoice.get_detail_element()
                invoice.action_generate_invoice()
                invoice.connect_db()
                sale.description = sale.reference
                sale.save()
                return 'end'
            """
            if sale.state != 'draft':
                return 'end'
            """
        return 'end'

class InvoiceReportPosE(Report):
    __name__ = 'nodux_sale_pos_electronic_invoice_ec.invoice_pos_e'

    @classmethod
    def parse(cls, report, records, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        sale = records[0]
        TermLines = pool.get('account.invoice.payment_term.line')
        invoices = Invoice.search([('description', '=', sale.reference), ('description', '!=', None)])
        motivo = 'Emitir factura con el mismo concepto'
        if sale.motivo:
            motivo = sale.motivo

        fecha = None
        numero = None
        cont = 0
        if invoices:
            for i in invoices:
                invoice = i
                invoice_e = 'true'
        else:
            invoice_e = 'false'
            invoice = sale

        if sale.tipo_p:
            tipo = (sale.tipo_p).upper()
        else:
            tipo = None
        if sale.payment_term:
            term = sale.payment_term
            termlines = TermLines.search([('payment', '=', term.id)])
            for t in termlines:
                t_f = t
                cont += 1

        if cont == 1 and t_f.days == 0:
            forma = 'CONTADO'
        else:
            forma = 'CREDITO'

        if sale.total_amount:
            d = str(sale.total_amount)
            decimales = d[-2:]
        else:
            decimales='0.0'

        user = User(Transaction().user)
        localcontext['user'] = user
        localcontext['company'] = user.company
        localcontext['invoice'] = invoice
        localcontext['invoice_e'] = invoice_e
        localcontext['subtotal_0'] = cls._get_subtotal_0(Sale, sale)
        localcontext['subtotal_12'] = cls._get_subtotal_12(Sale, sale)
        localcontext['subtotal_14'] = cls._get_subtotal_14(Sale, sale)
        localcontext['descuento'] = cls._get_descuento(Sale, sale)
        localcontext['forma'] = forma
        localcontext['tipo'] = tipo
        localcontext['numero'] = numero
        localcontext['fecha'] = fecha
        localcontext['motivo'] = motivo
        localcontext['amount2words']=cls._get_amount_to_pay_words(Sale, sale)
        localcontext['decimales'] = decimales
        localcontext['lineas'] = cls._get_lineas(Sale, sale)
        if invoice_e == 'true':
            localcontext['barcode_img']=cls._get_barcode_img(Invoice, invoice)
        else:
            localcontext['barcode_img']= None
        #localcontext['fecha_de_emision']=cls._get_fecha_de_emision(Invoice, invoice)
        return super(InvoiceReportPosE, cls).parse(report, records, data,
                localcontext=localcontext)
    @classmethod
    def _get_amount_to_pay_words(cls, Sale, sale):
        amount_to_pay_words = Decimal(0.0)
        if sale.total_amount and conversor:
            amount_to_pay_words = sale.get_amount2words(sale.total_amount)
        return amount_to_pay_words

    @classmethod
    def _get_lineas(cls, Sale, sale):
        cont = 0

        for line in sale.lines:
            cont += 1
        return cont

    @classmethod
    def _get_descuento(cls, Sale, sale):
        descuento = Decimal(0.00)
        descuento_parcial = Decimal(0.00)

        for line in sale.lines:
            descuento_parcial = Decimal(line.product.template.list_price - line.unit_price)
            if descuento_parcial > 0:
                descuento = descuento + descuento_parcial
            else:
                descuento = Decimal(0.00)
        return descuento

    @classmethod
    def _get_subtotal_12(cls, Sale, sale):
        subtotal12 = Decimal(0.00)
        pool = Pool()

        for line in sale.lines:
            if  line.taxes:
                for t in line.taxes:
                    if str('{:.0f}'.format(t.rate*100)) == '12':
                        subtotal12= subtotal12 + (line.amount)
        if subtotal12 < 0:
            subtotal12 = subtotal12*(-1)
        return subtotal12

    @classmethod
    def _get_subtotal_14(cls, Sale, sale):
        subtotal14 = Decimal(0.00)
        pool = Pool()

        for line in sale.lines:
            if  line.taxes:
                for t in line.taxes:
                    if str('{:.0f}'.format(t.rate*100)) == '14':
                        subtotal14= subtotal14 + (line.amount)
        if subtotal14 < 0:
            subtotal14 = subtotal14*(-1)
        return subtotal14

    @classmethod
    def _get_subtotal_0(cls, Sale, sale):
        subtotal0 = Decimal(0.00)
        pool = Pool()

        for line in sale.lines:
            if  line.taxes:
                for t in line.taxes:
                    if str('{:.0f}'.format(t.rate*100)) == '0':
                        subtotal0= subtotal0 + (line.amount)
        if subtotal0 < 0:
            subtotal0 = subtotal0*(-1)
        return subtotal0

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
