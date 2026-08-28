"""W40 行为锁:结算屏 stat 帧采集落地(damage_dealt 数据源;W23 定谳的最大数据缺口)。

W23 报告定谳:结算屏无敌方血量通道;「数据统计」面板的己方角色伤害明细是
enemy_hp_after 的最接近语义代理(0/239 未采)。W40 fixture 实锤(win/ended
两态同布局):**面板就在结算屏本体右侧列**——无需点开放大镜子子面板,
``read_round_outcome`` 的同一帧全图 OCR(带坐标)即可解析求和。

纯函数 + read_round_outcome 集成 + battle_loop 接线桩测试;不写真实 .debug
(TelemetryRecorder 指向 tmp_path)。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_performance import RoundOutcome
from sr_od.application.currency_war.cw_settlement_obs import (
    parse_settlement_damage,
    read_round_outcome,
)
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_telemetry import TelemetryRecorder, read_jsonl


class _Item(SimpleNamespace):
    """OCR 结果桩(data/x/y/width/height;坐标取自 fixture 实测 OCR)。"""


@pytest.fixture(autouse=True)
def _no_gold_detail_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    """W414 金币明细采集钩子 no-op:既有 read_round_outcome 锁不落旁路台账
    (测试不写真实 .debug;钩子自身契约在 test_cw_w414_gold_detail_hook.py)。"""
    import sr_od.application.currency_war.cw_settlement_obs as _so
    monkeypatch.setattr(_so, 'collect_gold_detail_hook', lambda *a, **k: None)


def _items(spec: list[tuple[str, int, int, int, int]]) -> list[_Item]:
    return [_Item(data=t, x=x, y=y, width=w, height=h)
            for t, x, y, w, h in spec]


# sr-od-test/screens/货币战争-结算/win.webp 全屏 OCR 实测(token, x, y, w, h)
WIN_FRAME = _items([
    ('挑战成功', 831, 192, 256, 73), ('1-8', 887, 270, 44, 28),
    ('奖励', 981, 269, 55, 30), ('Lv.5', 1110, 367, 85, 66),
    ('4/20', 1127, 427, 55, 25), ('小队命值20i', 646, 479, 226, 43),
    ('获得金币总览', 530, 553, 146, 28), ('10', 1042, 555, 31, 26),
    ('数据统计', 1120, 554, 98, 29), ('基础奖励', 530, 604, 98, 28),
    ('5', 1051, 605, 22, 25), ('试用', 1144, 601, 47, 25),
    ('396.3万', 1198, 635, 81, 25), ('利息', 527, 653, 56, 31),
    ('4', 1057, 660, 13, 17), ('试用', 1144, 678, 48, 26),
    ('连胜×0', 528, 702, 113, 35), ('6.4万', 1196, 712, 58, 26),
    ('掉落晶矿', 528, 771, 100, 32), ('5', 1058, 780, 8, 14),
    ('继续挑战', 910, 878, 100, 31),
])

# ended.webp(挑战结束态)同布局;伤害列 137.0万 + 1.1万
ENDED_DAMAGE = _items([
    ('挑战结束', 831, 191, 257, 73), ('数据统计', 1120, 554, 98, 29),
    ('试用', 1144, 601, 48, 25), ('137.0万', 1198, 635, 80, 25),
    ('试用', 1144, 678, 48, 26), ('1.1万', 1196, 712, 56, 26),
])


# ===== 纯函数:parse_settlement_damage =====

def test_win_fixture_damage_sum() -> None:
    """win.webp 伤害列 396.3万 + 6.4万 → 4027000(左列金币裸数字 10/5/4 不入)。"""
    assert parse_settlement_damage(WIN_FRAME) == 4_027_000


def test_ended_fixture_damage_sum() -> None:
    """ended.webp(挑战结束态)同布局:137.0万 + 1.1万 → 1381000。"""
    assert parse_settlement_damage(ENDED_DAMAGE) == 1_381_000


def test_damage_token_outside_stat_column_ignored() -> None:
    """「万」形 token 落在左列区(位置守卫)→ 不计;全无命中 → None。"""
    items = _items([('6.5万', 600, 650, 50, 25), ('基础奖励', 530, 604, 98, 28)])
    assert parse_settlement_damage(items) is None


def test_no_damage_token_returns_none() -> None:
    """无「万」token(面板不可见/OCR 漏)→ None,不冒认 0。"""
    items = _items([('挑战成功', 831, 192, 256, 73), ('10', 1042, 555, 31, 26)])
    assert parse_settlement_damage(items) is None


# ===== read_round_outcome 集成(同帧产 hp + damage) =====

def _ctx_with_items(items: list[_Item]) -> SimpleNamespace:
    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image, rect=None, crop_first=False: items))


def test_read_round_outcome_produces_damage() -> None:
    """结算帧 → RoundOutcome 同帧产 hp_after=20 + damage_dealt=4027000。"""
    obs = read_round_outcome(_ctx_with_items(WIN_FRAME), None,
                             plane=1, round_num=8, comp_tag='c')
    assert obs.hp_after == 20
    assert obs.damage_dealt == 4_027_000
    assert obs.killed is True


def test_read_round_outcome_damage_none_without_panel() -> None:
    """无伤害行的帧(战斗中/面板被遮)→ damage_dealt=None(旧 schema 默认不破坏)。"""
    items = _items([('挑战成功', 831, 192, 256, 73),
                    ('小队生命值86i', 646, 479, 226, 43)])
    obs = read_round_outcome(_ctx_with_items(items), None,
                             plane=1, round_num=3, comp_tag='c')
    assert obs.damage_dealt is None
    assert obs.hp_after == 86


def test_outcome_record_damage_roundtrip(tmp_path) -> None:
    """OutcomeRecord.damage_dealt 落盘往返;默认行(None)旧锁兼容。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.record_outcome('r1', RoundOutcome(
        round_num=8, plane=1, node_type='奖励', comp_tag='c',
        hp_after=20, hp_confidence=1.0, damage_dealt=4_027_000))
    rec.record_outcome('r1', RoundOutcome(
        round_num=9, plane=1, node_type='boss', comp_tag='c', hp_after=1))
    lines = read_jsonl(tmp_path / 'outcomes.jsonl')
    assert lines[0]['damage_dealt'] == 4_027_000
    assert lines[1]['damage_dealt'] is None


