import sys
import unittest
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from apps.csv_parser.csv_parse_handler import parse_latam_csv
from apps.html_parser.html_parse_handler import parse_latam_html


class LatamTemplateParserTests(unittest.TestCase):
    def test_parse_latam_csv_groups_rows_by_tipo_and_folio(self):
        csv_content = """TIPO (33: Factura electrónica);FOLIO;SECUENCIA;FECHA;RUT;RAZONSOCIAL;GIRO;COMUNA;DIRECCION;AFECTO;PRODUCTO;CANTIDAD;CODITEM;UNIDADMEDIDA(HR, KG, M3, MR, PM, PP, QTAL, TBDM, TBDU, TON, UNID);COMUNADESTINO;CIUDADDESTINO;DIRECCIONDESTINO
33;1001;2;20-07-2026;PO-1;Bepensa;Bebidas;Santo Domingo;Main Street;Y;Monster Zero;3;MAT2;UNID;;Santo Domingo;Ship address
33;1001;1;20-07-2026;PO-1;Bepensa;Bebidas;Santo Domingo;Main Street;Y;Monster Energy;2;MAT1;UNID;;Santo Domingo;Ship address
""".encode("utf-8")

        result = parse_latam_csv(csv_content, {"file_name": "sample.csv", "file_type": "text/csv"})

        self.assertEqual(["1001"], list(result.keys()))
        record = result["1001"]
        self.assertEqual("LATAM", record["Region"])
        self.assertEqual("CSV", record["Podoctype"])
        self.assertEqual("PO-1", record["CustPo"])
        self.assertEqual("MAT1", record["NavHeadToItem"][0]["Material"])
        self.assertEqual("MAT2", record["NavHeadToItem"][1]["Material"])

    def test_parse_latam_html_extracts_header_items_and_totals(self):
        html_content = """
<HTML><body>
<p>Orden de compra : OCBD0125252 Fecha Orden Compra: 30/Junio/2026</p>
<p>Proveedor : MONSTER ENERGY DOMINICAN REPUBLIC SRL Vendedor :</p>
<p>Fecha Promesa : 30/Junio/2026 Facturar a : Bepensa Dominicana S.A. Consignar a : Producto Terminado Refrescos Elaboró : User Requisitó : Buyer Folio de solicitud de compra : REQ-0128109</p>
<table><tr><th>Cantidad</th><th>Unidad</th><th>Descripción</th><th>Precio</th><th>Importe (USD)</th></tr>
<tr><td>1,540.00</td><td>473ML-24</td><td>E081003503 Monster Energy Lata 473ml 24P</td><td>24.6600</td><td>37,976.4000</td></tr></table>
<table><tr><td>Subtotal:</td><td>37,976.4000</td></tr><tr><td>IVA:</td><td>6,835.7500</td></tr><tr><td>Total:</td><td>44,812.1500</td></tr></table>
</body></HTML>
""".encode("utf-8")

        result = parse_latam_html(html_content, {"file_name": "sample.html", "file_type": "text/html"})

        record = result["OCBD0125252"]
        self.assertEqual("HTML", record["Podoctype"])
        self.assertEqual("MONSTER ENERGY DOMINICAN REPUBLIC SRL", record["SalesOrgDescription"])
        self.assertEqual("E081003503", record["NavHeadToItem"][0]["Material"])
        self.assertEqual("44,812.1500", record["Total"])


if __name__ == "__main__":
    unittest.main()