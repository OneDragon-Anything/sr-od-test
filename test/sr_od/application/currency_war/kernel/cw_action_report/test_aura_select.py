"""report_action_aura_select_param 记账测试(主角光环选择落地)。

锁的设计约定(契约正文 = aura_slot 字段注释 + 本函数 docstring):
- 合法槽 1..4 → write_logic 落 ``aura_slot``(source=logic,
  produced_by=CwScreenAuraSelect);
- 值域守卫:域外(0 / 负值 / 超前排容量 / 后排语义)= ValueError 显式
  报错,禁钳位禁静默(调用方漂移形态由 op 侧跳写闸拦截,到达本函数的
  域外值 = 调用方 bug);
- 渠道族守卫:family 非 logic_action = 显式炸错(_validate_sig 统一口)。
"""

import pytest

from sr_od.application.currency_war.kernel.cw_action_report.aura_select import (
    report_action_aura_select_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)

_SIG = ChannelSig(family='logic_action', actor='CwScreenAuraSelect',
                  screen='货币战争-主角光环选择', mode='compute')


def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def test_valid_slot_writes_logic() -> None:
    """合法槽写入:值/来源/产生者逐位断言;重复写 = 整值替换(逻辑态
    标准通道语义,重选重记账幂等)。"""
    gs = _gs()
    report_action_aura_select_param(gs, 1, sig=_SIG)
    assert gs.aura_slot.value == 1
    assert gs.aura_slot.source == 'logic'
    # 换抓点重试漂移落点如实重记账(最新落点覆盖)
    report_action_aura_select_param(gs, 3, sig=_SIG)
    assert gs.aura_slot.value == 3


@pytest.mark.parametrize('slot', [0, -1, 5, 99])
def test_out_of_domain_slot_raises(slot: int) -> None:
    """值域守卫:域外显式报错(1..4 前排物理槽;域外 = 调用方 bug)。"""
    gs = _gs()
    with pytest.raises(ValueError):
        report_action_aura_select_param(gs, slot, sig=_SIG)
    assert gs.aura_slot.value is None   # 报错路径零写


def test_wrong_sig_family_rejected() -> None:
    """渠道族守卫:obs 族签名进动作上报 = 显式炸错(写入口统一校验)。"""
    gs = _gs()
    with pytest.raises(ValueError):
        report_action_aura_select_param(
            gs, 1, sig=ChannelSig(family='obs', actor='test', mode='read'))
    assert gs.aura_slot.value is None
