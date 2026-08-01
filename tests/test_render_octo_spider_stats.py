import importlib.util
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
MODULE_PATH = os.path.join(ROOT, "examples", "render_octo_spider_stats.py")

spec = importlib.util.spec_from_file_location("render_octo_spider_stats", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)


class RenderOctoSpiderStatsTests(unittest.TestCase):
    def test_task_is_correct_treats_error_rows_as_incorrect(self):
        self.assertFalse(module._task_is_correct({"error": "boom"}))
        self.assertFalse(module._task_is_correct({"execution_error": "boom"}))

    def test_render_table_counts_error_rows_in_total(self):
        rendered = module._render_table(
            [
                {"task_id": "t1", "db_id": "DB1", "matched_gold": True},
                {"task_id": "t2", "db_id": "DB1", "error": "missing snapshot"},
                {"task_id": "t3", "db_id": "DB2", "execution_error": "sql failed"},
            ]
        )

        self.assertIn("| DB1", rendered)
        self.assertIn("| DB2", rendered)
        self.assertIn("***GRAND TOTAL***", rendered)
        self.assertIn("3", rendered)
        self.assertNotIn("Skipped tasks without definitive correctness field", rendered)


if __name__ == "__main__":
    unittest.main()
