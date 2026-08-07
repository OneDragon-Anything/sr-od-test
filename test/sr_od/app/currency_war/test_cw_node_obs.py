"""货币战争 节点选项观测(遭遇/…)reader 测试 —— 纯逻辑(喂 mock OCR map)。

验证 ``read_encounter_options`` 解析:标题「遭遇其X」→ difficulty(X 漏读→1)、reward 按带 + x 归卡、
左→右 idx。不依赖真 OCR(快);真 OCR 行为由 offline baseline probe 核实(见 process_log D-91)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.cw_node_obs import read_encounter_options


def _ocr_map(items: list[tuple[str, int, int]]) -> dict:
    """构造 mock ocr_map:text → {max: {center: {x,y}}}。"""
    return {
        t: SimpleNamespace(max=SimpleNamespace(center=SimpleNamespace(x=cx, y=cy)))
        for t, cx, cy in items
    }


class _FakeCtx:
    def __init__(self, m: dict) -> None:
        self.ocr_service = SimpleNamespace(
            get_ocr_result_map=lambda **kw: m,
        )


def test_read_encounter_options_baseline_layout() -> None:
    """baseline 实测 OCR(2026-08-07):左卡=其一(「一」漏读→「遭遇其」)、右卡=其四 + 各自奖励。"""
    m = _ocr_map([
        ('遭遇其', 655, 389),        # 左卡(其一,「一」笔画细被漏 → 无数字)
        ('遭遇其四', 1251, 389),     # 右卡(其四)
        ('奖励预览', 655, 580),
        ('奖励预览', 1251, 580),
        ('金币', 640, 646),          # 左奖励
        ('随机4费角色', 1263, 647),  # 右奖励
        ('2', 601, 672),             # 数量(<2 字,过滤)
        ('3', 1187, 672),
        ('选择', 1081, 898),
    ])
    opts = read_encounter_options(_FakeCtx(m), None)
    assert len(opts) == 2
    assert opts[0].idx == 0 and opts[0].difficulty == 1 and opts[0].rewards == ['金币']
    assert opts[1].idx == 1 and opts[1].difficulty == 4 and opts[1].rewards == ['随机4费角色']


def test_read_encounter_options_no_cards_returns_empty() -> None:
    """无「遭遇其X」标题(非遭遇屏)→ [](handler 退默认 idx0)。"""
    opts = read_encounter_options(_FakeCtx({}), None)
    assert opts == []


def test_read_encounter_options_ignores_zaojie_node_label() -> None:
    """「遭遇节点」(屏标题)不含「其」→ 不误当卡。"""
    m = _ocr_map([('遭遇节点', 960, 96), ('选择', 1081, 898)])
    assert read_encounter_options(_FakeCtx(m), None) == []


def test_read_encounter_options_reward_assigned_by_nearest_x() -> None:
    """奖励按 x 就近归卡(左卡奖励归左、右归右),不按行索引。"""
    m = _ocr_map([
        ('遭遇其二', 400, 389),
        ('遭遇其五', 1200, 389),
        ('奖励预览', 400, 580),
        ('奖励预览', 1200, 580),
        ('装备', 410, 646),
        ('晶矿', 1190, 646),
    ])
    opts = read_encounter_options(_FakeCtx(m), None)
    assert opts[0].difficulty == 2 and opts[0].rewards == ['装备']
    assert opts[1].difficulty == 5 and opts[1].rewards == ['晶矿']
