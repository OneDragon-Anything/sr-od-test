"""W971 P3b 段2 接线锁:纯分发器接管备战/商店常态编排(W970 批 C 全项)。

设计单一源 = docs/develop/currency_war/prereg/w970_layered_arch/DESIGN.md
§3/§4.3(RunBuyPhase 解体/EnsureShop 意图退役/腾席链 b read_only/探针挂点
随迁/_handle_bench_full 合流)+ w971_flow_layer/03-prep.md(稳定门退役)。
"""

import inspect

from sr_od.application.currency_war.decision.decision_v2.adapter import (
    action_to_atomop,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PREP_ACTION_TYPES,
    OpenShop,
)

# ==================== 决策层:动作发射改型(新旧映射对拍) ====================

#: 新旧动作映射(决策输出等价改名;流程层语义由编排承接)
_RENAME_MAP = {
    'RunBuyPhase': lambda a: isinstance(a, OpenShop) and not a.read_only,
    'EnsureShopOpen': lambda a: isinstance(a, OpenShop) and a.read_only,
    'EnsureShopClosed': lambda a: isinstance(a, OpenShop) and a.read_only,
}


def test_open_shop_action_registered() -> None:
    """OpenShop 进动作全集白名单 + AtomOp 映射(漏登记 = F3 拒绝/影子未知缺陷)。"""
    assert OpenShop in PREP_ACTION_TYPES
    op = action_to_atomop(OpenShop(read_only=True))
    assert op.op_key.startswith('open_shop') and op.domain == 'shop'


def test_strategy_emits_open_shop_forms() -> None:
    """决策发射改型(对拍:旧输出 → 新输出按改名映射逐项等价):
    RunBuyPhase→OpenShop / EnsureShopOpen→OpenShop(read_only) /
    EnsureShopClosed→OpenShop(read_only),生产路径零旧意图残留。"""
    from sr_od.application.currency_war.decision.decision_v2 import (
        strategy as strat_mod,
    )

    src = inspect.getsource(strat_mod.DecisionV2Strategy)
    assert src.count('return OpenShop(read_only=True)') == 2, (
        '腾席链 b / 开态清洁面板两处须发 OpenShop(read_only)')
    assert 'return OpenShop()' in src, '主流程买牌段须发显式开店意图 OpenShop()'
    for retired in ('return RunBuyPhase()', 'return EnsureShopOpen()',
                    'return EnsureShopClosed()'):
        assert retired not in src, f'{retired} 仍在新接口发射(须按映射改型)'


def test_v2_engine_intercepts_open_shop_by_type() -> None:
    """流程层拦截 = 类型分派(字符串匹配判据退役,W970 §3)。"""
    from sr_od.application.currency_war import prep_director as pd_mod

    port_src = inspect.getsource(pd_mod.PrepDirector._run_prep_loop_v2)
    assert 'isinstance(action, OpenShop)' in port_src, '执行端口缺 OpenShop 类型分派'
    assert "if 'EnsureShopClosed' in key" not in port_src, (
        '探针挂点字符串匹配判据未退役(§3:改类型分派)')


def test_open_shop_phase_orchestration() -> None:
    """流程层商店编排契约(read_only 与买牌两形态 + 探针挂点随迁)。"""
    from sr_od.application.currency_war import prep_director as pd_mod

    src = inspect.getsource(pd_mod.PrepDirector._open_shop_phase)
    # 编排序:open_shop → (read_only: 观察+关店 | 波循环+关店) → finalize → 探针
    assert src.index('open_shop(self)') < src.index('close_shop(self)'), '开店须先于关店'
    assert 'run_buy_waves' in src and 'finalize_buy_phase' in src, (
        '买牌形态缺商店动作波循环/单元收尾(壳直调三 op 调用点须上移流程层)')
    assert src.rindex('_probe_node_type') > src.rindex('close_shop(self)'), (
        '节点探针挂点须在 CloseShopOp 完成后(W970 §4.3.5)')
    # read_only 形态:heavy 观察刷新(gold 开态真值)语义在编排内声明
    assert src.count('read_only') >= 3 and '_observe(heavy=True)' in src


def test_buy_phase_finalize_single_source() -> None:
    """买后收尾单一源:finalize_buy_phase 模块函数,壳与流程层共用(防双份漂移)。"""
    from sr_od.application.currency_war.operations.prep import shop as shop_mod

    assert hasattr(shop_mod, 'finalize_buy_phase')
    buy_src = inspect.getsource(shop_mod.BuyShopCards.buy)
    assert 'finalize_buy_phase(' in buy_src, '壳未改用共用收尾函数'
    assert 'pending_buy_expect' not in buy_src, (
        '买后收尾段仍内联在壳里(应已抽入 finalize_buy_phase 单一源)')


# ==================== 主循环:稳定门/标志位/接管补采退役 ====================


def _loop_src() -> str:
    from sr_od.application.currency_war.operations import battle_loop
    return inspect.getsource(battle_loop.CurrencyWarRunLoop)


def test_prep_settle_gate_retired() -> None:
    """PREP_SETTLE_S 稳定门退役(W971 03-prep §1):门常量与 bookkeeping 删除。"""
    src = _loop_src()
    assert 'PREP_SETTLE_S: ClassVar' not in src, '稳定门常量未退役'
    assert '_prep_entry_ts' not in src and '_prev_frame_prep' not in src, (
        '稳定门 bookkeeping 未删')


def test_post_settle_auto_shop_flag_retired() -> None:
    """_post_settle_auto_shop 标志位退役(W971 §2.11:判稳收编战斗等待侧/
    director 环入口预收探针,不再跨分支传标志)。"""
    src = _loop_src()
    assert '_post_settle_auto_shop = True' not in src, '标志位写入点未退役'
    assert 'getattr(self, \'_post_settle_auto_shop\', False)' not in src, (
        '标志位消费点未退役')


def test_takeover_collect_moved_to_director() -> None:
    """接管局补采挂点迁移(01-opening §2.1):battle_loop 内联块退役,
    由干净备战观察(prep_director 环入口 gate 后稳定帧)承担。"""
    assert '_cw_takeover_done' not in _loop_src(), 'loop 内联补采块未退役'
    from sr_od.application.currency_war import prep_director as pd_mod
    src = inspect.getsource(pd_mod.PrepDirector._run_loop)
    assert 'cw_takeover_collect_done' in src, 'prep_director 缺接管补采块'
    assert 'briefing_bosses' in src, '补采触发门(简报真值空)缺失'
    assert 'CollectPlaneIntel' in src, '补采通道(位面详情采集 op)缺失'
