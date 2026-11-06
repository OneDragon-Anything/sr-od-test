"""遭遇选档决策单帧测试(能力态直通形;判据语义 =
 §2.2-§2.5,
;验收锚点 = design §2.12 锚点 1-6
+ 立场重拍回退态(design §2.2/§2.3)。

测试语义不写巧合:断言「这段判据应该怎么表现」(窗口普战口径、κ_S 三态、
边缘 cap、经验档层、tiebreak 档序、刷新阀两臂、重拍回退、注入面),
不断言具体卡面;reason 仅断言 design §2.2 明文的归因串与因词封闭枚举
(判读侧契约)。

测试纪律:零真实副作用(纯函数 + 自造输入 + 提交进仓的注册表数据);
结算环行经生产单一写端 record_settlement_row 构造(与生产同口)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_encounter_selection import (
    record_settlement_row,
)
from sr_od.application.currency_war.kernel.cw_events import EncounterOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    encounter_pick,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.encounter_pick import (
    EncounterPickDecision,
    EncounterRefreshSuggestion,
)

_SIG = ChannelSig(family='logic_action', actor='cw-encounter-pick-test',
                  mode='compute')
_PB = 'cw-encounter-pick-test'


# ==================== 构造器 ====================

def _fresh_gs() -> GameState:
    """独立状态容器(桩 session 宿主;弱引用表按宿主隔离,零跨测残留)。"""
    return game_state_of(SimpleNamespace())


def _opt(idx: int, difficulty: int,
         rewards: list[str] | None = None) -> EncounterOption:
    return EncounterOption(idx=idx, difficulty=difficulty, affixes=[],
                           rewards=rewards or [])


def _row(gs: GameState, plane: int, round_num: int, node_type: str,
         killed: bool | None, encounter_tier: int | None = None,
         fill: float | None = None) -> None:
    """结算行入环(生产单一写端;outcome 分支桩最小面,hp_after = None
    读缺形态——本文件断言面是窗口/经验读口,不消费 hp 差分)。"""
    record_settlement_row(
        gs, SimpleNamespace(killed=killed, progress_fill_ratio=fill,
                            hp_after=None),
        plane=plane, round_num=round_num, node_type=node_type,
        difficulty_node=None, encounter_tier=encounter_tier)


def _win_window(gs: GameState, new_killed: bool | None = True) -> None:
    """P1 遭遇决策帧(r7)的窗口构造:r4/r6 两场普战,r4 全胜、r6 缺省
    全胜(改 new_killed 构造边缘/不足帧;fill 恒 None = 分支不激活)。"""
    _row(gs, 1, 4, '普通战斗', True)
    _row(gs, 1, 6, '普通战斗', new_killed)


def _set_left(gs: GameState, left: int) -> None:
    """写遭遇刷新剩余次数(状态容器观察真值形态;不写 = None 未观察)。"""
    gs.write_logic(gs.encounter_refresh_left, left, produced_by=_PB, sig=_SIG)


# ==================== 锚点 1:足量帧选最高可及档 ====================

def test_sufficient_frame_picks_highest_reachable_tier():
    """锚点 1:窗口两场全胜 → κ_S 足量 → 难度最高可及档胜出(t ≤ 4
    能力态直判);reason 照 design §2.2 归因串。"""
    gs = _fresh_gs()
    _win_window(gs)
    out = encounter_pick.decide([_opt(0, 1), _opt(1, 3)], gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1
    assert out.reason == 'e3-simple|pick:t3|kappa=足量'


# ==================== 锚点 2:边缘帧 cap ====================

def test_edge_frame_caps_reachable_at_two():
    """锚点 2:恰一胜 → 边缘态难度上限 = 立场常量 EDGE_CAP(其三不可及);
    另一场删失(None)同归边缘(删失分支,非不足);cap 过滤在前——其五
    即使有经验正证据也被排除(边缘态 t ≥ 3 全排除,含五/六)。"""
    # 败局臂:另一场败局(fill 槽 None → fill 分支不激活)→ 边缘
    gs = _fresh_gs()
    _win_window(gs, new_killed=False)
    out = encounter_pick.decide([_opt(0, 2), _opt(1, 3)], gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 0
    assert out.reason == 'e3-simple|pick:t2|kappa=边缘'
    # 删失臂:另一场删失 → 边缘
    gs2 = _fresh_gs()
    _win_window(gs2, new_killed=None)
    out = encounter_pick.decide([_opt(0, 2), _opt(1, 3)], gs2)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 0
    # cap 过滤在前:其五有 killed=True 经验行,边缘态下仍全排除
    gs3 = _fresh_gs()
    _win_window(gs3, new_killed=False)
    _row(gs3, 1, 3, '遭遇', True, encounter_tier=5)
    out = encounter_pick.decide([_opt(0, 1), _opt(1, 5)], gs3)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 0, '边缘态 cap 过滤在前:其五即使经验层放行也被排除'


# ==================== 锚点 3:不足帧刷新阀两臂 ====================

def test_insufficient_frame_refresh_valve_two_arms():
    """锚点 3:κ_S 不足 → 可及集空:剩余 ≥1 → 建议刷;剩余 0/None
    (未观察,fail-closed)→ 落最低档(dark-fallback 因词;最低档按
    difficulty 取,与列表位置无关)。"""
    # 两场全败 → 不足;有次数 → 刷
    gs = _fresh_gs()
    _row(gs, 1, 4, '普通战斗', False)
    _row(gs, 1, 6, '普通战斗', False)
    _set_left(gs, 1)
    out = encounter_pick.decide([_opt(0, 1), _opt(1, 3)], gs)
    assert isinstance(out, EncounterRefreshSuggestion)
    assert out.reason == 'e3-simple|refresh-valve:kappa-不足'
    # 刷尽 → 最低档(候选序 [t3, t1] 验证按 difficulty 取下标 1)
    gs2 = _fresh_gs()
    _row(gs2, 1, 4, '普通战斗', False)
    _row(gs2, 1, 6, '普通战斗', False)
    _set_left(gs2, 0)
    out = encounter_pick.decide([_opt(0, 3), _opt(1, 1)], gs2)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1
    assert out.reason == 'e3-simple|dark-fallback:kappa-不足'
    # 剩余未观察(None)→ fail-closed 同臂
    gs3 = _fresh_gs()
    _row(gs3, 1, 4, '普通战斗', False)
    _row(gs3, 1, 6, '普通战斗', False)
    out = encounter_pick.decide([_opt(0, 3), _opt(1, 1)], gs3)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1
    # 一败一删失 → 不足(三态表支)
    gs4 = _fresh_gs()
    _row(gs4, 1, 4, '普通战斗', False)
    _row(gs4, 1, 6, '普通战斗', None)
    _set_left(gs4, 1)
    out = encounter_pick.decide([_opt(0, 1)], gs4)
    assert isinstance(out, EncounterRefreshSuggestion)


# ==================== 锚点 4:其五/六仅经验层放行 ====================

def test_tier5_6_gated_by_experience_evidence():
    """锚点 4:足量态下其五/六无经验正证据不可及;本局该档存在
    killed=True 遭遇行 → 可及且按主序胜出;败局行不算正证据。"""
    gs = _fresh_gs()
    _win_window(gs)
    out = encounter_pick.decide([_opt(0, 3), _opt(1, 5), _opt(2, 6)], gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 0, '无经验行:其五/六不可及,落其三'
    # tier5 正证据 → 可及(5 > 3 按主序胜出)
    _row(gs, 1, 3, '遭遇', True, encounter_tier=5)
    out = encounter_pick.decide([_opt(0, 3), _opt(1, 5), _opt(2, 6)], gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1
    assert out.reason == 'e3-simple|pick:t5|kappa=足量'
    # tier6 仅败局行 → 非正证据,不可及,仍 t5
    _row(gs, 1, 5, '遭遇', False, encounter_tier=6)
    out = encounter_pick.decide([_opt(0, 3), _opt(1, 5), _opt(2, 6)], gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1


# ==================== 锚点 5:同档并列 tiebreak ====================

def test_same_tier_tiebreak_preference_order():
    """锚点 5:同档并列按奖励偏好档序(钻 > 装备 > 金币 > 末档,小 = 优);
    档序仍并列 → 输入序先。奖励文本用注册表真名(火力风暴潮 ∈
    EQUIPMENT_ROSTER)/钻字面(红钻 ∈ 检测集)/金币字面构造。"""
    gs = _fresh_gs()
    _win_window(gs)
    opts = [_opt(0, 2, ['未知之匣']),      # 末档(映射不到)
            _opt(1, 2, ['金币×2']),        # 金币档
            _opt(2, 2, ['火力风暴潮']),    # 装备档(注册表真名)
            _opt(3, 2, ['红钻×1'])]        # 钻档(检测集子串命中)
    out = encounter_pick.decide(opts, gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 3, '钻档优先'
    # 无钻帧:装备 > 金币 > 末档
    opts2 = [_opt(0, 2, ['未知之匣']), _opt(1, 2, ['金币×2']),
             _opt(2, 2, ['火力风暴潮'])]
    out = encounter_pick.decide(opts2, gs)
    assert isinstance(out, EncounterPickDecision) and out.idx == 2
    opts3 = [_opt(0, 2, ['未知之匣']), _opt(1, 2, ['金币×2'])]
    out = encounter_pick.decide(opts3, gs)
    assert isinstance(out, EncounterPickDecision) and out.idx == 1
    # 档序并列(同末档)→ 输入序先(EncounterOption.idx 小者)
    opts4 = [_opt(0, 2, ['未知之匣']), _opt(1, 2, ['谜之馈赠'])]
    out = encounter_pick.decide(opts4, gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 0


# ==================== 锚点 6:窗口普战口径 ====================

def test_window_counts_last_two_normal_battles_only():
    """锚点 6:窗口 = 最近 2 个普通战斗行(普战口径,design §2.2 候选 A)
    ——奖励行/遭遇行不入窗:两者 killed 为删失/败局,若误入窗会压 κ 降档,
    本帧须仍判足量选其三(误入窗即红)。"""
    gs = _fresh_gs()
    _row(gs, 1, 4, '普通战斗', True)
    _row(gs, 1, 5, '奖励', None)          # 奖励行:不入窗
    _row(gs, 1, 6, '普通战斗', True)
    out = encounter_pick.decide([_opt(0, 1), _opt(1, 3)], gs)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1
    assert out.reason == 'e3-simple|pick:t3|kappa=足量', \
        '奖励行不入窗:窗口 = r4/r6 两场普战全胜'
    # 同位面遭遇行(败局)亦不入窗
    gs2 = _fresh_gs()
    _row(gs2, 1, 4, '普通战斗', True)
    _row(gs2, 1, 5, '遭遇', False, encounter_tier=3)
    _row(gs2, 1, 6, '普通战斗', True)
    out = encounter_pick.decide([_opt(0, 1), _opt(1, 3)], gs2)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1, '遭遇行不入窗:普战口径维持足量判'


# ==================== 锚点 7:窗口不足独立态与因词 ====================

def test_window_insufficient_is_distinct_state_with_own_cause():
    """锚点 7:窗口 < 2 普战行 = 独立态(数据不足 ≠ κ_S 能力不足),
    因词 window-insufficient 与 kappa-不足 分因可判读;阀两臂同锚点 3。"""
    gs = _fresh_gs()   # 空环
    _set_left(gs, 1)
    out = encounter_pick.decide([_opt(0, 1)], gs)
    assert isinstance(out, EncounterRefreshSuggestion)
    assert out.reason == 'e3-simple|refresh-valve:window-insufficient'
    # 无次数 → dark-fallback 同因词落最低档
    gs2 = _fresh_gs()
    out = encounter_pick.decide([_opt(0, 3), _opt(1, 1)], gs2)
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 1
    assert out.reason == 'e3-simple|dark-fallback:window-insufficient'
    # 单行环(1 < 2)同态
    gs3 = _fresh_gs()
    _row(gs3, 1, 4, '普通战斗', True)
    _set_left(gs3, 1)
    out = encounter_pick.decide([_opt(0, 1)], gs3)
    assert isinstance(out, EncounterRefreshSuggestion)
    assert out.reason == 'e3-simple|refresh-valve:window-insufficient'


# ==================== 锚点 8:立场重拍回退态 ====================

def test_stance_none_falls_back_to_lowest_tier_zero_refresh(monkeypatch):
    """锚点 8(重拍回退机制,design §2.2/§2.3):立场常量任一置 None →
    恒最低档零刷新(dark-fallback:stance-unconfirmed)——即使窗口足量、
    可及集非空、刷新次数在场也不评估。"""
    opts = [_opt(0, 3), _opt(1, 1)]
    for attr in ('EDGE_CAP', 'REWARD_ORDER_APPROVED'):
        gs = _fresh_gs()
        _win_window(gs)
        _set_left(gs, 1)
        monkeypatch.setattr(encounter_pick, attr, None)
        out = encounter_pick.decide(opts, gs)
        assert isinstance(out, EncounterPickDecision)
        assert out.idx == 1, f'{attr} 置 None:恒最低档(t1,下标 1)'
        assert out.reason == 'e3-simple|dark-fallback:stance-unconfirmed'


# ==================== 注入面(fill 双键)与 fill 分支激活 ====================

def test_calibration_face_fill_dual_keys_and_fill_branch():
    """注入面(design §2.3):合法键 = fill 双键;未知键抛错(kernel 侧
    D_ENC_VARIANT 键在本口即未知——两注入口互不可见);非 None 不覆盖
    (幂等);reset 清场。双槽注入后败局 fill 分支激活:fill < 阈值 →
    不足 → 阀,fill ≥ 阈值(边界 0.5 取等不降档)→ 边缘;reset 后回到
    不激活(败局臂恒边缘)。"""
    encounter_pick.apply_calibration(PROGRESS_BAR_DIRECTION='forward')
    try:
        # 非 None 不覆盖(幂等)
        encounter_pick.apply_calibration(PROGRESS_BAR_DIRECTION='inverted')
        assert encounter_pick.PROGRESS_BAR_DIRECTION == 'forward'
        encounter_pick.apply_calibration(BAR_SEMANTICS='node')
        # 未知键抛错(含 kernel 专属键)
        with pytest.raises(KeyError):
            encounter_pick.apply_calibration(D_ENC_VARIANT='ii')
        # fill 分支激活:恰一胜 + 败局 fill 0.3 < 0.5 → 不足 → 阀
        gs = _fresh_gs()
        _row(gs, 1, 4, '普通战斗', True)
        _row(gs, 1, 6, '普通战斗', False, fill=0.3)
        _set_left(gs, 1)
        out = encounter_pick.decide([_opt(0, 1)], gs)
        assert isinstance(out, EncounterRefreshSuggestion)
        assert out.reason == 'e3-simple|refresh-valve:kappa-不足'
        # fill 0.5(取等不降档)→ 边缘
        gs2 = _fresh_gs()
        _row(gs2, 1, 4, '普通战斗', True)
        _row(gs2, 1, 6, '普通战斗', False, fill=0.5)
        out = encounter_pick.decide([_opt(0, 2), _opt(1, 3)], gs2)
        assert isinstance(out, EncounterPickDecision)
        assert out.idx == 0
        assert out.reason == 'e3-simple|pick:t2|kappa=边缘'
        # reset 清场 → fill 分支不激活(败局臂恒边缘,fill 不再看)
        encounter_pick.reset_calibration()
        assert encounter_pick.PROGRESS_BAR_DIRECTION is None
        assert encounter_pick.BAR_SEMANTICS is None
        gs3 = _fresh_gs()
        _row(gs3, 1, 4, '普通战斗', True)
        _row(gs3, 1, 6, '普通战斗', False, fill=0.3)
        out = encounter_pick.decide([_opt(0, 2), _opt(1, 3)], gs3)
        assert isinstance(out, EncounterPickDecision)
        assert out.idx == 0, '未定论:fill 分支不激活,败局臂恒边缘'
    finally:
        encounter_pick.reset_calibration()


# ==================== 空候选帧 ====================

def test_empty_options_frame_returns_no_options():
    """空候选帧 idx=0 no-options(纯函数定义完备;现役观察层守卫下
    不可达,design §2.2)。"""
    out = encounter_pick.decide([], _fresh_gs())
    assert isinstance(out, EncounterPickDecision)
    assert out.idx == 0
    assert out.reason == 'no-options'
