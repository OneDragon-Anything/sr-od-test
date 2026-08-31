"""分包期 0b 单元2 等价锁:经济循环接缝族下沉 kernel cw_economy(§3.3-①a/①b)。

背景:schedule_upgrade/refresh_ev_budget 自 decision_v2.economy_cycle 下沉
cw_economy(kernel 桶),refresh_ev_budget 内应急谓词 is_emergency 一并下沉
(decision_v2.filters 改委托重定向)。本文件锁「重构注入前后同输入同输出
逐位一致」:注入前后契约差异 = 零(谓词单一源随符号迁移,非行为重写)。

桩点契约(防「桩了旧位置、生产走新路径」全绿假象):生产桩点钉
cw_economy 符号(消费方函数内懒 import,属性动态解析),本文件附带
identity 锁——filters.is_emergency 与 cw_economy.is_emergency 同一谓词。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import inspect

from sr_od.application.currency_war.kernel import cw_economy
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY

_REG = DEFAULT_REGISTRY


def _st(gold: int, hp: int = 80, level: int = 6, plane: int = 1,
        round_num: int = 5) -> GameState:
    st = GameState(gold=gold, level=level, plane=plane,
                   round_num=round_num, hp=hp)
    st.active_strategies = []
    return st


def test_is_emergency_single_source_identity() -> None:
    """单一源锁:filters.is_emergency 本体 = cw_economy.is_emergency。"""
    import sr_od.application.currency_war.decision.decision_v2.filters as _f
    src = inspect.getsource(_f.is_emergency)
    assert 'cw_economy import is_emergency' in src, \
        'filters 侧必须保持 kernel 重定向(禁本地复刻谓词)'
    # 边界逐位:hp == emergency_hp 恰为 True(≤ 语义)
    assert cw_economy.is_emergency(_st(50, hp=_REG.emergency_hp), _REG)
    assert not cw_economy.is_emergency(
        _st(50, hp=_REG.emergency_hp + 1), _REG)


def test_refresh_ev_budget_bitwise_contract() -> None:
    """单元等价锁:下沉后输出与重构前公式逐位一致(帧矩阵全覆盖)。

    契约(`w615_rules_advocacy/` §2-R3 + `w623_batch3_pre-mortem/` D2):
    应急帧 → 0;g ≤ R* → 0;溢余帧 → min(6, ⌊(g−R*)/刷价⌋)。"""
    sess = StrategySession()
    # 应急帧(hp=emergency_hp)→ 0
    assert cw_economy.refresh_ev_budget(
        _st(80, hp=_REG.emergency_hp), sess, _REG) == 0
    # 常态帧 g ≤ R*(息线 50,无排程)→ 0
    assert cw_economy.refresh_ev_budget(_st(50), sess, _REG) == 0
    # 溢余帧:g−R* = 30,刷价缺省 2 → 15 刷 → 6 刷帽
    assert cw_economy.refresh_ev_budget(_st(80), sess, _REG) == 6
    # 溢余小帧:over=6/刷价2 → 3 刷
    assert cw_economy.refresh_ev_budget(_st(56), sess, _REG) == 3
    # 刷价现读优先:shop_refresh_cost=3 → over=30//3=10 → 6 刷帽
    st3 = _st(80)
    st3.shop_refresh_cost = 3
    assert cw_economy.refresh_ev_budget(st3, sess, _REG) == 6
    # 溢余 5/刷价3 → 1 刷
    st4 = _st(55)
    st4.shop_refresh_cost = 3
    assert cw_economy.refresh_ev_budget(st4, sess, _REG) == 1


# ---- 已退役 2 条(失去保护注记,w729 残差收尾批)----
# test_get_node_goal_projection_uses_local_seam(断环锁 cw_economy 零
#   decision 依赖):上层覆盖复核成立——test_cw_package_layout::
#   test_bucket_dependency_matrix 对 kernel→decision 全桶禁边(含函数级
#   import),严格强于本锁的单文件 AST 检查。
# test_seam_injection_contract_registry_override(P6 注入契约:显式
#   registry 优先):上层覆盖复核成立——test_cw_w633_migration_b3
#   「注入一致性锁(W636 A)」对三接缝含 refresh_ev_budget 做同型
#   reg2 vs 缺省表对照,行域更宽,本锁无独占行。
