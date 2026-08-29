"""W379 · C4 存活轮数门 v2 栈接线单帧锁。

背景(W376 A/B 实证):survival_gate 唯一消费点在 default_strategy.
update_target,而生产策略栈 DecisionV2Strategy 完整覆写 update_target
(意向状态机,不调 super)→ 门在生产栈无行为通道(off 与 C4-only 两臂
300 局逐位相等)。本批把门接进 v2 换线判据路径:cw_intention.update_
intention 的撤销后替代线锁定处(v2 语义下的「换线」决策位置;判据单一
源=cw_line_switch.survival_gate 不变,本批只补消费点)。

锁面:
- G1 接线锁:weak→换线被门拦(保持弱意向,线对拦截计数去重);
- G2 零漂移锁:开关关(缺省 registry)同帧照旧落锁;
- G3 同线重锁不辖:门开也放行(重锁原线非换线);
- G4 初始锁线不辖:unlocked→lock 不经门(P2 首锁非换线);
- G5 registry 注入透传:DecisionV2Strategy.update_target 把 self.registry
  传到门(A/B replace 注入臂可达;W376 C4 臂失效的直接根因面)。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_intention import (
    CORE_MISS_N,
    IntentionState,
    update_intention,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)

_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)

#: P2 位面节点表(与 W373 夹具同款;r1 起投影含 boss 附加费路径)
P2_TABLE = ['battle', 'battle', 'encounter', 'reward',
            'encounter', 'reward', 'boss']


def _state(plane: int = 2, **kw) -> GameState:
    s = GameState()
    s.plane = plane
    s.round_num = kw.get('round_num', 1)
    s.level = kw.get('level', 5)
    s.hp = kw.get('hp', 20)          # 低血=投影存活轮数短(门收紧方向)
    s.active_env = kw.get('env', '')
    for name in kw.get('shop', []):
        ch = CHARACTERS.get(name)
        s.shop.append(ShopCard(x=len(s.shop), name=name,
                               faction=ch.factions[0] if ch and ch.factions
                               else '?',
                               cost=ch.cost if ch else 3))
    for name in kw.get('bench', []):
        ch = CHARACTERS.get(name)
        s.bench.append(BenchChar(slot=len(s.bench), char_id=name,
                                 faction=ch.factions[0] if ch and ch.factions
                                 else '?', star=1))
    return s


def _sess() -> StrategySession:
    s = StrategySession()
    s.plane_node_table = list(P2_TABLE)
    s.plane_node_table_plane = 2
    return s


#: 证据组 B 夹具(W423 起撤销出口①须异线资产证据,同 test_cw_intention):
#: 异线「万敌单C」(v2 家族)终局件 5 张在手,核心万敌可达 → 厚度 ≥ A_min。
EVIDENCE_BENCH = ['万敌', '千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _weak_on_xianzhou(registry=None) -> tuple[IntentionState, StrategySession]:
    """走真实状态机抵达 weak:锁希儿量子 → 核心断供证据(三条件合取:
    miss ≥ max(CORE_MISS_N, N_req)+ 异线在场资产)撤销。
    (门只辖真实撤销后的替代线锁定,夹具必须走全撤销路径。)"""
    from sr_od.application.currency_war.cw_intention import (
        core_miss_n_required,
    )
    reg = registry or DEFAULT_REGISTRY
    sess = _sess()
    ist = update_intention(_state(shop=['希儿']), IntentionState(),
                           sess, registry=registry)
    assert ist.locked_comp == '希儿量子', '夹具前提:③锁希儿量子'
    gone = _state(bench=EVIDENCE_BENCH)
    need = max(CORE_MISS_N,
               core_miss_n_required('希儿', 5, reg.revoke_miss_tolerance_eps))
    for _ in range(need):
        update_intention(gone, ist, sess, registry=registry)
    assert ist.phase == 'weak' and ist.weak_comp == '希儿量子', \
        '夹具前提:撤销出口①降级弱意向'
    return ist, sess


# --- G1 接线锁:weak→换线被门拦(单帧) ----------------------------------------


def test_w379_g1_gate_blocks_line_switch_in_v2() -> None:
    """门开 + 低血(投影存活不足)→ 替代线锁定被门拦。

    改判(v3 R-A 门感知滞回闩;本锁语义两次演进:W665 v2 曾改 N=2
    计数回锁,被 W683 实锤周期-3 极限环后废弃;v3 终态 = 首次拦截帧
    即置闩 + 一次性回锁原线,轨迹锁见 test_cw_line_gate_relock)。
    本锁钉:被拦帧拦截位/反事实位记账 + 线对拦截计数 + 回锁原线。
    """
    ist, _ = _weak_on_xianzhou(_REG_GATE)
    sess = _sess()
    sw = _state(env='列车同行概念股', hp=20)
    out = update_intention(sw, ist, sess, registry=_REG_GATE)
    assert out.phase == 'locked' and out.locked_comp == '希儿量子'
    assert out.last_event == 'gate_relock:希儿量子'
    assert sess.line_switch_block_counts == {('希儿量子', '列车同行'): 1}
    assert sess.v3_line_gate_blocked is True
    assert sess.v3_line_gate_cf_blocked is True   # on 臂=门判定本身


# --- G2 零漂移锁:开关关(缺省 registry)同帧照旧落锁 --------------------------


def test_w379_g2_default_off_locks_as_before() -> None:
    """registry 缺省(门关)→ 同一换线帧照旧锁列车同行——生产默认路径
    零漂移的结构前提(与既有 test_cw_intention 行为锁同判)。"""
    ist, _ = _weak_on_xianzhou(None)
    sess = _sess()
    out = update_intention(_state(env='列车同行概念股', hp=20), ist,
                           sess)
    assert out.phase == 'locked' and out.locked_comp == '列车同行'
    assert not hasattr(sess, 'line_switch_block_counts')


# --- G3 同线重锁不辖 -----------------------------------------------------------


def test_w379_g3_same_line_relock_not_gated() -> None:
    """门开 + 低血,但新信号即原弱意向线(希儿再现)→ 照旧落锁:
    重锁原线不是换线,门不辖(与 default 栈「换线才过门」辖域对齐)。"""
    ist, _ = _weak_on_xianzhou(_REG_GATE)
    sess = _sess()
    out = update_intention(_state(shop=['希儿'], hp=20), ist, sess,
                           registry=_REG_GATE)
    assert out.phase == 'locked' and out.locked_comp == '希儿量子'


# --- G4 初始锁线不辖 -----------------------------------------------------------


def test_w379_g4_initial_lock_not_gated() -> None:
    """门开 + 低血,unlocked 初始态 P2 首锁(无在先承诺线)→ 照旧落锁:
    初始锁线非换线(W376 default 栈语义:门只在换线裁决之后串联)。"""
    sess = _sess()
    ist = update_intention(_state(shop=['希儿'], hp=20), IntentionState(),
                           sess, registry=_REG_GATE)
    assert ist.phase == 'locked' and ist.locked_comp == '希儿量子'


# --- G5 registry 注入透传锁 -----------------------------------------------------


def test_w379_g5_strategy_threads_injected_registry(monkeypatch) -> None:
    """DecisionV2Strategy.update_target 把 self.registry 传到门:monkeypatch
    捕获 cw_intention.survival_gate 的 registry 实参必须是注入副本(W376
    C4 臂经 dataclasses.replace 构造注册表,透传断链=门恒读缺省关表)。"""
    import sr_od.application.currency_war.cw_intention as ci

    captured: dict = {}
    orig = ci.survival_gate

    def spy(state, session, e_alt, registry=None):
        captured['registry'] = registry
        return orig(state, session, e_alt, registry)

    monkeypatch.setattr(ci, 'survival_gate', spy)
    strat = DecisionV2Strategy(registry=_REG_GATE)
    sess = StrategySession()
    ist = IntentionState()
    ist.phase = 'weak'
    ist.weak_comp = '希儿量子'
    sess.v3_intention = ist
    sess.v3_intention_key = None   # 强制本帧驱动状态机
    strat.update_target(_state(env='列车同行概念股', hp=20), sess,
                        SimpleNamespace())
    assert captured.get('registry') is _REG_GATE
    # 改判(v3 R-A):门拦首帧即置闩+一次性回锁原线(原断言「保持 weak」
    # 是 v2 修复前语义,已被闩取代)
    assert ist.phase == 'locked' and ist.locked_comp == '希儿量子'
    assert ist.last_event == 'gate_relock:希儿量子'
