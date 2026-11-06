"""sim 遭遇呈现集收窄测试(镜像 src = sim/cw_sim_backend.py 的
encounter_options_for helper + encounter 呈现写点 + STRATEGY_ECONOMY
『二极管』三条效果条目注册行)。

测试面依据 = 迭代设计 designs/T-133-erjiguan.md §4 + REVIEW-T133 实现
要点摘要 §④ 三锁:
- 锁 1 助手谓词:持卡收窄 = 全档首尾两元素(派生式断言,不硬编档数,
  防 U22 档数校准时锁双源)+ idx 重排 [0,1];未持有/空名单/非本卡/
  表外名 → 全四档原样;多策略含本卡 → 仍收窄(任一命中即收窄,局级
  持续语义);
- 锁 2 写点集成:backend 局预种持卡(observe 写入;选卡落地链 = 按名
  去重追加,预种不被后续 pick 覆写)走到遭遇节点 → 容器呈现集长度 2 ∧
  difficulty 集 = {全集首, 全集末} ∧ idx 集 = {0,1}(全派生式),
  观察生成器(gen_encounter 容器回读链)与容器一致;
- 锁 3 注册行直测:STRATEGY_ECONOMY['二极管'] 直读三条效果条目值(instant_gold
  ==6 ∧ hp_instant==10 ∧ encounter_tier_extremes_only is True,防表外
  安静返 0/注册笔误,T-121 注册行直测先例);hp 腿直调真值 + 表外卡
  零写(apply_strategy_pick_hp 通用腿直调,照 T-127
  test_strategy_pick_hp.py 形态)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(在册超限
拆分债文件,禁追加,只 import 复用不改)。
"""
from __future__ import annotations

import random

from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG_OBS,
    _backend,
    _open_to_first_window,
    _walk_to,
)

from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_ENCOUNTER,
    SimBackend,
    apply_strategy_pick_hp,
    encounter_options,
    encounter_options_for,
    uninstall_backend,
)

#: 本卡注册键(卡面 id 103802;注册面单一源 = cw_investments.
#: STRATEGY_ECONOMY)。
_CARD = '二极管'

#: hp 即时腿独立笔 evidence 前缀(单一源 = cw_sim_base.sim_evidence
#: 契约:前缀 sim:engine: + 写点 tag hp:strategy_pick:<卡名>)。
_HP_EV_PREFIX = 'sim:engine:hp:strategy_pick:'


# ============================================================ 锁 1 助手谓词

def test_held_card_narrows_to_derived_extremes_with_idx_rebuild() -> None:
    """持卡收窄:全集首尾两元素 ∧ idx 重排 [0,1](端点/难度全派生式
    断言,不硬编 1/4——U22 档数校准时零联动);非端点载荷随源条目
    携带,收窄不重写 rewards。"""
    full = encounter_options()
    narrowed = encounter_options_for([_CARD])
    assert len(narrowed) == 2
    assert (narrowed[0].difficulty, narrowed[-1].difficulty) == \
        (full[0].difficulty, full[-1].difficulty)
    assert [o.idx for o in narrowed] == [0, 1]
    assert narrowed[0].rewards == full[0].rewards
    assert narrowed[-1].rewards == full[-1].rewards


def test_unheld_or_nonmember_returns_full_set_unchanged() -> None:
    """未持有/空名单/非本卡(在册无旗标卡 + 表外名)→ 全四档原样,
    零收窄(负例:读法 miss 安静回全集,不抛不窄)。"""
    full = encounter_options()
    assert encounter_options_for([]) == full
    assert encounter_options_for(['躺平']) == full
    assert encounter_options_for(['不在册卡名']) == full


def test_multi_strategy_any_hit_still_narrows() -> None:
    """多策略含本卡 → 仍收窄(任一命中即收窄;持卡位次无关,局级
    持续语义)。"""
    full = encounter_options()
    for names in ([_CARD, '躺平'], ['躺平', _CARD]):
        narrowed = encounter_options_for(names)
        assert len(narrowed) == 2
        assert (narrowed[0].difficulty, narrowed[-1].difficulty) == \
            (full[0].difficulty, full[-1].difficulty)
        assert [o.idx for o in narrowed] == [0, 1]


