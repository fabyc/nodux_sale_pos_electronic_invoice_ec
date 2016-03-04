=============
Ventas
=============

En el menú Ventas/Ventas TPV se ha incluido las caractrerísticas del módulo 
nodux_account_electronic_invoice_ec.
Cuando el vendedor presione el botón pagar se hará la conexión con el WS-Nodux en caso 
que el cliente no se encuentre activo, o sus datos de conexión no sean correctos se 
presentará un mensaje indicando el error. 
Si no se recibió un error el comprobante será firmado y se establecerá la conexión con 
los Servidores del SRi para proceder al envío del comprobante, si luego de enviar el comprobante 
firmado al SRI no se ha presentado un error se preocede a enviar el comprobante para su Autorización, 
si el comprobante ha sido AUTORIZADO se hace el envío del correo electrónico al cliente y se 
guardan los datos necesarios para presentarse en el aplicativo WEB. Caso contrario deberá corregir
la factura y enviarla nuevamente para que sea autorizada. La factura se crerá con su respectivo
estado AUTORIZADA o NO AUTORIZADA. La misma que se podrá revisar en Facturas.

Nota. Se ha agregado las características heredando del módulo sale_shop
