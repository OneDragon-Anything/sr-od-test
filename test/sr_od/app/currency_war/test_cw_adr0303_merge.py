"""ADR-0303 合流批锁(危机常量上移 registry + copy_swap 守卫×目标件豁免)。

锁定对象(decision_v2/registry.py + filters.py + candidates.py):
① 常量上移:应急集 for_gold/levelup 与危机三参(crisis_hoard_gold/
   crisis_buy_bias/crisis_buy_tags)在 registry 单一源,filters 暂驻
   常量已删(旧名残留即红);
② copy_swap 豁免(ADR-0303 落地;ADR-0304 裁决默认关=回退守卫直通,
   开关 registry.copy_swap_target_exempt 留作 A/B 通道):开=在场
   目标件(∈ _target_names 保护集)的第 2 份不被 r410 守卫拦;非目标
   件照旧拦(v1 守卫判据不动)。
决策见 docs/develop/currency_war/decisions/0303-decision-v2-merge.md。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.cw_bridge_pool import BRIDGE_POOL
from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2 import candidates as _cands
from sr_od.application.currency_war.decision_v2 import filters as _filters
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY

# 注入「press 通道关」注册表:press 通道已正式开臂(commit cb7688d4,
# press_channel_enabled 默认 True)。copy_swap 守卫锁与该通道无关,
# 锁守卫自身判据时注入关臂隔离 press 豁免臂。
_REG_NO_PRESS = replace(_REG, press_channel_enabled=False)


def _sess() -> StrategySession:
    s = StrategySession()
    s.locked_line = None
    s.bridge_id = None
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy_names(st: GameState, sess: StrategySession,
               reg: object | None = None) -> set[str]:
    """reg=None 用默认注册表;锁通道无关行为时传 _REG_NO_PRESS。"""
    use = _REG if reg is None else reg
    return {c.action.card.name for c in generate_candidates(st, sess, use)
            if getattr(c.action, 'card', None) is not None}


# --- ① 常量上移 ---------------------------------------------------------------


def test_crisis_constants_in_registry() -> None:
    """危机三参在 registry 单一源(ADR-0302 值不变,ADR-0303 上移)。"""
    assert _REG.crisis_hoard_gold == 40
    assert _REG.crisis_buy_bias == 1.0
    # W35 载体批语义化:crisis 战力买偏置辖的标签集并入 'plugin'
    # (层1 插件通道,定义节 class5——危机态插件同属战力买)
    assert _REG.crisis_buy_tags == frozenset({
        'line_carry', 'line_opportunistic', 'bridge_core',
        'engine_seed', 'plugin', 'carry_gate',
    })


def test_emergency_tags_merged_content() -> None:
    """应急集已并入 for_gold/levelup(ADR-0302 内容修正,合流落位)。"""
    assert {'for_gold', 'levelup'} <= _REG.emergency_tags
    # 应急集保持窄(ADR-0300):经济类仍滤出
    assert not ({'pair', 'copy', 'bond_fallback', 'synthesize'}
                & _REG.emergency_tags)


def test_filters_temp_constants_removed() -> None:
    """filters 暂驻常量已删(旧名残留=上移不彻底,双源即红)。"""
    for name in ('_EMERGENCY_EXTRA_TAGS', '_CRISIS_HOARD_GOLD',
                 '_CRISIS_BUY_BIAS', '_CRISIS_BUY_TAGS'):
        assert not hasattr(_filters, name), (
            f'filters.{name} 残留:危机常量应只在 registry(ADR-0303)')


# --- ② copy_swap 守卫×目标件豁免 ------------------------------------------------


def _target_and_non_target() -> tuple[str, str]:
    """目标件(桥 fixed∪core,无方向种子态口径)与非目标件载体。"""
    target = next(n for c in BRIDGE_POOL for n in c.fixed)
    non_target = '佩拉'   # 引擎阵营但非桥池件(0300 测试同款载体)
    assert non_target not in {n for c in BRIDGE_POOL
                              for n in set(c.fixed) | set(c.core)}
    return target, non_target


def test_copy_swap_exempts_onboard_target_piece() -> None:
    """锁(ADR-0304 语义化:豁免默认关,开关打开才放行):registry
    copy_swap_target_exempt=True 时目标件在场第 2 份不被守卫拦
    (第 2 份语义=3合1 素材/阵容深度,批㉞ M2:483 次误拦)。"""
    from dataclasses import replace
    target, _nt = _target_and_non_target()
    ch = CHARACTERS[target]
    sess = _sess()   # 无方向:桥 fixed∪core 全是目标(保护集口径)
    sess.target_comp = None   # v1 守卫判据下本会被拦(豁免才放行)
    st = _state(
        board={ch.factions[0]: 1},
        deployed=[BenchChar(slot=0, char_id=target,
                            faction=ch.factions[0], position_pref='back')],
        shop=[ShopCard(x=0, name=target, faction=ch.factions[0],
                       cost=ch.cost)],
    )
    # 镜像:v1 守卫本身会拦(target_comp=None 无保留判据)
    assert _cands._copy_swap_useless(st.shop[0], st, sess)
    # 默认关(ADR-0304 裁决回退):守卫直通,照拦——注入关臂隔离
    # press 豁免臂(开臂后默认注册表该臂会放行 band 内副本)
    assert not _REG.copy_swap_target_exempt
    assert _cands._copy_swap_blocked(st.shop[0], st, sess, _REG_NO_PRESS)
    assert target not in _buy_names(st, sess, _REG_NO_PRESS)
    # 开关开(ADR-0303 豁免,A/B 通道):不拦 + 买候选生成
    reg_on = replace(_REG, copy_swap_target_exempt=True)
    assert not _cands._copy_swap_blocked(st.shop[0], st, sess, reg_on)
    assert target in {c.action.card.name
                      for c in generate_candidates(st, sess, reg_on)
                      if getattr(c.action, 'card', None) is not None}


def test_copy_swap_still_blocks_non_target_piece() -> None:
    """锁:非目标件在场第 2 份照旧被拦(v1 r410 判据不动;豁免=
    目标件名单交叉,非守卫整体下线——开/关两态皆拦)。"""
    from dataclasses import replace
    _t, non_target = _target_and_non_target()
    ch = CHARACTERS[non_target]
    sess = _sess()
    sess.target_comp = None
    st = _state(
        board={ch.factions[0]: 1},
        deployed=[BenchChar(slot=0, char_id=non_target,
                            faction=ch.factions[0], position_pref='back')],
        shop=[ShopCard(x=0, name=non_target, faction=ch.factions[0],
                       cost=ch.cost)],
    )
    assert _cands._copy_swap_useless(st.shop[0], st, sess)
    assert _cands._copy_swap_blocked(st.shop[0], st, sess, _REG_NO_PRESS)
    reg_on = replace(_REG_NO_PRESS, copy_swap_target_exempt=True)
    assert _cands._copy_swap_blocked(st.shop[0], st, sess, reg_on)
    assert non_target not in _buy_names(st, sess, _REG_NO_PRESS)
    assert non_target not in {
        c.action.card.name
        for c in generate_candidates(st, sess, reg_on)
        if getattr(c.action, 'card', None) is not None}
