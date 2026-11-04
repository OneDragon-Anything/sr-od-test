"""策略卡首领节点完成固定集发放检查腿测试(镜像 src = kernel/
cw_gain_chain.py 的 check_strategy_boss_completion_grants)。

测试面依据 = 迭代设计 designs/T-330-wuqi-pifashang.md §4 锁 3 + §2.2/
§5-7(直构形态先例 = 同目录 test_check_strategy_boss_battle_grants.py
的容器直置,禁经战斗链假绿):
- 条件矩阵短路:node_kind 非 boss → 零写;未持卡/表外卡 → 零写零闩;
- 发放真值:持卡未闩 → 简易池全集 8 件按注册表序逐件追加(rand=False
  确定事件 = logic 渠道零采样)、闩落(strategy_conditional_done 纯卡名
  追加)、evidence ``strategy_boss_completion#<卡名>``(**断言用前缀
  匹配禁精确匹配**,gain_equipment 原语内追加 ``#equip`` 后缀,T-167
  锁 2 判例);
- 一次性闩:卡名已闩 → 短路零写(「下个」恰一次;幂等守卫只防同战斗
  重放,闩防下一场 boss 重复,函数内自管);
- 拒落不闩自愈 = 裁决点 7 边界申报(sim 域 equips 恒种子观察拒落不可达,
  直构拒落窗语义归自愈面,本文件不立锁——锁面 §4 明文四条)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_boss_completion_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    SIMPLE_EQUIP_ALL,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '武器批发商'
_EVIDENCE_PREFIX = f'strategy_boss_completion#{_CARD}'


def _gs(*, card: str | None = _CARD) -> GameState:
    """直构 gs(equips 观察定发放承载;card=None = 未持卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def test_non_boss_kind_zero_write() -> None:
    """锁 3d:node_kind != 'boss' → 零写零闩(节点类型条件矩阵首位
    短路,持卡与否零影响;kind = 调用方传结算点现值)。"""
    for kind in ('battle', 'encounter', 'reward', 'supply', ''):
        gs = _gs()
        before = gs.write_seq
        check_strategy_boss_completion_grants(gs, kind, _LSIG)
        assert gs.equips.value == [], f'非首领 kind={kind!r} 误入栏'
        assert gs.strategy_conditional_done.value in (None, ()), \
            f'非首领 kind={kind!r} 误闩'
        assert gs.write_seq == before, f'非首领 kind={kind!r} 误写'


def test_no_card_and_out_of_registry_zero_write() -> None:
    """锁 3a:未持卡 + boss → 零写;持表外卡(躺平,效果原文含装备字样
    但不在登记表)+ boss → 零写零闩(表外卡一律无条目,禁从效果原文
    自动猜装的通道纪律)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card)
        before = gs.write_seq
        check_strategy_boss_completion_grants(gs, 'boss', _LSIG)
        assert gs.equips.value == [], f'card={card!r} 误入栏'
        assert gs.strategy_conditional_done.value in (None, ()), \
            f'card={card!r} 误闩'
        assert gs.write_seq == before, f'card={card!r} 误写'


def test_boss_completion_grants_full_set_and_latch() -> None:
    """锁 3b:持卡未闩 + boss → 简易池全集 8 件按注册表序追加
    (rand=False 确定事件 = logic 渠道零采样)+ 闩落 + evidence 前缀
    匹配(**禁精确匹配**,原语内追加 #equip 后缀;8 件共享同证据基)。"""
    gs = _gs()
    before = gs.write_seq
    check_strategy_boss_completion_grants(gs, 'boss', _LSIG)
    assert gs.equips.value == list(SIMPLE_EQUIP_ALL), \
        f'发放漂移(应为注册表序全集): {gs.equips.value!r}'
    assert gs.strategy_conditional_done.value == (_CARD,), \
        f'闩未落: {gs.strategy_conditional_done.value!r}'
    assert gs.equips.source == 'logic_rand', (
        '直构域容器未锚定 → 随机态通道(模块通道规则;rand=False 锁值'
        '确定性 = 注册表序全集非采样,通道与值语义解耦,锚定域归 sim e2e)')
    assert gs.equips.evidence.startswith(_EVIDENCE_PREFIX), \
        f'evidence 前缀漂移: {gs.equips.evidence}'
    assert gs.equips.evidence.endswith('#equip'), \
        f'evidence 后缀漂移: {gs.equips.evidence}'
    assert gs.strategy_conditional_done.source == 'logic', '闩 = 逻辑态'
    assert gs.strategy_conditional_done.evidence == _EVIDENCE_PREFIX, \
        f'闩 evidence 漂移: {gs.strategy_conditional_done.evidence}'
    assert gs.write_seq == before + (len(SIMPLE_EQUIP_ALL) + 1), \
        '写笔数 = 8 件 + 1 闩'


def test_latched_short_circuit_zero_write() -> None:
    """锁 3c:卡名已闩 → 短路零写(「下个」恰一次;闩后后续首领节点
    再结算零发放零新笔)。"""
    gs = _gs()
    gs.write_logic(gs.strategy_conditional_done, (_CARD,),
                   produced_by='test-seed', evidence='t:done', sig=_LSIG)
    before = gs.write_seq
    check_strategy_boss_completion_grants(gs, 'boss', _LSIG)
    assert gs.equips.value == [], '已闩误入栏'
    assert gs.strategy_conditional_done.value == (_CARD,), '闩值漂移'
    assert gs.write_seq == before, '已闩短路应零写'


def test_second_boss_no_repeat_after_latch() -> None:
    """锁 3c 补面(跨节点时序直读):首 boss 结算闩落 → 同 gs 再调
    (模拟下一场 boss)→ 零新笔零重复——幂等守卫防同战斗重放,闩防
    跨 boss 重复,两层各司其职。"""
    gs = _gs()
    check_strategy_boss_completion_grants(gs, 'boss', _LSIG)
    after_first = list(gs.equips.value or [])
    before = gs.write_seq
    check_strategy_boss_completion_grants(gs, 'boss', _LSIG)
    assert list(gs.equips.value or []) == after_first, '跨 boss 重复发放'
    assert gs.write_seq == before, '跨 boss 零新笔'
