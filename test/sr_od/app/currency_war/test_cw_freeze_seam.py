"""T-171 批序 3:冻结接缝单帧锁(命题 1b form_ok 冻结,ADR-0616 §2.2)。

出处(全部设计定义量,零拟合常数):
- 设计正本 = ADR-0616(docs/develop/currency_war/decisions/
  0616-t166-pair-direction-predicate-ontology.md)§2.2 命题 1b:F 状态机
  (置位=事件闩 / 冻结抑制重派生 / 解冻闭集 p1_pair 域恰三项 / 外部清除
  ⟹F 同帧归 0 ⟹ F=1⟹对非空不变式 / 再闩封印防逐帧空转环);
- 实施批 = T-171 批序 3(冻结接缝落码批;文件面 = kernel/cw_intention.py);
- §12.13 联审(A/T-166 接口项)= ADR-0613 偏开分量处置,见本批交付报告
  与 ADR-0613 §中间态申报(本锁文件不承载联审结论)。

锁面分布(按被锁语义):
- TestFreezeLatch:置位=事件闩(非空+fp≥1.0 才闩;空对/半成品不闩);
- TestFreezeHold:冻结抑制重派生 + fp 回落不清位(闭集外解冻必无——
  「注入第四出口」变异的靶锁);
- TestOverwindowExit:解冻闭集出口①「面③超窗出口」(E>R_rem 同帧解冻
  +在任保持帧对保持+再闩封印环);
- TestUnfreezeClosedSet:闭集出口②位面末(exit_p1)/③comp 锁定取代
  (_lock)+ F=1⟹对非空不变式(写点全集扫描)。

变异红证(亲测记录,红后已还原,零残留):
- M4 注入第四出口(重派生 fp 回落分支加 ist.p1_pair_frozen=False)
  → test_fp_fall_does_not_unfreeze 红;
- M3 删超窗出口(注释出口判定块)→ test_exit_fires_on_overwindow 红;
- M0 删置位闩(置位块跳过)→ test_form_ok_frame_latches 红。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)

_PAIR: tuple[str, ...] = ('持续伤害', '列车同行')
_OTHER_PAIR: tuple[str, ...] = ('仙舟', '持续伤害')


def _chars_with_tag(tag: str, k: int) -> list[str]:
    """按注册表标签取前 k 个成员名(禁手抄成员清单——注册表演化自动跟)。"""
    names = [n for n, ch in CHARACTERS.items()
             if tag in (set(ch.factions or ()) | set(ch.flows or ()))]
    return names[:k]


def _bc(names: list[str], star: int = 1) -> list[BenchChar]:
    return [BenchChar(slot=i + 1, char_id=n, star=star)
            for i, n in enumerate(names)]


def _mk_state(board: dict[str, int] | None = None,
              bench: list[str] | None = None,
              deployed: list[str] | None = None,
              plane: int = 1,
              round_num: int = 5,
              gold: int = 10,
              level: int = 5) -> GameState:
    """最小对局帧:board 羁绊计数 + bench/deployed 名单(判据只读这几样)。"""
    st = GameState(gold=gold, level=level, plane=plane,
                   round_num=round_num, hp=100)
    st.board = dict(board or {})
    st.bench = _bc(bench or [])
    st.deployed = _bc(deployed or [])
    return st


def _form_ok_frame(round_num: int = 5) -> GameState:
    """派生对 = _PAIR 且 fp=1.0 的帧:bench 挂两系各 2 成员(支持度双 1.0,
    派生 top-2 = _PAIR)+ board 满两系档(form_progress=1.0)。"""
    bench = (_chars_with_tag('持续伤害', 2) + _chars_with_tag('列车同行', 2))
    return _mk_state(board={'持续伤害': 2, '列车同行': 2},
                     bench=bench, round_num=round_num)


def _drive(state: GameState, ist: ci.IntentionState) -> ci.IntentionState:
    # W6 波3:update_intention 已切容器签名,旧帧经过渡桥装箱。
    return ci.update_intention(board_state_bridge(state), ist)


def _latched_ist(round_num: int = 5) -> tuple[GameState, ci.IntentionState]:
    """已闩状态:跑一帧 form_ok 帧,返回 (该帧 state, ist)。"""
    st = _form_ok_frame(round_num)
    ist = _drive(st, ci.IntentionState())
    assert ist.p1_pair_frozen is True          # 前置:本帧已闩
    assert ist.p1_pair_frozen_pair == _PAIR
    return st, ist


def _assert_invariant(ist: ci.IntentionState) -> None:
    """F=1 ⟹ 对非空 ∧ p1_pair==frozen_pair(不变式,写点全集扫描共用)。"""
    if ist.p1_pair_frozen:
        assert ist.p1_pair_frozen_pair, 'F=1 ⟹ frozen_pair 非空(不变式)'
        assert ist.p1_pair == ist.p1_pair_frozen_pair, \
            'F=1 期间 p1_pair 钉在 frozen_pair(重派生抑制)'


# ===== 置位 = 事件闩 =====

class TestFreezeLatch:
    def test_form_ok_frame_latches(self) -> None:
        """【M0 变异靶】form_ok 帧闩:F=True + frozen_pair=派生对 +
        last_event 冻结分键(p1_pair:freeze:<pair>)。"""
        st = _form_ok_frame()
        ist = _drive(st, ci.IntentionState())
        assert ist.p1_pair == _PAIR
        assert ist.p1_pair_frozen is True
        assert ist.p1_pair_frozen_pair == _PAIR
        assert ist.last_event == 'p1_pair:freeze:' + '+'.join(_PAIR)
        _assert_invariant(ist)

    def test_empty_pair_never_latches(self) -> None:
        """空窗帧(零资产)派生空对 → 永不置位(空对永不置位,§2.2)。"""
        ist = _drive(_mk_state(bench=[]), ci.IntentionState())
        assert ist.p1_pair == ()
        assert ist.p1_pair_frozen is False

    def test_below_form_ok_never_latches(self) -> None:
        """支持度过线但 fp<1.0(board 半成品)→ 不闩(置位判据=fp≥1.0,
        非「方向非空」)。"""
        bench = (_chars_with_tag('持续伤害', 2)
                 + _chars_with_tag('列车同行', 2))
        st = _mk_state(board={'持续伤害': 2, '列车同行': 1}, bench=bench)
        ist = _drive(st, ci.IntentionState())
        assert ist.p1_pair == _PAIR          # 方向已立
        assert ist.p1_pair_frozen is False   # 但未成型不闩


# ===== 冻结抑制 + fp 回落不清位 =====

class TestFreezeHold:
    def test_unfrozen_redispatch_moves_pair(self) -> None:
        """阴性对照:未闩帧资产变化(仙舟支持度并列)→ 派生对照常重派生
        (证明下一条锁的「不动」归因于冻结,非派生器惰性)。"""
        bench = (_chars_with_tag('仙舟', 3) + _chars_with_tag('持续伤害', 2)
                 + _chars_with_tag('列车同行', 2))
        st = _mk_state(board={}, bench=bench)
        ist = _drive(st, ci.IntentionState())
        assert ist.p1_pair == _OTHER_PAIR    # 三系并列,PREF 序取前二

    def test_freeze_suppresses_redispatch(self) -> None:
        """闩后同款资产变化 → p1_pair 钉在 frozen_pair(冻结的是方向,
        重派生被抑制)。"""
        _st, ist = _latched_ist()
        st2 = _mk_state(
            board={},
            bench=(_chars_with_tag('仙舟', 3) + _chars_with_tag('持续伤害', 2)
                   + _chars_with_tag('列车同行', 2)))
        ist2 = _drive(st2, ist)
        assert ist2.p1_pair_frozen is True
        assert ist2.p1_pair == _PAIR         # 未随支持度翻向
        _assert_invariant(ist2)

    def test_fp_fall_does_not_unfreeze(self) -> None:
        """【M4 变异靶】fp 回落(board 退化)不清位——「fp 回落不自动
        清位」= 解冻闭集外零出口的直接断言;注入第四出口(fp 回落解冻)
        变异时本锁红。"""
        _st, ist = _latched_ist()
        st2 = _mk_state(board={'持续伤害': 1},          # 板面退化 fp<1.0
                        bench=_chars_with_tag('持续伤害', 2))
        ist2 = _drive(st2, ist)
        assert ist2.p1_pair_frozen is True    # 闭集外:不清位
        assert ist2.p1_pair == _PAIR
        _assert_invariant(ist2)


# ===== 解冻闭集出口①:面③超窗出口 =====

class TestOverwindowExit:
    def test_overwindow_math_unit_lock(self) -> None:
        """出口数值本体(零 monkeypatch):实现判定 ≡ 规格式
        「非( E 有限 ∧ E≤R_rem )」,R_rem 取 cw_plane_table.r_remaining
        单一源读法;健康帧(dist=0 → E=0)恒不超窗(冻结无害分支)。
        运营域申报(非断言):本注册表 P1 域有限 E 上界 ≈ dist_max/p̄_min
        (列车系 2/0.227≈8.8)< P1 域 R_rem 下界(r9=19)⟹ 自然触发域
        当前为空,出口牙齿依赖注册表演化或读法变更(设计面,归编排者)。"""
        st_healthy = _form_ok_frame()
        over, e_f, r_rem = ci._p1_pair_overwindow(
        _PAIR, board_state_bridge(st_healthy))
        from sr_od.application.currency_war.kernel.cw_plane_table import (
            r_remaining,
        )
        assert r_rem == r_remaining(None, 1, st_healthy.round_num)
        assert over == (not (e_f <= r_rem))  # 规格式逐字
        assert e_f == pytest.approx(0.0)     # dist=0 → 已完成
        assert over is False

    def test_exit_fires_on_overwindow(self, monkeypatch) -> None:
        """【M3 变异靶】出口触发:超窗帧解冻(F=False / frozen_pair=() /
        hold=旧对 / last_event 带出口分键)——出口后本帧重派生照走
        (§2.2 清除后段)。E 数值由 monkeypatch 注入(状态机响应与出口
        数值解耦;数值本体上一锁)。"""
        _st, ist = _latched_ist()
        monkeypatch.setattr(ci, '_p1_pair_overwindow',
                            lambda pair, state, session=None, registry=None:
                            (True, 99.0, 3))
        st2 = _form_ok_frame(round_num=6)
        ist2 = _drive(st2, ist)
        assert ist2.p1_pair_frozen is False
        assert ist2.p1_pair_frozen_pair == ()
        assert ist2.p1_pair_refreeze_hold == _PAIR
        assert 'unfreeze_overwindow' in ist2.last_event

    def test_exit_in_place_hold_keeps_pair_and_event(self, monkeypatch) -> None:
        """出口帧资产未变(重派生=原对,在任保持)→ 对保持 + F=False +
        unfreeze 事件不被重派生覆写(同帧转移链:出口事件保留)。"""
        _st, ist = _latched_ist()
        monkeypatch.setattr(ci, '_p1_pair_overwindow',
                            lambda pair, state, session=None, registry=None:
                            (True, 99.0, 3))
        st2 = _form_ok_frame(round_num=6)    # 资产不变 → 派生=原对
        ist2 = _drive(st2, ist)
        assert ist2.p1_pair == _PAIR         # 在任保持
        assert ist2.p1_pair_frozen is False
        assert ist2.last_event.startswith('p1_pair:unfreeze_overwindow')

    def test_refreeze_seal_cycle(self, monkeypatch) -> None:
        """再闩封印环(§2.2 清除后段:防「出口→解冻→保持→复位→再触发」
        逐帧空转环):出口后同向 form_ok 帧不再闩(段2);fp 回落解封
        (段3);此后再达成=新 form_ok 事件,允许再闩(段4)。"""
        _st, ist = _latched_ist()
        monkeypatch.setattr(ci, '_p1_pair_overwindow',
                            lambda pair, state, session=None, registry=None:
                            (True, 99.0, 3))
        ist = _drive(_form_ok_frame(round_num=6), ist)     # 段1:出口
        assert ist.p1_pair_refreeze_hold == _PAIR
        ist = _drive(_form_ok_frame(round_num=7), ist)     # 段2:同向再达成
        assert ist.p1_pair_frozen is False                 # 封印:不闩
        assert ist.p1_pair_refreeze_hold == _PAIR          # fp 未回落,封印保持
        st_fall = _mk_state(board={'持续伤害': 1},
                            bench=_chars_with_tag('持续伤害', 2))
        ist = _drive(st_fall, ist)                         # 段3:fp 回落
        assert ist.p1_pair_refreeze_hold == ()             # 回落解封
        ist = _drive(_form_ok_frame(round_num=9), ist)     # 段4:再达成
        assert ist.p1_pair_frozen is True                  # 新 form_ok 帧,再闩
        assert ist.p1_pair_frozen_pair == _PAIR
        _assert_invariant(ist)

    def test_direction_switch_releases_seal(self, monkeypatch) -> None:
        """换向解封:出口后资产大变(派生出不同对)→ 封印对旧对不辖
        新方向,新对以 F=0 起步自由评估(域切换不继承冻结)。"""
        _st, ist = _latched_ist()
        monkeypatch.setattr(ci, '_p1_pair_overwindow',
                            lambda pair, state, session=None, registry=None:
                            (True, 99.0, 3))
        ist = _drive(_form_ok_frame(round_num=6), ist)     # 出口,hold=旧对
        bench_swap = (_chars_with_tag('仙舟', 3)
                      + _chars_with_tag('持续伤害', 2))
        st_new = _mk_state(board={'仙舟': 3, '持续伤害': 2}, bench=bench_swap)
        ist = _drive(st_new, ist)
        assert ist.p1_pair_refreeze_hold == ()             # 换向解封
        assert ist.p1_pair == _OTHER_PAIR
        # 新对 form_ok(本帧板满)→ 以 F=0 起步自由评估后照常闩上新对:
        # 封印只辖被解冻的旧对,不辖新方向(封印误辖新对 = 本断言红)。
        assert ist.p1_pair_frozen is True
        assert ist.p1_pair_frozen_pair == _OTHER_PAIR


# ===== 解冻闭集出口②③ + 不变式 =====

class TestUnfreezeClosedSet:
    def test_exit_p1_clears_frozen(self) -> None:
        """出口②位面末:plane 切 2 帧,p1_pair 退场同帧 F 归 0
        (外部清除⟹F 同帧归 0)。last_event 断言说明:exit_p1 后同帧
        P2 移交通道对 vacuum 强制 assignment(handoff_lock)覆盖单值
        last_event——「最近一次转移」既有事件语义;出口行为由四字段
        清零断言 + 移交锁发生(其前提=配方锁已退场的 unlocked 态)承载。"""
        _st, ist = _latched_ist()
        st2 = _mk_state(plane=2, round_num=1, board={}, bench=[])
        ist2 = _drive(st2, ist)
        assert ist2.p1_pair == ()
        assert ist2.p1_pair_frozen is False
        assert ist2.p1_pair_frozen_pair == ()
        assert ist2.p1_pair_refreeze_hold == ()
        assert ist2.locked_comp != '' \
            and ist2.last_event.startswith('handoff_lock:')

    def test_comp_lock_supersedes_clears_frozen(self) -> None:
        """出口③comp 锁定取代:_lock 域退出类清除,三冻结字段同帧归 0
        (冻结保护配方方向不被噪声重派生,不保护已被合法方向替代取代的
        承诺,ADR-0616 §2.2)。"""
        _st, ist = _latched_ist()
        sig = ci.IntentionSignal(3, 'core_card', '专家桑博DOT', '测试', 1.0)
        ci._lock(ist, board_state_bridge(_st), sig)
        assert ist.p1_pair == ()
        assert ist.p1_pair_frozen is False
        assert ist.p1_pair_frozen_pair == ()
        assert ist.p1_pair_refreeze_hold == ()

    def test_invariant_across_scenarios(self, monkeypatch) -> None:
        """F=1 ⟹ frozen_pair≠() ∧ p1_pair==frozen_pair:闩→抑制→回落→
        出口→封印全序列逐帧扫描(写点全集断言,非真子集——§2.2 写点完备
        断言按全集建)。"""
        scenarios: list[list[GameState]] = [
            # 甲:闩后连续资产扰动帧
            [_form_ok_frame(round_num=r) for r in (5, 6, 7)],
            # 乙:闩后回落再回复
            [_form_ok_frame(round_num=5),
             _mk_state(board={'持续伤害': 1},
                       bench=_chars_with_tag('持续伤害', 2)),
             _form_ok_frame(round_num=7)],
            # 丙:出口后封印帧序列
            [_form_ok_frame(round_num=5),
             _form_ok_frame(round_num=6),
             _form_ok_frame(round_num=7)],
        ]
        monkeypatch.setattr(ci, '_p1_pair_overwindow',
                            lambda pair, state, session=None, registry=None:
                            (True, 99.0, 3))
        for frames in scenarios:
            ist = ci.IntentionState()
            for st in frames:
                ist = _drive(st, ist)
                _assert_invariant(ist)
