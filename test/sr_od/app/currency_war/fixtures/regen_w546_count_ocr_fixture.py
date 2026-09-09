"""一次性生成 w546 数量锁的识别结果 fixture(录制真引擎输出,按裁片内容哈希键控)。

用法(主仓根,需真机 OCR 环境):
  $env:PYTHONPATH="src"; uv run python -X utf8 sr-od-test/test/sr_od/app/currency_war/fixtures/regen_w546_count_ocr_fixture.py
产物: 同目录 w546_count_ocr_fixture.json
内容:每代表帧 → 目标格 TM 峰心(真 read_equip_grid 输出)+ 数量裁片 → 真引擎原文表。
录制路径与 test_cw_equip_grid.TestEquipCount 的回放路径完全一致;
裁片内容变 → 哈希变 → 回放未命中 = 失读,与真引擎对错裁片失读同语义。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'sr-od-test' / 'test' / 'sr_od' / 'app' / 'currency_war'))

import test_cw_equip_grid as t  # noqa: E402

from sr_od.application.currency_war.obs.cw_equipment import (  # noqa: E402
    read_equip_count,
)

# 与测试内 case 表一致:(帧, 装备名, 列 x, 期望)
CASES = [('攻略已应用', '拆装扳手', 1847, '4'), ('shop_closed', '精密拆装扳手', 1843, '∞')]


class Recorder:
    """包真 OcrService:逐裁片哈希 → 真引擎调用 → 记录返回的原文列表。"""

    def __init__(self) -> None:
        from one_dragon.base.matcher.ocr.ocr_service import OcrService
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        self.svc = OcrService(ocr_matcher=OnnxOcrMatcher())
        self.svc.ocr_matcher.init_model()
        self.table: dict[str, list[str]] = {}

    def get_ocr_result_list(self, image, **_kw):
        key = hashlib.md5(np.ascontiguousarray(image).tobytes()).hexdigest()
        results = self.svc.get_ocr_result_list(image=image)
        self.table[key] = [getattr(r, 'data', None) or '' for r in (results or [])]
        return results


def main() -> None:
    templates = t._templates()
    fixture: dict[str, dict] = {}
    for frame, eq_name, col_x, expect in CASES:
        rgb = t._load_frame(frame)
        assert rgb is not None, f'帧缺失: {frame}'
        cells = t.read_equip_grid(rgb, templates)  # 一次性真识别,取 TM 峰心
        target = [c for c in cells if c.name == eq_name
                  and abs(c.cx - col_x) <= 40 and c.row == 0]
        assert len(target) == 1, f'{frame} {eq_name} 命中 {len(target)} 格'
        rec = Recorder()
        ctx = SimpleNamespace(ocr_service=rec)
        count = read_equip_count(ctx, rgb, target[0].cx, target[0].cy)
        assert count == expect, f'{frame} {eq_name}: expect={expect} got={count}'
        print(f'{frame}: cell=({target[0].cx},{target[0].cy}) count={count} ocr_calls={len(rec.table)}')
        fixture[frame] = {'cell': [target[0].cx, target[0].cy], 'ocr': rec.table}
    out = REPO / 'sr-od-test' / 'test' / 'sr_od' / 'app' / 'currency_war' / 'fixtures' / 'w546_count_ocr_fixture.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixture, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'written: {out}')


if __name__ == '__main__':
    main()
