# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
from .shop import *

def register():
    Pool.register(
        SaleShop,
        module='nodux_sale_pos_electronic_invoice_ec', type_='model')
    Pool.register(
        WizardSalePayment,
        module='nodux_sale_pos_electronic_invoice_ec', type_='wizard')
