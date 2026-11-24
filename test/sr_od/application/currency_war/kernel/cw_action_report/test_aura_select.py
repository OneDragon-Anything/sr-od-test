"""report_action_aura_select_param 记账测试(主角光环选择落地)。

锁的设计约定(契约正文 = aura_slot / chosen_aura 字段注释 + 本函数 docstring):
- 合法槽 + 光环卡序号 → write_logic 落 ``aura_slot``(source=logic,
  produced_by=CwScreenAuraSelect)与 ``chosen_aura``(选中的光环标准名,名字由
  ``aura_select_opts[idx]`` 单一源按序号提供,上报层零名字转换);
- 值域守卫:槽域外(0 / 负值 / 超前排容量 / 后排语义)= ValueError 显式
  报错,禁钳位禁静默(调用方漂移形态由 op 侧跳写闸拦截,到达本函数的
  域外值 = 调用方 bug);序号越界 / 名单缺席 = AssertionError(观察未上报
  即选择落地 = 调用方 bug);报错路径两字段零写;
- 渠道族守卫:family 非 logic_action = 显式炸错(_validate_sig 统一口)。

``chosen_aura`` 的消费点 = 上阵规模占用派生(``team_size_used_of``:持有者
额外占用按光环代价计)——选了哪张光环不记账,超限态就算不出来。
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
_OPTS = ['高傲巨人', '从师']


def _gs(opts: list[str] | None = _OPTS) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if opts is not None:
        gs.write_logic(gs.aura_select_opts, list(opts),
                       produced_by='CwScreenAuraSelect', sig=_SIG)
    return gs


def test_valid_slot_writes_logic() -> None:
    """合法槽写入:值/来源/产生者逐位断言;重复写 = 整值替换(逻辑态
    标准通道语义,重选重记账幂等)。"""
    gs = _gs()
    report_action_aura_select_param(gs, 1, aura_idx=0, sig=_SIG)
    assert gs.aura_slot.value == 1
    assert gs.aura_slot.source == 'logic'
    # 换抓点重试漂移落点如实重记账(最新落点覆盖)
    report_action_aura_select_param(gs, 3, aura_idx=0, sig=_SIG)
    assert gs.aura_slot.value == 3


def test_chosen_aura_from_opts_by_idx() -> None:
    """选中光环名按序号取自名单单一源:左卡 idx 0 / 右卡 idx 1;来源逻辑态;
    位面重选覆盖写(最新选择覆盖)。"""
    gs = _gs()
    report_action_aura_select_param(gs, 2, aura_idx=0, sig=_SIG)
    assert gs.chosen_aura.value == '高傲巨人'
    assert gs.chosen_aura.source == 'logic'
    report_action_aura_select_param(gs, 1, aura_idx=1, sig=_SIG)
    assert gs.chosen_aura.value == '从师'
    assert gs.aura_slot.value == 1


@pytest.mark.parametrize('slot', [0, -1, 5, 99])
def test_out_of_domain_slot_raises(slot: int) -> None:
    """值域守卫:域外显式报错(1..4 前排物理槽;域外 = 调用方 bug)。"""
    gs = _gs()
    with pytest.raises(ValueError):
        report_action_aura_select_param(gs, slot, aura_idx=0, sig=_SIG)
    assert gs.aura_slot.value is None   # 报错路径零写
    assert gs.chosen_aura.value is None


@pytest.mark.parametrize(('opts', 'idx'), [
    (_OPTS, 2), (_OPTS, -1), (None, 0), ([], 0),
])
def test_bad_aura_idx_raises(opts, idx: int) -> None:
    """序号越界 / 名单缺席 = AssertionError(观察未上报即落地 = 调用方 bug),
    两字段零写。"""
    gs = _gs(opts)
    with pytest.raises(AssertionError):
        report_action_aura_select_param(gs, 1, aura_idx=idx, sig=_SIG)
    assert gs.aura_slot.value is None
    assert gs.chosen_aura.value is None


def test_wrong_sig_family_rejected() -> None:
    """渠道族守卫:obs 族签名进动作上报 = 显式炸错(写入口统一校验)。"""
    gs = _gs()
    with pytest.raises(ValueError):
        report_action_aura_select_param(
            gs, 1, aura_idx=0,
            sig=ChannelSig(family='obs', actor='test', mode='read'))
    assert gs.aura_slot.value is None
    assert gs.chosen_aura.value is None