# ===== battle_loop 接线(结算帧 → record_outcome 携带 damage_dealt) =====

def test_loop_outcome_carries_damage(monkeypatch) -> None:
    """分支3 路径:真实 read_round_outcome(不桩)喂 win 形帧 → 遥测行带 damage。"""
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []
    monkeypatch.setattr(bl.cw_telemetry, 'record_outcome',
                        lambda outcome, source='': captured.append(
                            {'outcome': outcome, 'source': source}))
    monkeypatch.setattr(bl.cw_telemetry, 'record_exogenous',
                        lambda *a, **k: None)
    monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, screen: (1, 8))

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._iter = 1
            self._summary_written = False
            self._is_new_match = True
            self._run_start_ts = time.monotonic() - 9999.0   # 超宽限:正常行
            self._first_settlement_seen = False
            self._settle_page1_progress = None
            self._last_outcome_t = None
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(target_comp=None,
                                            last_state=GameState(),
                                            last_hp=None),
                    strategy=SimpleNamespace(on_round_end=lambda *a, **k: None),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None,
                    color_range=None, crop_first=False: WIN_FRAME),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    op = _Loop()
    op._record_round_outcome(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == ''
    assert captured[0]['outcome'].damage_dealt == 4_027_000
    assert captured[0]['outcome'].round_num == 8


def test_branch3_records_before_continue_click() -> None:
    """弱锁:分支3 采样点在「继续挑战」点击前(结算停留期先读后点)。"""
    import inspect

    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop.loop)
    i_read = src.index('_record_round_outcome(screen)')
    i_click = src.index("round_by_find_and_click_area(self.screenshot(), "
                        "'货币战争-结算', '按钮-继续挑战'")
    assert i_read < i_click
