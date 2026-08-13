import unittest

from app.services.glossary_service import GlossaryService


class GlossaryServiceTests(unittest.TestCase):
    def test_extracts_json_from_markdown(self):
        raw = '''```json
        {
          "definicion_tecnica": "Una definición técnica suficientemente extensa para superar la validación mínima requerida por el servicio jurídico.",
          "explicacion_sencilla": "Una explicación práctica suficientemente clara y extensa para comprender la aplicación del concepto.",
          "mnemotecnia": "Regla fácil de recordar"
        }
        ```'''
        parsed = GlossaryService._extraer_json(raw)
        validated = GlossaryService._validar_datos_ia(parsed)
        self.assertEqual(validated["mnemotecnia"], "Regla fácil de recordar")

    def test_rejects_incomplete_json(self):
        with self.assertRaises(ValueError):
            GlossaryService._extraer_json('{"definicion_tecnica": "incompleta"')

    def test_rejects_generic_fallback(self):
        self.assertFalse(GlossaryService.es_ficha_valida(
            "Definición generada para ley marcial.",
            "Concepto jurídico fundamental.",
            "Recordar según el contexto de la materia.",
        ))


if __name__ == "__main__":
    unittest.main()
