import unittest

from app.services.rag_service import RAGService


class RAGServiceTests(unittest.TestCase):
    def test_extracts_article_number_variants(self):
        self.assertEqual(RAGService._extraer_numero_articulo("¿Qué dice el artículo 1o.?"), "1")
        self.assertEqual(RAGService._extraer_numero_articulo("Explica el artículo 20 Bis"), "20 Bis")
        self.assertIsNone(RAGService._extraer_numero_articulo("Explica la retroactividad"))

    def test_exact_article_response_uses_verified_context(self):
        context = (
            "[Fuente: CCF.pdf, página 1, COINCIDENCIA EXACTA DEL ARTÍCULO SOLICITADO]\n"
            "Artículo 1o.- Las disposiciones de este Código regirán en toda la República."
        )
        response = RAGService._respuesta_extractiva_verificable(
            "¿Qué establece el artículo 1 del Código Civil Federal?", context
        )
        self.assertIn("Las disposiciones de este Código", response)
        self.assertIn("CCF.pdf, página 1", response)

    def test_retroactivity_response_does_not_deny_available_evidence(self):
        context = (
            "[Fuente: CCF.pdf, página 1, COINCIDENCIA LITERAL]\n"
            "Artículo 5o.- A ninguna ley ni disposición gubernativa se dará efecto retroactivo "
            "en perjuicio de persona alguna.\nArtículo 6o.- Texto siguiente."
        )
        response = RAGService._respuesta_extractiva_verificable(
            "¿Qué dispone el Código sobre la aplicación retroactiva de las leyes?", context
        )
        self.assertIn("prohíbe dar efecto retroactivo", response)
        self.assertNotIn("no dispone", response.lower())

    def test_article_reference_does_not_end_article_body(self):
        context = (
            "[Fuente: CCF.pdf, página 4, COINCIDENCIA LITERAL]\n"
            "Artículo 25.- Son personas morales:\n"
            "IV. Los sindicatos a que se refiere la fracción XVI del\n"
            "artículo 123 de la Constitución Federal;\n"
            "V. Las sociedades cooperativas y mutualistas;\n"
            "Artículo 26.- Las personas morales pueden ejercitar derechos."
        )
        article = RAGService._extraer_articulo_contexto(context, "25")
        self.assertIn("artículo 123", article)
        self.assertIn("V. Las sociedades cooperativas", article)
        self.assertNotIn("Artículo 26", article)


if __name__ == "__main__":
    unittest.main()
