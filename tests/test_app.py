import unittest

from pacemaker.app_state import AppState
from pacemaker.data_loader import normalize_metal


class LoaderTests(unittest.TestCase):
    def test_normalize_metal_aliases(self):
        self.assertEqual(normalize_metal("Aluminium"), "aluminum")
        self.assertEqual(normalize_metal("CU"), "copper")


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = AppState()

    def test_metals_available(self):
        metals = self.state.get_metals()
        self.assertIn("copper", metals)
        self.assertIn("aluminum", metals)
        self.assertIn("nickel", metals)

    def test_available_dates(self):
        dates = self.state.get_available_dates("copper")
        self.assertGreater(len(dates), 10)
        self.assertEqual(dates[0], "2020-01-02")

    def test_news_deduplication(self):
        copper_clusters = self.state.get_news_clusters("copper")
        strike_clusters = [cluster for cluster in copper_clusters if cluster["theme"] == "supply disruption"]
        self.assertEqual(strike_clusters[0]["article_count"], 1)

    def test_decision_shape(self):
        decision = self.state.get_decision("copper")
        self.assertTrue(decision.action)
        self.assertEqual(decision.metal, "copper")
        self.assertEqual(len(decision.rationale) >= 3, True)

    def test_decisions_expose_confidence_and_probability(self):
        aluminum = self.state.get_decision("aluminum")
        copper = self.state.get_decision("copper")
        self.assertGreaterEqual(aluminum.confidence, 0.0)
        self.assertLessEqual(aluminum.confidence, 1.0)
        self.assertGreaterEqual(copper.why_now["price_context"]["up_probability"], 0.0)
        self.assertLessEqual(copper.why_now["price_context"]["up_probability"], 1.0)

    def test_model_is_trained(self):
        self.assertGreater(self.state.trained_model["sample_count"], 0)
        self.assertGreaterEqual(self.state.trained_model["train_accuracy"], 0.4)

    def test_historical_performance_present(self):
        decision = self.state.get_decision("copper", as_of_date="2025-06-02", risk_appetite="low")
        self.assertEqual(decision.risk_appetite, "low")
        self.assertEqual(decision.decision_date, "2025-06-02")
        self.assertIn("verification_status", decision.historical_performance)
        self.assertIn("realized_return_pct", decision.historical_performance)


if __name__ == "__main__":
    unittest.main()