# ============================================================ 锁 2 写点集成

def _backend_with_card_at_encounter(seed: int) -> SimBackend:
    """装配后端预种持卡推进至 P1r7 遭遇节点窗(调用方负责 uninstall)。"""
    b = _backend(seed=seed)
    _open_to_first_window(b)
    b._maybe_finish_wait()
    b.gs.observe(b.gs.active_strategies, [_CARD], sig=_SIG_OBS)
    _walk_to(b, 1, 7)
    assert b.screen_identity() == SCREEN_ENCOUNTER
    return b


def test_presentation_write_point_narrows_container() -> None:
    """呈现写点集成:预种持卡局走到遭遇节点 → 容器呈现集长度 2 ∧
    difficulty 集 = {全集首, 末} ∧ idx 集 = {0,1}(全派生式);观察
    生成器(gen_encounter 容器回读链)与容器一致。seed 7 = 受扰面
    存量锁实证可达 (1,7) 的种子(种子非断言对象,换 seed 需重证可达)。"""
    b = _backend_with_card_at_encounter(seed=7)
    try:
        full = encounter_options()
        container = list(b.gs.encounter.value.options)
        assert len(container) == 2
        assert {o.difficulty for o in container} == \
            {full[0].difficulty, full[-1].difficulty}
        assert {o.idx for o in container} == {0, 1}
        obs = b.observe(SCREEN_ENCOUNTER)
        assert obs.options == container
    finally:
        uninstall_backend()


def test_no_card_presentation_stays_full_set() -> None:
    """无卡局对照:同 seed 不预种 → 呈现集 = 全四档原样(写点收窄仅在
    持卡局生效的集成面锚;前置断言本 seed 未自然持有本卡,若 offer 选中
    属种子不幸,换 seed 而非改断言)。"""
    b = _backend(seed=7)
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        assert _CARD not in (b.gs.active_strategies.value or []), \
            '本 seed offer 自然选中本卡,对照局前提破,换 seed'
        _walk_to(b, 1, 7)
        assert b.screen_identity() == SCREEN_ENCOUNTER
        container = list(b.gs.encounter.value.options)
        assert container == list(encounter_options())
    finally:
        uninstall_backend()


# ============================================================ 锁 3 注册行直测 + hp 腿直调

def test_registration_row_direct_three_legs() -> None:
    """注册行直测:三条效果条目值全直读——卡面「获得10小队生命值和生命上限,
    获得6金币」+ 遭遇两档(防表外安静返 0/注册笔误,T-121 先例)。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.instant_gold == 6
    assert eff.hp_instant == 10
    assert eff.encounter_tier_extremes_only is True


def test_hp_leg_direct_call_grants_exact_and_offtable_zero_write() -> None:
    """hp 腿直调真值 + 表外卡零写(apply_strategy_pick_hp 通用腿直调,
    T-127 test_strategy_pick_hp.py 形态):在册卡入账恰 +10 恰一笔
    (独立 evidence 笔),表外名零笔零写(hp/evidence 双不动)。rng
    形参 = 负值支扩挂点随批加入(正部成员不消费采样,传独立实例形)。"""
    b = _backend(seed=52)
    try:
        gs = b.gs
        hp0 = int(gs.hp.value)
        assert apply_strategy_pick_hp(gs, [_CARD], random.Random(7)) == 1
        assert gs.hp.value == hp0 + 10, f'hp 恰 +10: {gs.hp.value}'
        assert gs.hp.evidence == _HP_EV_PREFIX + _CARD, \
            f'独立笔缺失或来源漂移: {gs.hp.evidence}'
        hp1, ev1 = int(gs.hp.value), gs.hp.evidence
        assert apply_strategy_pick_hp(gs, ['不在册卡名'],
                                      random.Random(7)) == 0
        assert gs.hp.value == hp1 and gs.hp.evidence == ev1, \
            f'表外卡出现写: {gs.hp.value} / {gs.hp.evidence}'
    finally:
        uninstall_backend()
