import sys
import unittest
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))
from apps.csv_parser.csv_parse_handler import parse_latam_csv
from apps.html_parser.html_parse_handler import parse_latam_html


class LatamTemplateParserTests(unittest.TestCase):
    def test_parse_latam_csv_matches_mass_creation_contract(self):
        csv_content = """TIPO (33: Factura electrónica);FOLIO;SECUENCIA;FECHA;RUT;RAZONSOCIAL;GIRO;COMUNA;DIRECCION;AFECTO;PRODUCTO;CANTIDAD;CODITEM;UNIDADMEDIDA(HR, KG, M3, MR, PM, PP, QTAL, TBDM, TBDU, TON, UNID);COMUNADESTINO;CIUDADDESTINO;DIRECCIONDESTINO
33;1001;2;20-07-2026;PO-1;Bepensa;Bebidas;Santo Domingo;Main Street;Y;Monster Zero;3;MAT2;UNID;;Santo Domingo;Ship address
33;1001;1;20-07-2026;PO-1;Bepensa;Bebidas;Santo Domingo;Main Street;Y;Monster Energy;2;MAT1;UNID;;Santo Domingo;Ship address
""".encode("utf-8")

        result = parse_latam_csv(csv_content, {
            "file_name": "sample.csv",
            "file_type": "text/csv",
            "created_at": "2026-08-25T09:30:00",
            "sender_email": "sender@example.com"
        })

        self.assertEqual({"AsopNo", "AddField1", "NavHeadToItem", "NavHeadtoMeta"}, set(result))
        self.assertEqual({
            "AsopNo", "CsvNO", "OCRItemno", "MatDesc", "Quantity", "Material",
            "Uom", "DlvDate", "CustPo", "SoldTo", "ShipCity", "ShipTo"
        }, set(result["NavHeadToItem"][0]))
        self.assertEqual("0000000000", result["AsopNo"])
        self.assertEqual("MASSCREATION", result["AddField1"])
        self.assertEqual(2, len(result["NavHeadToItem"]))
        self.assertEqual("33;1001;2", result["NavHeadToItem"][0]["CsvNO"])
        self.assertEqual("10", result["NavHeadToItem"][0]["OCRItemno"])
        self.assertEqual("33;1001;1", result["NavHeadToItem"][1]["CsvNO"])
        self.assertEqual("20", result["NavHeadToItem"][1]["OCRItemno"])
        self.assertEqual("2026-07-20", result["NavHeadToItem"][0]["DlvDate"])
        self.assertEqual("2026-08-25", result["NavHeadtoMeta"][0]["FileDate"])
        self.assertEqual("Amit.Nirala@Monsterenergy.com", result["NavHeadtoMeta"][0]["CustEmail"])
        self.assertEqual("application/vnd.ms-excel", result["NavHeadtoMeta"][0]["MimeType"])
        self.assertEqual({
            "AsopNo", "CustEmail", "MonsterEmail", "FileDate", "FileName", "MimeType",
            "Field1", "Field2", "Field3", "Field4", "Field5"
        }, set(result["NavHeadtoMeta"][0]))

    def test_parse_latam_html_matches_confirmed_output_contract(self):
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

        result = parse_latam_html(html_content, {
            "file_name": "sample.html",
            "file_type": "text/html",
            "created_at": "2026-09-21T15:20:00"
        })

        record = result
        self.assertEqual({
            "AsopNo",
            "Region",
            "Podoctype",
            "CustPo",
            "PODate",
            "DlvDate",
            "SalesOrg",
            "SoldTo",
            "ShipTo",
            "NavHeadToItem",
            "NavHeadtoMeta"
        }, set(record))
        self.assertEqual("HTML", record["Podoctype"])
        self.assertEqual("2026-06-30", record["PODate"])
        self.assertEqual("2026-06-30", record["DlvDate"])
        self.assertEqual("MONSTER ENERGY DOMINICAN REPUBLIC SRL", record["SalesOrg"])
        self.assertEqual("E081003503", record["NavHeadToItem"][0]["Material"])
        self.assertEqual({
            "AsopNo",
            "OCRItemno",
            "Quantity",
            "Uom",
            "Material",
            "MatDesc"
        }, set(record["NavHeadToItem"][0]))
        self.assertNotIn("UnitPrice", record["NavHeadToItem"][0])
        self.assertNotIn("Amount", record["NavHeadToItem"][0])
        self.assertEqual("2026-09-21", record["NavHeadtoMeta"][0]["FileDate"])
        self.assertNotIn("Subtotal", record)
        self.assertNotIn("IVA", record)
        self.assertNotIn("Total", record)

    def test_parse_latam_html_uses_asop_and_region_from_metadata(self):
        html_content = b"<html><body>Orden de compra: PO-123</body></html>"

        result = parse_latam_html(html_content, {
            "asop_no": "ASOP-123",
            "region": "LATAM",
            "file_name": "sample.html",
            "file_type": "text/html"
        })

        record = result
        self.assertEqual("ASOP-123", record["AsopNo"])
        self.assertEqual("LATAM", record["Region"])
        self.assertEqual("ASOP-123", record["NavHeadtoMeta"][0]["AsopNo"])


if __name__ == "__main__":
    unittest.main()