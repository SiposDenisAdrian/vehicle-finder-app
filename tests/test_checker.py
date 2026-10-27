import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import checker
from google.genai import errors


def make_evaluation(title, price, mileage, reliability_score, matches=True):
    return {
        "matches": matches,
        "title": title,
        "price": price,
        "mileage": mileage,
        "engine": "1.5 TSI DSG benzină",
        "year": 2022,
        "reason": "Respectă filtrele.",
        "reliability_score": reliability_score,
        "reliability_reason": "Combinație cu reputație bună.",
    }


class RecommendationTests(unittest.TestCase):
    def test_gemini_request_pacing_limits_calls_to_twelve_per_minute(self):
        with patch.object(checker, "_last_gemini_request_at", None), patch.object(
            checker.time, "monotonic", side_effect=[100, 100, 102, 107]
        ), patch.object(checker.time, "sleep") as sleep:
            checker.wait_for_gemini_rate_limit()
            checker.wait_for_gemini_rate_limit()

        sleep.assert_called_once_with(3)

    def test_gemini_429_retries_after_server_requested_delay(self):
        client = Mock()
        client.models.generate_content.side_effect = [
            errors.ClientError(
                429,
                {"error": {"message": "Please retry in 2.5s."}},
                None,
            ),
            Mock(text="{}"),
        ]

        with patch.object(checker, "wait_for_gemini_rate_limit"), patch.object(
            checker.time, "sleep"
        ) as sleep:
            response = checker.generate_content_with_retry(
                client, "gemini-test", "prompt", {}
            )

        self.assertEqual(response.text, "{}")
        sleep.assert_called_once_with(2.5)
        self.assertEqual(client.models.generate_content.call_count, 2)

    def test_primary_429_uses_fallback_model(self):
        evaluation = make_evaluation("VW Golf", 15_000, 40_000, 80)
        client = Mock()
        client.models.generate_content.side_effect = [
            errors.ClientError(429, {"error": {"message": "quota exceeded"}}, None),
            Mock(text=json.dumps(evaluation)),
        ]
        car = {
            "title": "VW Golf 1.5 TSI DSG",
            "text": "Benzină, automată, 40.000 km.",
            "url": "https://example.test/golf",
        }

        with patch.object(checker, "wait_for_gemini_rate_limit"):
            result = checker.evaluate_with_ai(client, car)

        self.assertEqual(result, evaluation)
        self.assertEqual(
            [call.kwargs["model"] for call in client.models.generate_content.call_args_list],
            ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"],
        )

    def test_target_model_filter_includes_t_roc_and_excludes_other_models(self):
        self.assertTrue(
            checker.is_target_model(
                {"title": "VW T-Roc Life 1.5 TSI DSG"}
            )
        )
        self.assertTrue(
            checker.is_target_model(
                {"title": "Volkswagen T Roc 1.5 TSI"}
            )
        )
        self.assertFalse(
            checker.is_target_model(
                {"title": "VW T-Cross Life 1.0 TSI DSG"}
            )
        )

    def test_recommendation_score_weights_reliability_price_and_mileage(self):
        evaluation = make_evaluation("VW Golf", 10_500, 45_000, 80)

        self.assertEqual(checker.recommendation_score(evaluation), 65)

    def test_validate_evaluation_rejects_out_of_range_reliability(self):
        evaluation = make_evaluation("VW Golf", 15_000, 40_000, 101)

        with self.assertRaises(ValueError):
            checker.validate_evaluation(evaluation, "listing-1")

    def test_main_sends_top_three_and_reuses_unchanged_evaluations(self):
        cars = [
            {"id": "1", "url": "https://example.test/1", "title": "VW Golf 1", "text": "ad 1"},
            {"id": "2", "url": "https://example.test/2", "title": "Audi A3 2", "text": "ad 2"},
            {"id": "3", "url": "https://example.test/3", "title": "VW Golf 3", "text": "ad 3"},
            {"id": "4", "url": "https://example.test/4", "title": "Audi A3 4", "text": "ad 4"},
        ]
        evaluations = {
            "1": make_evaluation("VW Golf 1", 10_000, 40_000, 70),
            "2": make_evaluation("Audi A3 2", 12_000, 50_000, 90),
            "3": make_evaluation("VW Golf 3", 15_000, 60_000, 80),
            "4": make_evaluation("Audi A3 4", 14_000, 50_000, 75, matches=False),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "car_evaluations.json"
            sent_recommendations = []

            with patch.object(checker, "CACHE_FILE", cache_path), patch.dict(
                os.environ,
                {
                    "GEMINI_API_KEY": "test-key",
                    "TELEGRAM_BOT_TOKEN": "test-token",
                    "TELEGRAM_CHAT_ID": "test-chat",
                },
            ), patch.object(
                checker, "get_listing_urls", return_value=["https://example.test/list"]
            ), patch.object(
                checker, "get_link_selector", return_value="a.car"
            ), patch.object(
                checker, "scrape_listings", return_value=cars
            ), patch.object(
                checker.genai, "Client", return_value=Mock()
            ), patch.object(
                checker,
                "evaluate_with_ai",
                side_effect=lambda client, car: evaluations[car["id"]],
            ) as evaluate, patch.object(
                checker,
                "send_telegram_recommendations",
                side_effect=lambda recommendations, *_: sent_recommendations.append(
                    recommendations
                ),
            ):
                checker.main()
                checker.main()

            self.assertEqual(evaluate.call_count, 4)
            self.assertEqual(len(sent_recommendations), 2)
            expected_urls = [
                "https://example.test/2",
                "https://example.test/1",
                "https://example.test/3",
            ]
            self.assertEqual(
                [item["url"] for item in sent_recommendations[0]], expected_urls
            )
            self.assertEqual(
                [item["url"] for item in sent_recommendations[1]], expected_urls
            )
            self.assertEqual(len(json.loads(cache_path.read_text())), 4)


if __name__ == "__main__":
    unittest.main()
