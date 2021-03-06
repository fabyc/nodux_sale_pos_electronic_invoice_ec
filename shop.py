#This file is part sale_shop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['SaleShop']
__metaclass__ = PoolMeta


class SaleShop:
    __name__ = 'sale.shop'
    lote = fields.Boolean('Enviar Comprobantes por Lote',
        help='Enviar sus comprobantes electronicos por Lote')
