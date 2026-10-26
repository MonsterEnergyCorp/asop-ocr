import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_PATH = Path(__file__).resolve().parents[1] / "code" / "backend"
sys.path.insert(0, str(BACKEND_PATH))
from apps.csv_parser import mappings
from apps.csv_parser.csv_parse_handler import (
    build_erp_payload,
    detect_csv_separator,
    parse_csv_po,
    parse_or_fail,
    po_numbers_of,
    update_processed_values,
)

SAMPLES = Path(__file__).resolve().parents[1] / "sample_inputs" / "latam" / "csv"
LOGINSA_FILE = SAMPLES / "Cargas Masivas_20-07-2026_Loginsa.csv"
ECSA_FILE = SAMPLES / "Cargas Masivas_20-07-2026_Ecsa.csv"
FILE_DATA = {"file_name": "sample.csv", "file_type": "text/csv", "created_at": "2026-07-20", "sender_email": "sender@example.com"}


class CsvParserTests(unittest.TestCase):
    def test_loginsa_sample_uses_latam_template(self):
        result = parse_csv_po(LOGINSA_FILE.read_bytes(), {**FILE_DATA, "file_name": LOGINSA_FILE.name})

        self.assertEqual({"AsopNo", "AddField1", "NavHeadToItem", "NavHeadtoMeta"}, set(result))
        self.assertEqual("0000000000", result["AsopNo"])
        self.assertEqual("MASSCREATION", result["AddField1"])
        items = result["NavHeadToItem"]
        self.assertEqual(9, len(items))
        self.assertEqual({
            "AsopNo": "0000000000", "CsvNO": "52;1;1", "OCRItemno": "10", "MatDesc": "MONS PARADISE X06 LA473",
            "Quantity": "320", "Material": "109363", "Uom": "CAJA", "DlvDate": "2026-07-22", "CustPo": "93281000-K",
            "SoldTo": "COCA COLA EMBONOR S.A.;ELABORACION BEBIDAS NO ALCOHOLICAS;ARICA;AVENIDA SANTA MARIA 2654",
            "ShipCity": "CONCON", "ShipTo": "CAMINO INTERNACIONAL 13255",
        }, items[0])
        self.assertEqual({
            "AsopNo": "0000000000", "CsvNO": "52;5;4", "OCRItemno": "90", "MatDesc": "MONS PIPELINE X06 LA473",
            "Quantity": "720", "Material": "116363", "Uom": "CAJA", "DlvDate": "2026-07-24", "CustPo": "93281000-K",
            "SoldTo": "COCA COLA EMBONOR S.A.;ELABORACION BEBIDAS NO ALCOHOLICAS;ARICA;AVENIDA SANTA MARIA 2654",
            "ShipCity": "TEMUCO", "ShipTo": "AVENIDA MANUEL RECABARREN 02850",
        }, items[-1])
        self.assertEqual("93281000-K", po_numbers_of({"MASSCREATION": result}))
        meta = result["NavHeadtoMeta"][0]
        self.assertEqual(f"{LOGINSA_FILE.name}.eml", meta["FileName"])
        self.assertEqual("sender@example.com", meta["CustEmail"])

    def test_ecsa_sample_parses_with_the_same_template(self):
        result = parse_csv_po(ECSA_FILE.read_bytes(), {**FILE_DATA, "file_name": ECSA_FILE.name})

        items = result["NavHeadToItem"]
        self.assertEqual(18, len(items))
        self.assertEqual("52;1;1", items[0]["CsvNO"])
        self.assertEqual("ARICA", items[0]["ShipCity"])
        self.assertEqual("1760", items[0]["Quantity"])
        self.assertEqual("107458", items[0]["Material"])
        self.assertEqual("CAJA", items[0]["Uom"])
        self.assertEqual("2026-07-20", items[0]["DlvDate"])
        self.assertEqual("52;17;1", items[-1]["CsvNO"])
        self.assertEqual("TEMUCO", items[-1]["ShipCity"])
        self.assertEqual("AVENIDA MANUEL RECABARREN 02850", items[-1]["ShipTo"])
        self.assertEqual(f"{ECSA_FILE.name}.eml", result["NavHeadtoMeta"][0]["FileName"])

    def test_mime_type_is_the_file_content_type(self):
        result = parse_csv_po(LOGINSA_FILE.read_bytes(), {**FILE_DATA, "file_type": "application/vnd.ms-excel"})

        self.assertEqual("application/vnd.ms-excel", result["NavHeadtoMeta"][0]["MimeType"])
        fallback = parse_csv_po(LOGINSA_FILE.read_bytes(), {**FILE_DATA, "file_type": ""})
        self.assertEqual("text/csv", fallback["NavHeadtoMeta"][0]["MimeType"])

    def test_unreadable_file_goes_to_erp_with_status_52(self):
        result = parse_csv_po(b"A;B\n1;2\n", {**FILE_DATA, "file_name": "junk.csv"})
        payload = build_erp_payload(result)

        self.assertEqual({"UNEXTRACTED"}, set(payload))
        self.assertEqual("52", payload["UNEXTRACTED"]["Status"])
        self.assertEqual("junk.csv.eml", payload["UNEXTRACTED"]["NavHeadtoMeta"][0]["FileName"])

    def test_one_bad_date_fails_the_whole_file_with_metadata_kept(self):
        content = LOGINSA_FILE.read_bytes().replace(b";22-07-2026;", b";not-a-date;", 1)
        result = parse_or_fail(content, {**FILE_DATA, "file_name": LOGINSA_FILE.name})

        self.assertEqual(mappings.UNEXTRACTED_PO, result["CustPo"])
        self.assertEqual([], result["NavHeadToItem"])
        self.assertEqual(LOGINSA_FILE.name + ".eml", result["NavHeadtoMeta"][0]["FileName"])

    def test_missing_required_column_fails_the_file(self):
        content = LOGINSA_FILE.read_bytes().replace(b";CANTIDAD;", b";CANTX;", 1)
        result = parse_or_fail(content, FILE_DATA)

        self.assertEqual(mappings.UNEXTRACTED_PO, result["CustPo"])

    def test_template_without_po_column_leaves_customer_po_blank(self):
        templates = copy.deepcopy(mappings.CSV_TEMPLATES)
        del templates["LATAM_MASS_CREATION"]["columns"]["po"]
        with mock.patch.object(mappings, "CSV_TEMPLATES", templates):
            result = parse_csv_po(ECSA_FILE.read_bytes(), FILE_DATA)

        self.assertEqual("", result["NavHeadToItem"][0]["CustPo"])
        self.assertEqual("MASSCREATION", po_numbers_of({"MASSCREATION": result}))

    def test_new_template_is_picked_from_configuration(self):
        templates = {
            "OTHER_CLIENT": {
                "markers": ["PEDIDO", "CODIGO", "CANTIDAD"],
                "add_field1": "CUSTOMER_X",
                "columns": {
                    "tipo": ["TIPO"],
                    "folio": ["PEDIDO"],
                    "secuencia": ["LINEA"],
                    "fecha": ["FECHA"],
                    "company": ["CLIENTE"],
                    "business_activity": ["RUBRO"],
                    "sold_city": ["CIUDAD"],
                    "sold_address": ["DIRECCION"],
                    "description": ["DESCRIPCION"],
                    "quantity": ["CANTIDAD"],
                    "material": ["CODIGO"],
                    "uom": ["UNIDAD"],
                    "po": ["ORDEN"],
                },
                "csv_no": ["tipo", "folio", "secuencia"],
                "sold_to": ["company", "sold_city"],
                "ship_city": ["sold_city"],
                "ship_to": ["sold_address"],
            },
        }
        content = (
            "TIPO,PEDIDO,LINEA,FECHA,CLIENTE,RUBRO,CIUDAD,DIRECCION,DESCRIPCION,CANTIDAD,CODIGO,UNIDAD,ORDEN\n"
            "10,P-7,1,03/04/2026,Acme,Retail,Lima,Av. Uno 100,Widget,5,W-1,CAJA,PO-99\n"
        ).encode("utf-8")
        with mock.patch.object(mappings, "CSV_TEMPLATES", templates):
            result = parse_csv_po(content, FILE_DATA)

        self.assertEqual("CUSTOMER_X", result["AddField1"])
        item = result["NavHeadToItem"][0]
        self.assertEqual("10;P-7;1", item["CsvNO"])
        self.assertEqual("PO-99", item["CustPo"])
        self.assertEqual("Acme;Lima", item["SoldTo"])
        self.assertEqual("Av. Uno 100", item["ShipTo"])
        self.assertEqual("W-1", item["Material"])

    def test_comma_separated_file_is_detected_from_header(self):
        content = "TIPO,FOLIO,SECUENCIA,FECHA,RAZONSOCIAL,GIRO,COMUNA,DIRECCION,PRODUCTO,CANTIDAD,CODITEM,UNIDADMEDIDA(HR, KG)\n33,1,1,20-07-2026,Acme,Bebidas,Lima,Av 1,Monster,4,M1,UNID\n"
        self.assertEqual(",", detect_csv_separator(content))
        result = parse_csv_po(content.encode("utf-8"), FILE_DATA)

        self.assertEqual("33;1;1", result["NavHeadToItem"][0]["CsvNO"])
        self.assertEqual("4", result["NavHeadToItem"][0]["Quantity"])

    def test_erp_payload_and_po_numbers_for_success(self):
        result = parse_csv_po(LOGINSA_FILE.read_bytes(), FILE_DATA)
        payload = build_erp_payload(result)
        update = update_processed_values(payload)

        self.assertEqual({"MASSCREATION"}, set(payload))
        self.assertIn('"po_numbers" = \'93281000-K\'', update)

    def test_semicolon_wins_when_header_has_commas_inside_legends(self):
        self.assertEqual(";", detect_csv_separator(ECSA_FILE.read_bytes().decode("cp1252")))


if __name__ == "__main__":
    unittest.main()
