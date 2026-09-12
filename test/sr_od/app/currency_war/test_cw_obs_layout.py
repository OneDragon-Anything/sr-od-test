"""obs 识别层·后台布局公式与选档(重建合同 ④)。

后台布局是事故响应批的核心产出(W209/run26 崩坏根因),有明确口述真值:
后台格数 = 6+(cap−level),值域 {6..9}(上限 9 = 用户口述 2026-09-11 重申)。
本文件锁:
- 公式纯函数四档对照(值域钳制:负 diff 归 0、域外封顶 9);
- 双通道对账裁决序 decision table(一致采公式/CV 下界不否决/未建档防抖/
  裁决值与坐标档分离 → 8 格超集);
- 布局未知态三键(unknown/frozen/streak,§3.2④ 消费契约)。
CV 通道(std 签名)归真帧锚(合同 ⑤),本文件桩化 CV 读数只锁裁决语义。
组织蓝图 = obs 先删后重建规格 §2④。
"""
import time

import pytest
from sr_od.application.currency_war.obs import cw_back_layout as cbl


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """全局状态清零 + 遥测静音:选档主链的裁决值不被记账侧干扰。"""
    cbl.reset_layout_unknown_state()
    monkeypatch.setattr(cbl, 'note_channel_conflict', lambda *a, **k: None)
    monkeypatch.setattr(time, 'sleep', lambda s: None)   # 防抖重读不真等
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_observe.obs_conflict',
        lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_telemetry_exit.record_defect',
        lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_telemetry_exit.'
        'record_back_layout_unknown', lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_telemetry_exit.'
        'record_back_layout_divergence', lambda *a, **k: None)


class TestCapDiffFormula:
    """口述公式:后台格数 = 6+(cap−level),值域 {6..9}(负归 0/域外封顶 9)。"""

    def test_diff0_is_baseline(self):
        assert cbl.back_slots_from_cap_diff(0) == 6

    def test_diff1_seven_archived(self):
        # diff==1 → 7 格已建档直读(2026-08-26 佩佩局交互实锤)
        assert cbl.back_slots_from_cap_diff(1) == 7

    def test_diff2_eight(self):
        # diff 2 → 8 格(狸猫局交互实拍,393-1529 带)
        assert cbl.back_slots_from_cap_diff(2) == 8

    def test_diff3_capped_at_nine(self):
        # 上限 9 = 用户口述真值(宝钻/召唤物扩展封顶;e4972b43 diff=5 实拍 9 格)
        assert cbl.back_slots_from_cap_diff(3) == 9

    def test_out_of_domain_clamped_to_nine(self):
        assert cbl.back_slots_from_cap_diff(5) == 9

    def test_negative_diff_treated_as_zero(self):
        # cap<level = 读错族(cw_screen_prep 另有留证),公式侧按无扩展
        assert cbl.back_slots_from_cap_diff(-1) == 6


class TestSelectBackLayoutDecisionTable:
    """双通道对账裁决序:一致采公式/冲突不对称/CV 未建档防抖/9→8 超集。"""

    def test_agree_takes_formula(self, monkeypatch):
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: 6)
        r = cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5)
        assert r['n'] == 6
        assert r['prefix'] == cbl._LAYOUT_PREFIX[6]
        assert r['unknown'] is False

    def test_cv_above_formula_adopts_cv(self, monkeypatch):
        # 冲突 ∧ paddle 不可得(ctx=None):cv>formula = 两端整格结构证据 → 采 CV
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: 8)
        r = cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5)
        assert r['n_raw'] == 8
        assert r['n'] == 8

    def test_cv_below_formula_does_not_veto(self, monkeypatch):
        # cv<formula = 下界读数(端点切片/失明非「无格」证据)→ 采公式
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: 6)
        r = cbl.resolve_back_slots(None, _SCREEN, level=5, cap=7)
        assert r['formula_n'] == 8
        assert r['n_raw'] == 8
        assert r['n'] == 8

    def test_unarchived_cv_reading_debounced_to_formula(self, monkeypatch):
        # CV 读出未建档档(9 ∉ {6,7,8}):三次一致才采;ctx=None 重读不可得
        # → 瞬态自愈退公式 + 重读序列留证(cv_readings)
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: 9)
        r = cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5)
        assert r['cv_readings'] == [9, None, None]
        assert r['cv_n'] is None
        assert r['n'] == 6   # 退公式值

    def test_ruling_value_9_runs_as_8_superset(self):
        # 裁决值与坐标档分离:diff=3 → 裁决 9(真实档),坐标未建档 → 运行 8 格
        # 超集(扩展带读全不丢系统单位;拖到不存在格被游戏拒 = 廉价失败方向)
        r = cbl.resolve_back_slots(None, None, level=5, cap=8)
        assert r['formula_raw'] == 9
        assert r['n_raw'] == 9
        assert r['n'] == 8
        assert r['prefix'] == cbl._LAYOUT_PREFIX[8]

    def test_screen_none_cv_abstains_formula_baselined(self):
        # CV 不可判(screen None)→ 公式值兜底(diff=0 → 6 档基线)
        r = cbl.resolve_back_slots(None, None, level=4, cap=4)
        assert r['cv_n'] is None
        assert r['n'] == 6


class TestLayoutUnknownState:
    """布局未知态(双弃权):单帧跳过后排依赖/连续冻结止损;已知帧解冻。"""

    def test_double_abstain_is_unknown_not_baseline(self, monkeypatch):
        # level_trusted=False(公式弃权)+ CV 不可判 → 双弃权:
        # n=None/prefix=''——禁把空串前缀静默当 6 档基线(缺省化复发防线)
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: None)
        r = cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5,
                                   level_trusted=False)
        assert r['unknown'] is True
        assert r['n'] is None
        assert r['prefix'] == ''

    def test_unknown_streak_accumulates_and_freezes(self, monkeypatch):
        # 连续未知达 UNKNOWN_FREEZE_FRAMES(3)= 写类冻结止损
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: None)
        for i in (1, 2, 3):
            r = cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5,
                                       level_trusted=False)
            assert r['unknown_streak'] == i
        assert r['frozen'] is True

    def test_known_frame_resets_streak(self, monkeypatch):
        # 任一已知帧清零复位(= 干净裁决解冻)
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: None)
        cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5, level_trusted=False)
        cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5, level_trusted=False)
        monkeypatch.setattr(cbl, 'cv_back_slots', lambda screen: 6)
        r = cbl.resolve_back_slots(None, _SCREEN, level=5, cap=5)
        assert r['unknown'] is False
        assert r['unknown_streak'] == 0
        assert r['frozen'] is False


class TestLayoutRegistry:
    """布局档登记面:screen_info 建档变更后同步登记的清点门(被动更新型)。"""

    def test_archived_tiers(self):
        # 在册档 = {6,7,8}:9 档坐标未交互建档(单帧剖面/无实锤不登记,
        # 勿重蹈 ADR-0281 幻影档覆辙);新增档须先交互实锤再入表
        assert set(cbl._layout_prefixes().keys()) == {6, 7, 8}

    def test_fallback_baseline_six_slots(self):
        # 无 ctx/无档兜底:静态 6 槽基线(与 screen_info 基线一致)
        assert len(cbl.fallback_back_slots()) == 6


_SCREEN = object()   # 桩化 CV 后 screen 不承载像素,占位即可
