import unittest
from pathlib import Path


README = (
    Path(__file__).resolve().parents[1] / "README.md"
).read_text(encoding="utf-8")


class TestDocumentacao(unittest.TestCase):
    def test_readme_contem_fluxo_completo_das_placas(self):
        trechos = [
            "Placa 1 P0 ↔ Placa 2 P4",
            "Placa 2 P0 ↔ Placa 3 P0",
            "sudo python3 placa1.py",
            "sudo python3 placa2.py",
            "sudo python3 placa3_eco.py",
            "nc 192.168.200.4 7000",
            "sudo python3 placa3.py",
            "nc -C 192.168.200.4 6667",
        ]
        for trecho in trechos:
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, README)


if __name__ == "__main__":
    unittest.main()
