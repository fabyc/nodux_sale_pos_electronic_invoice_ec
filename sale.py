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

    referencia_de_factura = fields.Char('Referencia de factura-devolucion')

    devolucion = fields.Boolean('Devolucion')

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


    @fields.depends('journal', 'party', 'tipo_p', 'tipo_pago_sri', 'credito', 'amount')
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

            pago_e = None
            pago_ch = None
            pago_t = None

            pagos_e = Pago.search([('code', '=', '01')])
            pagos_ch = Pago.search([('code', '=', '20')])
            pagos_t = Pago.search([('code', '=', '19')])

            if pagos_e:
                for p in pagos_e:
                    pago_e = p
            if pagos_ch:
                for p_ch in pagos_ch:
                    pago_ch = p_ch
            if pagos_t:
                for p_t in pagos_t:
                    pago_t = p_t

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

            if self.credito == True and self.amount >=1000:
                if pago_ch:
                    result['tipo_pago_sri'] = pago_ch.id

            if self.credito == True and self.amount < 1000:
                if pago_e:
                    result['tipo_pago_sri'] = pago_e.id
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
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')
        InvoiceAccountMoveLine = pool.get('account.invoice-account.move.line')
        Journal = pool.get('account.journal')
        ModuleAdvanced = pool.get('ir.module.module')
        modulesA = ModuleAdvanced.search([('name', '=', 'nodux_sale_payment_advanced_payment'), ('state', '=', 'installed')])

        move_lines = []
        line_move_ids = []

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

        if modulesA:
            if form.restante > Decimal(0.0) and form.devolver_restante == True:
                self.raise_user_warning('devolucion%s' % sale.id,
                       u'Esta seguro que desea devolver $%s '
                    'en efectivo.', (form.restante))

            if form.restante > Decimal(0.0) and form.devolver_restante == False:
                self.raise_user_warning('anticipo%s' % sale.id,
                       u'Esta seguro que desea dejar $%s '
                    'como anticipo del Cliente %s.', (form.restante, sale.party.name))


        if form.tipo_p == 'cheque':
            sale.tipo_p = form.tipo_p
            sale.bancos = form.bancos
            sale.numero_cuenta = form.numero_cuenta
            sale.fecha_deposito= form.fecha_deposito
            sale.titular = form.titular
            sale.numero_cheque = form.numero_cheque
            #se cambia para Pruebas de TONERS, para que acepte fecha anterior
            #sale.sale_date = date
            move, = Move.create([{
                'period': Period.find(sale.company.id, date=sale.sale_date),
                'journal': 1,
                'date': sale.sale_date,
                'origin': str(sale),
                'description': str(sale.id),
            }])

            postdated_lines = None
            Configuration = pool.get('account.configuration')
            if Configuration(1).default_account_check:
                account_check = Configuration(1).default_account_check
            else:
                self.raise_user_error('No ha configurado la cuenta por defecto para Cheques. \nDirijase a Financiero-Configuracion-Configuracion Contable')

            move_lines.append({
                'description' : str(sale.id),
                'debit': form.payment_amount,
                'credit': Decimal(0.0),
                'account': account_check,
                'move': move.id,
                'journal': 1,
                'period': Period.find(sale.company.id, date=sale.sale_date),
            })
            move_lines.append({
                'description': str(sale.id),
                'debit': Decimal(0.0),
                'credit': form.payment_amount,
                'account': sale.party.account_receivable.id,
                'move': move.id,
                'journal': 1,
                'period': Period.find(sale.company.id, date=sale.sale_date),
                'date': sale.sale_date,
                'party': sale.party.id,
            })
            self.create_move(move_lines, move)
            postdated_lines = []
            if form.bancos:
                pass
            else:
                self.raise_user_error('Ingrese el banco')

            if form.numero_cheque:
                pass
            else:
                self.raise_user_error('Ingrese el numero de cheque')

            if form.numero_cuenta:
                pass
            else:
                self.raise_user_error('Ingrese el numero de cuenta')

            postdated_lines.append({
                'reference': str(sale.id),
                'name': str(sale.id),
                'amount': Decimal(form.payment_amount),
                'account': account_check,
                'date_expire': sale.sale_date,
                'date': sale.sale_date,
                'num_check' : form.numero_cheque,
                'num_account' : form.numero_cuenta,
            })

            if postdated_lines != None:
                Postdated = pool.get('account.postdated')
                postdated = Postdated()
                for line in postdated_lines:
                    date = line['date']
                    postdated.postdated_type = 'check'
                    postdated.reference = str(sale.id)
                    postdated.party = sale.party
                    postdated.post_check_type = 'receipt'
                    postdated.journal = 1
                    postdated.lines = postdated_lines
                    postdated.state = 'draft'
                    postdated.date = sale.sale_date
                    postdated.save()
            #sale.sale_date = date
            sale.save()

        if form.tipo_p == 'deposito':
            sale.tipo_p = form.tipo_p
            sale.banco_deposito = form.banco_deposito
            sale.numero_cuenta_deposito = form.numero_cuenta_deposito
            sale.fecha_deposito = form.fecha_deposito
            sale.numero_deposito= form.numero_deposito
            #sale.sale_date = date
            sale.save()

        if form.tipo_p == 'tarjeta':
            sale.tipo_p = form.tipo_p
            sale.numero_tarjeta = form.numero_tarjeta
            sale.lote = form.lote
            sale.tarjeta = form.tarjeta
            #sale.sale_date = date
            move, = Move.create([{
                'period': Period.find(sale.company.id, date=sale.sale_date),
                'journal': 1,
                'date': sale.sale_date,
                'origin': str(sale),
                'description': str(sale.id),
            }])
            Configuration = pool.get('account.configuration')
            if Configuration(1).default_account_card:
                account_card = Configuration(1).default_account_card
            else:
                self.raise_user_error('No ha configurado la cuenta por defecto para Tarjetas. \nDirijase a Financiero-Configuracion-Configuracion Contable')

            move_lines.append({
                'description' : str(sale.id),
                'debit': form.payment_amount,
                'credit': Decimal(0.0),
                'account': account_card,
                'move': move.id,
                'journal': 1,
                'period': Period.find(sale.company.id, date=sale.sale_date),
            })
            move_lines.append({
                'description': str(sale.id),
                'debit': Decimal(0.0),
                'credit': form.payment_amount,
                'account': sale.party.account_receivable.id,
                'move': move.id,
                'journal': 1,
                'period': Period.find(sale.company.id, date=sale.sale_date),
                'date': sale.sale_date,
                'party': sale.party.id,
            })
            self.create_move(move_lines, move)
            postdated_lines = []
            if form.numero_tarjeta:
                pass
            else:
                self.raise_user_error('Ingrese el numero de Tarjeta')

            if form.tarjeta:
                pass
            else:
                self.raise_user_error('Ingrese la Tarjeta')

            if form.lote:
                pass
            else:
                self.raise_user_error('Ingrese el no. de lote de la tarjeta')

            postdated_lines.append({
                'reference': str(sale.id),
                'name': str(sale.id),
                'amount': Decimal(form.payment_amount),
                'account': account_card,
                'date_expire': sale.sale_date,
                'date': sale.sale_date,
                'num_check' : form.numero_tarjeta,
                'num_account' : form.lote,
            })

            if postdated_lines != None:
                Postdated = pool.get('account.postdated')
                postdated = Postdated()
                for line in postdated_lines:
                    date = line['date']
                    postdated.postdated_type = 'card'
                    postdated.reference = str(sale.id)
                    postdated.party = sale.party
                    postdated.post_check_type = 'receipt'
                    postdated.journal = 1
                    postdated.lines = postdated_lines
                    postdated.state = 'draft'
                    postdated.date = sale.sale_date
                    postdated.save()
            sale.save()

        if form.tipo_p == 'efectivo':
            sale.tipo_p = form.tipo_p
            sale.recibido = form.recibido
            sale.cambio = form.cambio_cliente
            #sale.sale_date = date
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
                #se cambia para Pruebas de TONERS, para que acepte fecha anterior
                #date=Date.today(),
                date=sale.sale_date,
                amount=form.payment_amount,
                party=sale.party.id,
                account=account,
                description=sale.reference,
                sale=active_id
                )
            payment.save()

        if sale.acumulativo != True:
            if sale.total_amount < Decimal(0.0):
                move_lines_dev= []
                line_move__dev_ids = []
                reconcile_lines_dev_advanced = []

                journal_r = Journal.search([('type', '=', 'revenue')])
                for j in journal_r:
                    journal_sale = j.id

                move_dev, = Move.create([{
                    'period': Period.find(sale.company.id, date=sale.sale_date),
                    'journal': journal_sale,
                    'date': sale.sale_date,
                    'origin': str(sale),
                    'description': 'ajustes '+ str(sale.description),
                }])

                move_lines_dev.append({
                    'description': 'ajustes '+ str(sale.description),
                    'debit': Decimal(0.0),
                    'credit': sale.total_amount * (-1),
                    'account': sale.party.account_receivable.id,
                    'move': move_dev.id,
                    'party': sale.party.id,
                    'journal': journal_sale,
                    'period': Period.find(sale.company.id, date=sale.sale_date),
                })

                move_lines_dev.append({
                    'description':  'ajustes '+ str(sale.description),
                    'debit': sale.total_amount * (-1),
                    'credit': Decimal(0.0),
                    'account': sale.party.account_receivable.id,
                    'move': move_dev.id,
                    'party': sale.party.id,
                    'journal': journal_sale,
                    'period': Period.find(sale.company.id, date=sale.sale_date),
                })

                created_lines_dev = MoveLine.create(move_lines_dev)
                Move.post([move_dev])

                sale.devolucion = True
                sales_d = Sale.search([('description', '=', sale.description)])
                for sale_d in sales_d:
                    sale_d.devolucion = True
                    sale_d.referencia_de_factura = sale.description
                    sale_d.save()

            pago_en_cero = False
            utiliza_anticipo_venta = False
            sale.formas_pago_sri = form.tipo_pago_sri
            sale.save()
            Sale.workflow_to_end([sale])
            Invoice = Pool().get('account.invoice')
            invoices = Invoice.search([('description','=',sale.reference)])
            lote = False
            modules = None
            Module = pool.get('ir.module.module')
            modules = Module.search([('name', '=', 'nodux_sale_payment_advanced_payment'), ('state', '=', 'installed')])

            if modules:
                move_invoice = None
                for i in invoices:
                    move_invoice = i.move
                    invoice_advanced = i
                #agregado para asientos de anticipos
                Period = pool.get('account.period')
                Move = pool.get('account.move')
                Invoice = pool.get('account.invoice')
                MoveLine = pool.get('account.move.line')
                InvoiceAccountMoveLine = pool.get('account.invoice-account.move.line')
                amount_a = Decimal(0.0)
                account_types = ['receivable', 'payable']
                """
                move_lines = MoveLine.search([
                    ('party', '=', sale.party),
                    ('account.kind', 'in', account_types),
                    ('state', '=', 'valid'),
                    ('reconciliation', '=', None),
                    ('maturity_date', '=', None),
                ])

                for line in move_lines:
                    lineas_anticipo_conciliar = (form.lineas_anticipo.replace("[", "").replace("]","").replace("'", "").replace("'", "")).split(",")
                    for l in lineas_anticipo_conciliar:
                        if str(line.id) == l:
                            description = sale.reference
                            new_advanced = form.anticipo-form.restante
                            line.credit = Decimal(new_advanced)
                            line.save()
                            move = line.move
                            move.description = description
                            for m in move.lines:
                                if m.debit > Decimal(0.0):
                                    m.debit = Decimal(new_advanced)
                                    m.save()
                            move.save()
                """
                Configuration = pool.get('account.configuration')

                if form.utilizar_anticipo == True:

                    utiliza_anticipo_venta = True
                    if Configuration(1).default_account_advanced:
                        account_advanced = Configuration(1).default_account_advanced
                    else:
                        self.raise_user_error('No ha configurado la cuenta de Anticipos')

                    pool = Pool()
                    ListAdvanced = pool.get('sale.list_advanced')
                    all_list_advanced = ListAdvanced.search([('party', '=', sale.party)])
                    move_lines_new_advanced = []
                    if form.restante == Decimal(0.0):
                        pagar = form.anticipo
                        if all_list_advanced:
                            for list_advanced in all_list_advanced:
                                for line in list_advanced.lines:
                                    if line.amount != line.utilizado:
                                        if pagar >= line.balance and line.balance > Decimal(0.0) and pagar > Decimal(0.0):
                                            monto_balance = line.balance
                                            line.utilizado = line.utilizado + monto_balance
                                            line.balance = line.balance - monto_balance
                                            line.save()
                                            pagar = pagar - monto_balance
                                            for linem in line.move.lines:
                                                if linem.party and linem.credit > Decimal(0.0) and linem.reconciliation == None and linem.description == "":
                                                    linem.description = "used"+str(sale.reference)
                                                    linem.save()
                                            move = line.move
                                            move.description = sale.reference
                                            move.save()

                                        elif pagar < line.balance and line.balance > Decimal(0.0) and pagar > Decimal(0.0):
                                            monto_balance = pagar
                                            line.utilizado = line.utilizado + monto_balance
                                            line.balance = line.balance - monto_balance
                                            line.save()
                                            pagar = pagar - monto_balance

                                            for linem in move.lines:
                                                if linem.party and linem.credit > Decimal(0.0) and linem.reconciliation == None and linem.description == "":
                                                    linem.credit = linem.credit - monto_balance
                                                    linem.save()
                                            move = line.move
                                            move.description = sale.reference
                                            move.save()

                                            move_lines_new_advanced.append({
                                                'description': "used"+str(sale.reference),
                                                'debit': Decimal(0.0),
                                                'credit': monto_balance,
                                                'account': account_advanced.id,
                                                'party' : sale.party.id,
                                                'move': line.move.id,
                                                'journal': line.move.journal.id,
                                                'period': Period.find(sale.company.id, date=sale.sale_date),
                                            })
                                            created_lines = MoveLine.create(move_lines_new_advanced)
                                            Move.post([line.move])

                    if form.restante > Decimal(0.0) and form.devolver_restante == False:

                        pago_en_cero = True
                        restante = form.restante
                        pagar = form.anticipo - form.restante
                        if all_list_advanced:
                            for list_advanced in all_list_advanced:
                                for line in list_advanced.lines:
                                    if line.amount != line.utilizado:
                                        if pagar >= line.balance and line.balance > Decimal(0.0) and pagar > Decimal(0.0):
                                            monto_balance = line.balance
                                            line.utilizado = line.utilizado + monto_balance
                                            line.balance = line.balance - monto_balance
                                            line.save()
                                            pagar = pagar - monto_balance
                                            for linem in line.move.lines:
                                                if linem.party and linem.credit > Decimal(0.0) and linem.reconciliation == None and linem.description == "":
                                                    linem.description = "used"+str(sale.reference)
                                                    linem.save()
                                            move = line.move
                                            move.description = sale.reference
                                            move.save()

                                        elif pagar < line.balance and line.balance > Decimal(0.0) and pagar > Decimal(0.0):
                                            monto_balance = pagar
                                            line.utilizado = line.utilizado + monto_balance
                                            line.balance = line.balance - monto_balance
                                            line.save()
                                            pagar = pagar - monto_balance

                                            for linem in line.move.lines:
                                                if linem.party and linem.credit > Decimal(0.0) and linem.reconciliation == None and linem.description == "":
                                                    linem.credit = linem.credit - monto_balance
                                                    linem.save()

                                            move_lines_new_advanced.append({
                                                'description': "used"+str(sale.reference),
                                                'debit': Decimal(0.0),
                                                'credit': monto_balance,
                                                'account': account_advanced.id,
                                                'party' : sale.party.id,
                                                'move': line.move.id,
                                                'journal': line.move.journal.id,
                                                'period': Period.find(sale.company.id, date=sale.sale_date),
                                            })
                                            created_lines = MoveLine.create(move_lines_new_advanced)
                                            Move.post([line.move])
                                            move = line.move
                                            move.description = sale.reference
                                            move.save()


                    if form.restante > Decimal(0.0) and form.devolver_restante == True:
                        if Configuration(1).default_account_return:
                            account_return = Configuration(1).default_account_return
                        else:
                            self.raise_user_error('No ha configurado la cuenta para devolucion de anticipos.'
                            '\nDirijase a Financiero-Configuracion-Configuracion Contable')

                        Journal = pool.get('account.journal')
                        journal_r = Journal.search([('type', '=', 'revenue')])
                        for j in journal_r:
                            journal_sale = j.id
                        pago_en_cero = True
                        #crear_nuevo_asiento
                        move_lines_new = []
                        line_move_ids = []
                        reconcile_lines_advanced = []
                        move, = Move.create([{
                            'period': Period.find(sale.company.id, date=sale.sale_date),
                            'journal': journal_sale,
                            'date': sale.sale_date,
                            'origin': str(sale),
                        }])
                        move_lines_new.append({
                            'description': invoice_advanced.number,
                            'debit': Decimal(0.0),
                            'credit': form.restante,
                            'account': invoice_advanced.party.account_receivable.id,
                            'move': move.id,
                            'party': sale.party.id,
                            'journal': journal_sale,
                            'period': Period.find(sale.company.id, date=sale.sale_date),
                        })
                        move_lines_new.append({
                            'description': invoice_advanced.number,
                            'debit': form.restante,
                            'credit': Decimal(0.0),
                            'account': account_return.id,
                            'move': move.id,
                            'journal': journal_sale,
                            'period': Period.find(sale.company.id, date=sale.sale_date),
                        })
                        created_lines = MoveLine.create(move_lines_new)
                        Move.post([move])

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
            if pago_en_cero == True and utiliza_anticipo_venta == True:
                Line = pool.get('account.move.line')
                account = sale.party.account_receivable
                lines = []
                amount = Decimal('0.0')
                for invoice in sale.invoices:
                    for line in invoice.lines_to_pay:
                        if not line.reconciliation:
                            lines.append(line)
                            amount += line.debit - line.credit
                moves = Move.search([('description', '=', sale.reference)])
                for move in moves:
                    if not move:
                        continue
                    for line in move.lines:
                        desc = "used"+str(sale.description)
                        if (not line.reconciliation and line.description == desc
                                and line.party == sale.party):
                            lines.append(line)
                            amount += line.debit - line.credit
                if lines and amount == Decimal('0.0'):
                    Line.reconcile(lines)

            if sale.total_amount < Decimal(0.0):
                Line = pool.get('account.move.line')
                account = sale.party.account_receivable
                lines_dev = []
                amount = Decimal('0.0')
                monto_debit = Decimal('0.0')
                monto_credit = Decimal('0.0')
                sales_dev = Sale.search([('referencia_de_factura', '=', sale.referencia_de_factura)])
                for sale_dev in sales_dev:
                    for invoice in sale_dev.invoices:
                        for line in invoice.lines_to_pay:
                            if not line.reconciliation:
                                lines_dev.append(line)
                                amount += line.debit - line.credit
                moves = Move.search([('description', '=', ('ajustes '+ str(sale.referencia_de_factura)))])
                for move in moves:
                    if not move:
                        continue
                    for line in move.lines:
                        if (not line.reconciliation and
                                line.account.id == account.id):
                            lines_dev.append(line)
                            monto_debit += line.debit
                            monto_credit += line.credit
                    amount = monto_debit - monto_credit
                if lines_dev and amount == Decimal('0.0'):
                    Line.reconcile(lines_dev)

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

    def create_move(self, move_lines, move):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Invoice = pool.get('account.invoice')
        created_lines = MoveLine.create(move_lines)
        Move.post([move])

        return True

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
        localcontext['plazo'] = cls._get_plazo(Invoice, invoice)
        localcontext['unidad'] = cls._get_unidad(Invoice, invoice)

        return super(InvoiceReportPosE, cls).parse(report, records, data,
                localcontext=localcontext)

    @classmethod
    def _get_plazo(cls, Invoice, invoice):
        plazo = 0
        if invoice.payment_term:
            day = 0
            month = 0
            week = 0
            for l in invoice.payment_term.lines:
                if l.days:
                    day += l.days
                if l.months:
                    month += l.months
                if l.weeks:
                    week += l.weeks
            if day >= 0 :
                plazo = day
            if month > 0:
                plazo = month
            if week > 0:
                plazo = week
        return plazo

    @classmethod
    def _get_unidad(cls, Invoice, invoice):
        unidad = ""
        if invoice.payment_term:
            day = 0
            month = 0
            week = 0
            for l in invoice.payment_term.lines:
                if l.days:
                    day += l.days
                if l.months:
                    month += l.months
                if l.weeks:
                    week += l.weeks
            if day >= 0 :
                unidad = 'dias'
            if month > 0:
                unidad = 'meses'
            if week > 0:
                unidad = 'semanas'
        return unidad

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
