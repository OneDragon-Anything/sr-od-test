"""ADR-0419新局开始全量状态重置锁:上一局残留不进下一局。

根因(抽样判读 §三 deploy_cap_vs_level 4/4 / phase_round 2/3 / level):run 异常
停在上局对局中时 ``ctx.cw_match`` 残留非 None → 下一次入口链开**新局**时
``RunLoop.handle_init`` 续跑判定(``cw_match is None``)误判为续跑,把旧 session 整体
延用 —— level 单调守卫拿上局值打新局真读(obs_conflict 三层 329 张残留源)。

修法(治本 = 重置宿主而非逐守卫打补丁):入口链在「确凿新局」三屏(难度确认/模式选择/
简报)弃置残留容器(cw_strategy.discard_stale_match_container)→ handle_init 走新建
分支,**全量重置 by construction**(StrategySession 新建每字段回默认);「继续进度」
恢复同一物理局不触发(合法续用)。
"""
import inspect

from sr_od.application.currency_war.cw_observation import (
    reset_phase_round_cache,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.cw_strategy import (
    CurrencyWarMatch,
    StrategySession,
    discard_stale_match_container,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)


class _FakeCtx:
    """最小 ctx 替身:discard 只读写 cw_match 属性。"""

    def __init__(self) -> None:
        self.cw_match: CurrencyWarMatch | None = None


def _polluted_match() -> CurrencyWarMatch:
    """构造带跨局毒值的容器(覆盖 三层实证字段 + tracked 宿主代表)。"""
    s = StrategySession()
    s.last_level_obs = 5          # 上局等级(cap_vs_level 抽样 4/4 的旧 level=5)
    s.last_streak = -7            # 上局连败(economy fold 门输入)
    s.last_hp_real = 12           # hp 对账锚
    s.tracked_deployed = [BenchChar(slot=1, char_id='旧局角色')]
    s.active_strategies = ['旧局策略']
    return CurrencyWarMatch(DecisionV2Strategy(), s)


def test_discard_stale_container_resets_for_new_match():
    """锁 1(核心语义:模拟第二局开始,上一局 tracked 值不残留):
    入口链见到新局确凿信号 → 弃置容器;随后 handle_init 新建 session 全默认。"""
    ctx = _FakeCtx()
    ctx.cw_match = _polluted_match()
    assert discard_stale_match_container(ctx, '到达难度确认屏=新局开始') is True
    assert ctx.cw_match is None   # 新建分支承担全量重置(容器已断开)

    # 第二局 session 由 create_session 重建 —— 与 handle_init 新 match 分支同路径,
    # 锁定观察域关键字段全默认(任何字段若被改成可携带上局值,此处红)。
    fresh = DecisionV2Strategy().create_session(None)
    assert fresh.last_level_obs == 0      # level 单调守卫不再拿上局值保旧
    assert fresh.last_streak == 0
    assert fresh.last_hp_real is None
    assert fresh.tracked_deployed == []
    assert fresh.active_strategies == []


def test_discard_idempotent_when_no_container():
    """锁 2(幂等直过):无残留(正常流程局终已清)→ 返回 False 不动。"""
    ctx = _FakeCtx()
    assert discard_stale_match_container(ctx, '任意原因') is False
    assert ctx.cw_match is None


def test_phase_round_cross_match_reset():
    """锁 3(phase_round 跨局重置豁免语义):last-known-good 在新局边界被清,
    单调守卫不会拿上局 [9,9] 打回新局 1-9(phase_round 抽样 2/3 ✗ 根因)。"""
    import sr_od.application.currency_war.cw_observation as obs_mod
    obs_mod._last_phase_round = (3, 9)     # 模拟上局 P3-9 残留
    try:
        assert obs_mod._last_phase_round == (3, 9)
        reset_phase_round_cache()          # discard/handle_init 新局边界调用点
        assert obs_mod._last_phase_round is None
    finally:
        reset_phase_round_cache()


def test_entry_discard_call_sites_are_new_match_only():
    """锁 4(静态口径:弃置只挂新局确凿三屏,不碰「继续进度」恢复同一物理局的合法续用):
    入口文件恰有 3 个调用点,理由串分别为难度确认/模式选择/简报。"""
    from sr_od.application.currency_war.operations.entry import (
        start_currency_war_match as entry_mod,
    )
    src = inspect.getsource(entry_mod)
    for reason in ('到达难度确认屏=新局开始',
                   '到达模式选择屏=新局开始',
                   '到达简报屏=新局开始'):
        assert reason in src                      # 三屏各有登记
    assert src.count('_discard_stale_once(') == 4  # 定义内转发 1 + 三调用点
    # 「继续进度」恢复路径(1b 分支)不得触发弃置:其代码块内无该调用
    resume_at = src.index("round_by_ocr_and_click(screen, '继续进度'")
    resume_block = src[resume_at:src.index('# 2)', resume_at)]
    assert '_discard_stale_once' not in resume_block
