"""三新画面观察域字段家族测试(幕后茶歇/奇遇对话/主角光环选择;
design 2026-11-20-cw-p0-chain §2.8,tasks 2.4 产出)。

锁的设计约定(kernel/cw_game_state.py 三新画面观察域):
- 三态开局初值:8 字段开局 = None(未观察;sim 无画面识别恒 None);
- 写读守卫:观察整表覆盖写 → 读回原序同值(名字域与坐标域同门同序
  等长的 game state 半边——写端构造守卫随 report 函数批落,不在本文件);
- 读缺跳写红线:observe 拒绝 None(「读到空」与「未读到」同判保持
  None,不设空列表态——report 读缺跳写闸的底层依据);
- 离屏清场:leave_screen 置 None(evidence=left_screen);路由点陈旧
  清点(_route_clear_stale_payloads)按 _PAYLOAD_DOMAINS 属屏保活/清场
  ——三屏均一次性访问瞬态画面,防跨屏携陈值;
- 注册表闭合:_PAYLOAD_DOMAINS 每键 = GameState 真实 Field 属性 +
  DEFAULT_GS_SCHEMA 注册行(跨表互恰,孤儿键当场红)。
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext

from sr_od.application.currency_war.kernel.cw_game_state import (
    _PAYLOAD_DOMAINS,
    DEFAULT_GS_SCHEMA,
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.operations.cw_loop import CwLoop

#: 三新画面观察域 8 字段(与生产字段清单同源;漂移 = 本文件先红)。
_NEW_SCREEN_FIELDS: tuple[str, ...] = (
    'tea_break_opts', 'tea_break_opts_xy',
    'adventure_partner_name', 'adventure_card_opts', 'adventure_card_opts_xy',
    'aura_select_opts', 'aura_select_opts_xy', 'aura_select_preview_xy',
)

#: 测试侧观察签名(通道合法即可;actor 沿 report 函数族命名习惯)。
_TEST_SIG: ChannelSig = ChannelSig(family='obs', actor='CwScreenTeaBreak',
                                   screen='货币战争-幕后茶歇', mode='read')


def _new_game_state() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def test_new_screen_fields_three_states_and_write_read_guard() -> None:
    """三态初值 + 写读守卫 + 读缺红线:开局 8 字段全 None;观察整表
    覆盖写后读回同序同值;observe(None) 显式炸错(读缺跳写的底层依据);
    leave_screen 清场回 None(evidence=left_screen)。"""
    gs = _new_game_state()
    for name in _NEW_SCREEN_FIELDS:
        assert getattr(gs, name).value is None, \
            f'{name} 开局应为未观察 None(三态初值)'

    # 写读守卫(名字域/坐标域同门同序等长的读回半边)
    gs.observe(gs.tea_break_opts, ['摇茶加成', '全队强化'], sig=_TEST_SIG)
    gs.observe(gs.tea_break_opts_xy, [(560, 400), (1200, 400)], sig=_TEST_SIG)
    assert gs.tea_break_opts.value == ['摇茶加成', '全队强化'], \
        '名字域读回应保序同值'
    assert gs.tea_break_opts_xy.value == [(560, 400), (1200, 400)], \
        '坐标域读回应保序同值(同门同序等长)'
    assert gs.tea_break_opts.source == 'observation', \
        '观察写应落 observation 来源(三态判定输入)'

    # 读缺红线:失读禁写 None(保持未观察态的唯一合法路径 = 不写)
    with pytest.raises(ValueError):
        gs.observe(gs.aura_select_opts, None, sig=_TEST_SIG)

    # 离屏清场(画面附加域显式例外;非清场域走此口会显式炸错)
    gs.leave_screen(gs.tea_break_opts_xy, sig=_TEST_SIG)
    assert gs.tea_break_opts_xy.value is None, '离屏清场应置 None'
    assert gs.tea_break_opts_xy.evidence == 'left_screen', \
        '离屏清场 evidence 应为 left_screen(结构事实非失读)'


def test_route_clear_keeps_own_screen_and_clears_off_screen(
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """路由点陈旧清点:属屏在屏 → 本屏槽保活、他屏槽清;无屏名语境
    (非身份分支/未识别)→ 全清——离屏清场防跨屏携陈值的接线语义。"""
    gs = _new_game_state()
    _seeded = {
        'tea_break_opts': ['摇茶加成', '全队强化'],
        'tea_break_opts_xy': [(560, 400), (1200, 400)],
        'adventure_partner_name': '姬奇猫',
        'adventure_card_opts': ['强化选项', '金卡选项'],
        'adventure_card_opts_xy': [(1300, 600), (1500, 600)],
        'aura_select_opts': ['光环甲', '光环乙'],
        'aura_select_opts_xy': [(420, 480), (1500, 480)],
        'aura_select_preview_xy': [(640, 640), (900, 640)],
    }
    for name, value in _seeded.items():
        gs.observe(getattr(gs, name), value, sig=_TEST_SIG)
    loop = CwLoop.__new__(CwLoop)
    loop.ctx = test_context
    monkeypatch.setattr(test_context, 'cw_match', SimpleNamespace(gs=gs))

    # 属屏 = 幕后茶歇:茶歇双槽保活,奇遇/光环五槽清
    loop._route_clear_stale_payloads('货币战争-幕后茶歇')
    assert gs.tea_break_opts.value == _seeded['tea_break_opts'], \
        '属屏在屏时名字域应保活(当前画面 payload)'
    assert gs.tea_break_opts_xy.value == _seeded['tea_break_opts_xy'], \
        '属屏在屏时坐标域应与名字域同格保活'
    for name in ('adventure_partner_name', 'adventure_card_opts',
                 'adventure_card_opts_xy', 'aura_select_opts',
                 'aura_select_opts_xy', 'aura_select_preview_xy'):
        assert getattr(gs, name).value is None, \
            f'非属屏槽 {name} 应被路由清点(防跨屏携陈值)'

    # 无屏名语境:剩余属屏槽也清(全清,该语境无任何 decide 消费)
    loop._route_clear_stale_payloads(None)
    assert gs.tea_break_opts.value is None, \
        '无屏名语境应全清(映射外建档屏/非身份分支语义)'


def test_payload_registry_closure_no_orphan_keys() -> None:
    """注册表闭合:_PAYLOAD_DOMAINS 每键 = GameState 真实 Field 属性
    (全表不变量——映射键摸不到真实字段时 leave_screen/清点即断);
    新增 8 槽逐字段全闭合 = 字段属性 + DEFAULT_GS_SCHEMA 注册行 +
    画面归属映射行(新增槽漏登记任一表 = 当场红)。注:存量旧槽的
    schema 键为域粒度(先例 invest_opts 一键覆盖双字段),故 schema
    逐键闭合只锁本批新增的逐字段键形态。"""
    gs_field_names = {f.name for f in dataclasses.fields(GameState)}
    for key in _PAYLOAD_DOMAINS:
        assert key in gs_field_names, \
            f'{key} 在画面归属映射但非 GameState 字段(孤儿键)'
    for name in _NEW_SCREEN_FIELDS:
        assert name in DEFAULT_GS_SCHEMA, \
            f'{name} 缺 DEFAULT_GS_SCHEMA 域版本注册行'
        assert name in _PAYLOAD_DOMAINS, \
            f'{name} 三新画面观察域字段漏 _PAYLOAD_DOMAINS 登记' \
            f'(离屏清场失联)'
