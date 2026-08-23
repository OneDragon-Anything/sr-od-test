# -*- coding: utf-8 -*-
"""ADR-0299 买入面差异解剖批锁(engine_seed 生成通道 + 锁线目标集补 fixed)。

锁定对象(decision_v2/candidates.py + registry.py,ADR-0299):
① engine_seed 买候选:过渡体系阵营(仙舟/列车同行/持续伤害)未持有
   件在 P1 生成 engine_seed 候选(v1 ADR-0260 门镜像直通);门:已持有
   不生成 / bench 满不种 / P2 不辖;
② 标签注册:engine_seed 进 buy_tag_priority 与四覆盖态放行标签集;
③ 锁线期目标集并入当前位面全部桥的 fixed∪core(旧版只并 core,
   桥 fixed 件如飞霄在锁线后候选不生成 + 无保护)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    _target_names,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _sess(line: str | None = None) -> StrategySession:
    s = StrategySession()
    s.locked_line = line
    s.bridge_id = None
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {'仙舟': 2}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy_tags(st: GameState, sess: StrategySession) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in generate_candidates(st, sess, _REG):
        a = c.action
        card = getattr(a, 'card', None)
        if card is not None and card.name:
            out[card.name] = c.tag
    return out


# --- ① engine_seed 生成通道 -------------------------------------------------


def test_engine_seed_generated_for_transition_unheld() -> None:
    """P1 未持有的过渡体系件(青雀=仙舟)→ engine_seed 候选
    (v2 买入面缺口主导层的修复:首块砖无需先凑档/锁线)。"""
    sess = _sess(line='jizi')
    st = _state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') == 'engine_seed'


def test_engine_seed_not_generated_when_held() -> None:
    """已持有同名(engine_seed 语义=未持有的第一块砖)不走
    engine_seed——副本走 copy 通道(ADR-0300 迁移后生成 'copy',
    上限归 copies_cap/层4,v1 同式)。"""
    sess = _sess(line='jizi')
    st = _state(round_num=1, board={}, bench=[
        BenchChar(slot=0, char_id='青雀', faction='仙舟')], shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_bench_full() -> None:
    """bench 满不种(r408 容量门:满员态「未持有」与卖出态构成
    永动机,ADR-0267 F1)——engine_seed 通道不触发;生成层其他
    通道(copy/pair)不受此门辖,容量由层4 bench_capacity 收口。"""
    sess = _sess(line='jizi')
    bench = [BenchChar(slot=i, char_id='娜塔莎', faction='护盾')
             for i in range(_REG.bench_capacity)]
    st = _state(round_num=1, board={}, bench=bench, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_plane2() -> None:
    """P2 不辖(过渡期种子是 P1 语义;v1 同式)——engine_seed 不
    触发;冷启动 pair 分支(classify_buy=engine)P2 照放(ADR-0300
    迁移,与 v1 _pair_wants 同判据)。"""
    sess = _sess(line='jizi')
    st = _state(plane=2, round_num=1, board={}, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_non_transition() -> None:
    """非过渡体系阵营件(阿格莱雅=昼之半神/能量)不生成
    (engine_seed 不是散买通道)。"""
    sess = _sess(line='jizi')
    st = _state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='阿格莱雅', faction='昼之半神', cost=1)])
    assert '阿格莱雅' not in _buy_tags(st, sess)


def test_engine_seed_target_piece_takes_target_tag() -> None:
    """目标件优先取目标类标签(bridge_core),不被 engine_seed
    降级(优先序 bridge_core > engine_seed)。"""
    sess = _sess()   # 无方向:桥 fixed∪core 全是目标
    st = _state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='三月七', faction='列车同行', cost=1)])
    assert _buy_tags(st, sess).get('三月七') == 'bridge_core'


# --- ② 标签注册 --------------------------------------------------------------


def test_engine_seed_registered_everywhere() -> None:
    """engine_seed 进 buy_tag_priority 与四覆盖态放行标签集
    (层2 过滤不误杀)。"""
    assert 'engine_seed' in _REG.buy_tag_priority
    for tags in (_REG.economy_tags, _REG.war_tags,
                 _REG.emergency_tags, _REG.catchup_tags):
        assert 'engine_seed' in tags


# --- ③ 锁线目标集补 fixed ----------------------------------------------------


def test_locked_target_names_include_bridge_fixed() -> None:
    """锁线期目标集含当前位面全部桥的 fixed∪core(旧版只并 core,
    飞霄=桥 fixed 件在锁线后不生成买候选且无卖保护——买入面
    缺口第二来源,seed 900003 r2 实证)。"""
    from sr_od.application.currency_war.cw_bridge_pool import BRIDGE_POOL
    sess = _sess(line='jizi')
    st = _state()
    names = _target_names(st, sess)
    for combo in BRIDGE_POOL:
        assert set(combo.fixed) <= names, \
            f'锁线目标集漏桥 {combo.bridge_id} 的 fixed'
        assert set(combo.core) <= names, \
            f'锁线目标集漏桥 {combo.bridge_id} 的 core'


def test_locked_bridge_fixed_buy_candidate_generated() -> None:
    """飞霄(桥 fixed,非 core)在锁线态仍生成买候选。"""
    sess = _sess(line='jizi')
    st = _state(round_num=2, board={}, shop=[
        ShopCard(x=0, name='飞霄', faction='追击', cost=2)])
    assert _buy_tags(st, sess).get('飞霄') == 'bridge_core'
