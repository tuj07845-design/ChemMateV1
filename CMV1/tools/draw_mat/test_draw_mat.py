# -*- coding: utf-8 -*-
"""
ChemMate V1 — draw_mat / tables 单元测试

跑法：python test_draw_mat.py
覆盖：
  - 四种图种的拆表逻辑（SplitTests）
  - draw_mat 的数据缓存 / dry_run 流程（CacheTests）

注意：全部测试走 dry_run，不会真的调 MATLAB。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import draw_mat as dm  # noqa: E402
from .tables import DrawError, split_for_plot  # noqa: E402


def vu(v, u=""):
    """构造 data_get 风格的 {value, unit} 结构。"""
    return {"value": v, "unit": u}


def sample_process():
    """最小流程样例：4 条流股 + 1 个 connections（B7: S6 → S7/S8）。"""
    return {
        "success": True,
        "streams": {
            "S5": {
                "temperature": vu(250, "C"),
                "pressure": vu(18, "bar"),
                "mole_fraction": {"CYCLO-01": vu(0.473), "CH4": vu(0.473)},
                "mole_flow": {"CYCLO-01": vu(47.3, "kmol/h"), "CH4": vu(47.3, "kmol/h")},
            },
            "S6": {
                "temperature": vu(30, "C"),
                "pressure": vu(10, "bar"),
                "mole_fraction": {"CYCLO-01": vu(0.473), "CH4": vu(0.473)},
                "mole_flow": {"CYCLO-01": vu(47.3, "kmol/h"), "CH4": vu(47.3, "kmol/h")},
            },
            "S7": {
                "temperature": vu(30, "C"),
                "pressure": vu(8, "bar"),
                "mole_fraction": {"CYCLO-01": vu(0.0197), "CH4": vu(0.886)},
                "mole_flow": {"CYCLO-01": vu(2.0, "kmol/h"), "CH4": vu(85.0, "kmol/h")},
            },
            "S8": {
                "temperature": vu(30, "C"),
                "pressure": vu(8, "bar"),
                "mole_fraction": {"CYCLO-01": vu(0.9718), "CH4": vu(0.0182)},
                "mole_flow": {"CYCLO-01": vu(4.0, "kmol/h"), "CH4": vu(0.08, "kmol/h")},
            },
            "S10": {
                "temperature": vu(89.7, "C"),
                "pressure": vu(1.0, "bar"),
                "mole_fraction": {"TOLUE-01": vu(0.4846), "CYCLO-01": vu(0.5154)},
                "mole_flow": {"TOLUE-01": vu(1.0, "kmol/h"), "CYCLO-01": vu(1.06, "kmol/h")},
            },
        },
        "connections": [{"block": "B7", "inputs": ["S6"], "outputs": ["S7", "S8"]}],
    }


class SplitTests(unittest.TestCase):
    """四种图种的拆表逻辑。"""

    def test_tp(self):
        # stream_tp：只画指定的两条流股
        rows, _, _ = split_for_plot("stream_tp", sample_process(), streams=["S5", "S10"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["T"], 250)

    def test_comp(self):
        # stream_composition：S10 的组分-分率表
        rows, _, _ = split_for_plot("stream_composition", sample_process(), stream="S10")
        self.assertEqual({r["component"] for r in rows}, {"TOLUE-01", "CYCLO-01"})

    def test_track(self):
        # component_track：大小写不敏感，matched_component 回填实际键名
        rows, _, extra = split_for_plot("component_track", sample_process(), component="cyclo-01")
        self.assertEqual(extra["matched_component"], "CYCLO-01")
        s8 = next(r for r in rows if r["stream"] == "S8")
        self.assertAlmostEqual(s8["value"], 0.9718)

    def test_balance(self):
        # balance_check：B7 进 S6 / 出 S7, S8，side 应为 in/out 混合
        rows, _, _ = split_for_plot("balance_check", sample_process(), block="B7")
        self.assertEqual({r["side"] for r in rows}, {"in", "out"})

    def test_sankey_rejected(self):
        # 白名单外图种必须拒绝（V1 只有四种图）
        with self.assertRaises(DrawError) as ctx:
            split_for_plot("sankey", sample_process())
        self.assertEqual(ctx.exception.code, "unknown_plot_type")


class CacheTests(unittest.TestCase):
    """draw_mat 数据缓存与 dry_run 流程。"""

    def setUp(self):
        dm._LAST_PROCESS_DATA = None

    def test_missing_without_cache(self):
        # 没数据也没缓存 → 明确报 missing_process_data
        r = draw_mat(plot_type="stream_tp", dry_run=True)
        self.assertFalse(r["success"])
        self.assertEqual(r["error"], "missing_process_data")

    def test_cache_then_draw_without_json(self):
        # 先缓存数据，再画图时不传 JSON 也能成功
        dm.remember_process_data(sample_process())
        with tempfile.TemporaryDirectory() as tmp:
            r = dm.draw_mat(
                plot_type="stream_tp",
                streams=["S5", "S10"],
                jobs_root=tmp,
                dry_run=True,
            )
        self.assertTrue(r["success"])
        self.assertEqual(r["plot_type"], "stream_tp")

    def test_wrap_data_get(self):
        # wrap_data_get：包一层后返回值自动进缓存
        def fake_get(path):
            return sample_process()

        wrapped = dm.wrap_data_get(fake_get)
        wrapped("dummy.bkp")
        self.assertIsNotNone(dm.get_cached_process_data())
        with tempfile.TemporaryDirectory() as tmp:
            r = dm.draw_mat(plot_type="stream_composition", stream="S10", jobs_root=tmp, dry_run=True)
        self.assertTrue(r["success"])


if __name__ == "__main__":
    unittest.main()
