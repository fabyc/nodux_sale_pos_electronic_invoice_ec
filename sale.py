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

__all__ = ['Sale', 'SalePaymentForm','InvoiceReportPosE', 'WizardSalePayment']
__metaclass__ = PoolMeta


class Sale:
    __name__ ='sale.sale'
    motivo = fields.Char('Motivo de devolucion', states={
            'readonly': Eval('state') != 'draft',
            })

    fisic_invoice = fields.Boolean('Fisic Invoice', states={
            'readonly' : Eval('state')!= 'draft',
            })

    number_invoice = fields.Char('Number Fisic Invoice', states={
            'readonly' : Eval('state')!= 'draft',
            'invisible' : ~Eval('fisic_invoice', True),
            'required' :  Eval('fisic_invoice', True),
            })

    formas_pago_sri = fields.Many2One('account.formas_pago', 'Formas de Pago SRI')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()

    @staticmethod
    def default_number_invoice():
        return '001-001-000000000'

class SalePaymentForm():
    __name__ = 'sale.payment.form'

    tipo_pago_sri = fields.Many2One('account.formas_pago', 'Formas de Pago SRI')

    @classmethod
    def __setup__(cls):
        super(SalePaymentForm, cls).__setup__()


    @fields.depends('journal', 'party', 'tipo_p', 'tipo_pago_sri', 'credito')
    def on_change_journal(self):
        if self.journal:
            result = {}
            pool = Pool()
            Statement=pool.get('account.statement')
            statement = Statement.search([('journal', '=', self.journal.id)])
            Pago = pool.get('account.formas_pago')
            pagos_e = None
            pagos_ch = None
            pagos_t = None
            pagos_n = None
            pago_e = None
            pago_ch = None
            pago_t = None
            pago_n = None
            pagos_e = Pago.search([('code', '=', '01')])
            pagos_ch = Pago.search([('code', '=', '20')])
            pagos_t = Pago.search([('code', '=', '19')])
            pagos_n = Pago.search([('name', '=', 'NINGUNA')])

            if pagos_e:
                for p in pagos_e:
                    pago_e = p
            if pagos_ch:
                for p_ch in pagos_ch:
                    pago_ch = p_ch
            if pagos_t:
                for p_t in pagos_t:
                    pago_t = p_t
            if pagos_n:
                for p_n in pagos_n:
                    pago_n = p_n

            if statement:
                for s in statement:
                    result['tipo_p'] = s.tipo_pago
                    tipo_p = s.tipo_pago
                if tipo_p :
                    pass
                else:
                    self.raise_user_error('No ha configurado el tipo de pago. \n-Seleccione el estado de cuenta en "Todos los estados de cuenta" \n-Seleccione forma de pago.')
            else:
                 self.raise_user_error('No ha creado el estado de cuenta para el punto de venta')

            if tipo_p == 'cheque':
                titular = self.party.name
                result['titular'] = titular
                if pago_ch:
                    result['tipo_pago_sri'] = pago_ch.id

            if tipo_p == 'efectivo':
                if pago_e:
                    result['tipo_pago_sri'] = pago_e.id

            if tipo_p == 'tarjeta':
                if pago_t:
                    result['tipo_pago_sri'] = pago_t.id

            if self.credito == True:
                if pago_n:
                    result['tipo_pago_sri'] = pago_n.id

        return result


