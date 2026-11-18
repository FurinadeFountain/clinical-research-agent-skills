"""The counts and group estimates come from the fixture design, not the analysis code."""
import tempfile
import unittest
from pathlib import Path

from analyze import summarize


class ExperimentalUnitTests(unittest.TestCase):
    def test_fixture_counts_and_reversal(self):
        result = summarize(Path(__file__).with_name("fields.csv"))
        groups = result["groups"]
        for row in groups.values():
            self.assertEqual((row["animals"], row["fields"]), (3, 30))
        self.assertEqual(groups["control"]["animal_means_pct"], {"C01": 10, "C02": 20, "C03": 30})
        self.assertEqual(groups["treated"]["animal_means_pct"], {"T01": 14, "T02": 24, "T03": 34})
        self.assertEqual(groups["control"]["animal_weighted_mean_pct"], 20)
        self.assertEqual(groups["treated"]["animal_weighted_mean_pct"], 24)
        self.assertEqual(result["treated_minus_control_pp"], 4)
        self.assertAlmostEqual(groups["control"]["field_weighted_mean_pct"], 70 / 3)
        self.assertAlmostEqual(groups["treated"]["field_weighted_mean_pct"], 62 / 3)

    def test_repeated_field_is_not_another_observation(self):
        header = "animal_id,group,field_id,stained_area_pct\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.csv"
            path.write_text(header + "A,control,1,20\n" * 2, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate field"):
                summarize(path)

    def test_animal_cannot_switch_groups_in_this_design(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.csv"
            path.write_text(
                "animal_id,group,field_id,stained_area_pct\n"
                "A,control,1,20\nA,treated,2,24\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "two groups"):
                summarize(path)


if __name__ == "__main__":
    unittest.main()