class WizardSalePayment:
    __name__ = 'sale.payment'
    print_ = StateAction('nodux_sale_pos_electronic_invoice_ec.report_invoice_pos_e')

    @classmethod
    def __setup__(cls):
        super(WizardSalePayment, cls).__setup__()

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
        if sale.self_pick_up == False:
            sale.create_shipment('out')
            sale.set_shipment_state()
        date = Pool().get('ir.date')
        date = date.today()
        if form.payment_amount == 0 and form.party.vat_number == '9999999999999':
            self.raise_user_error('No se puede dar credito a consumidor final, monto a pagar no puede ser %s', form.payment_amount)

        if sale.total_amount > 200 and form.party.vat_number == '9999999999999':
            self.raise_user_error('La factura supera los $200 de importe total, por cuanto no puede ser emitida a nombre de CONSUMIDOR FINAL')

        if form.credito == True and form.payment_amount == sale.total_amount:
            self.raise_user_error('No puede pagar el monto total %s en una venta a credito', form.payment_amount)

        if form.credito == False and form.payment_amount < sale.total_amount:
            self.raise_user_warning('not_credit%s' % sale.id,
                   u'Esta seguro que desea abonar $%s '
                'del valor total $%s, de la venta al CONTADO.', (form.payment_amount, sale.total_amount))

        if form.payment_amount == 0 and form.party.vat_number == '9999999999999':
            self.raise_user_error('No se puede dar credito a consumidor final, monto a pagar no puede ser %s', form.payment_amount)

        if form.tipo_p == 'cheque':
            sale.tipo_p = form.tipo_p
            sale.banco = form.banco
            sale.numero_cuenta = form.numero_cuenta
            sale.fecha_deposito= form.fecha_deposito
            sale.titular = form.titular
            sale.numero_cheque = form.numero_cheque
            sale.sale_date = date
            sale.save()

        if form.tipo_p == 'deposito':
            sale.tipo_p = form.tipo_p
            sale.banco_deposito = form.banco_deposito
            sale.numero_cuenta_deposito = form.numero_cuenta_deposito
            sale.fecha_deposito = form.fecha_deposito
            sale.numero_deposito= form.numero_deposito
            sale.sale_date = date
            sale.save()

        if form.tipo_p == 'tarjeta':
            sale.tipo_p = form.tipo_p
            sale.numero_tarjeta = form.numero_tarjeta
            sale.lote = form.lote
            sale.tarjeta = form.tarjeta
            sale.sale_date = date
            sale.save()

        if form.tipo_p == 'efectivo':
            sale.tipo_p = form.tipo_p
            sale.recibido = form.recibido
            sale.cambio = form.cambio_cliente
            sale.sale_date = date
            sale.save()

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
            sale.formas_pago_sri = form.tipo_pago_sri
            sale.save()
            Sale.workflow_to_end([sale])
            Invoice = Pool().get('account.invoice')
            invoices = Invoice.search([('description','=',sale.reference)])
            lote = False

            if sale.shop.lote != None:
                lote = sale.shop.lote

            if invoices:
                for i in invoices:
                    invoice = i
                invoice.formas_pago_sri = form.tipo_pago_sri
                invoice.save()
                if sale.comment:
                    invoice.comment = sale.comment
                    invoice.save()

            if sale.fisic_invoice == True :
                invoice.number = sale.number_invoice
                invoice.fisic_invoice = True
                invoice.save()
            else:
                if lote == False:
                    invoice.get_invoice_element()
                    invoice.get_tax_element()
                    invoice.generate_xml_invoice()
                    invoice.get_detail_element()
                    invoice.action_generate_invoice()
                    invoice.connect_db()
            sale.description = sale.reference
            sale.save()

            if sale.total_amount == sale.paid_amount:
                #return 'print_'
                return 'end'

            if sale.total_amount != sale.paid_amount:
                #return 'print_'
                return 'end'

            if sale.state != 'draft':
                #return 'print_'
                return 'end'
        else:
            if sale.total_amount != sale.paid_amount:
                return 'end'
            if (sale.total_amount == sale.paid_amount) | (sale.state != draft):
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
                return 'end'

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
        if (sale.state == 'quotation') | (sale.state == 'draft'):
            pass
        else:
            localcontext['maturity_date'] = cls._get_maturity_date(Invoice, invoice)

        if invoice_e == 'true':
            if invoice.numero_autorizacion:
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
        codigobarra = CodigoBarra()
        output = StringIO()
        bars= invoice.numero_autorizacion
        codigobarra.GenerarImagen(bars, output, basewidth=3, width=380, height=50, extension="PNG")
        image = buffer(output.getvalue())
        output.close()
        return image

    @classmethod
    def _get_maturity_date(cls, Invoice, invoice):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')
        PaymentLine = pool.get('account.voucher.line.paymode')
        Date = pool.get('ir.date')
        id_i = None
        date = Date.today()

        move = invoice.move
        lines = MoveLine.search([('move', '=', move), ('party', '!=', None), ('maturity_date', '!=', None)])
        if lines:
            for l in lines:
                date = l.maturity_date
        return date
