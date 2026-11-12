"""cw_screen_prep 镜像测试(按被测方法拆目录):_observe heavy 段
惊喜盒板件调用点行为。

镜像规范:cw_screen_prep.py 已超 800 行拆目录线,新测试按被测方法落
operations/cw_screen/cw_screen_prep/。锁面 = 迭代设计
原稿锁面(§ 号 = 原稿节序)§4.5:调用点触发即写(检测生成路径真实跑,不桩生成端)/ 零写路径经写
入口 no-op 证实 / 晶矿链真实读口回归零扰动(read_ore_sights 不桩)。
盒+球同区共存帧 fixture 未采(设计 §7 归校准批补采),共存不互扰暂由
两帧各自断言承担。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
    run_node,
)

import sr_od.application.currency_war.operations.cw_screen.cw_screen_prep as prep_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    NodeKey,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

_SCREEN = '货币战争-备战'
_SIG = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')


def _run_heavy(test_context, monkeypatch, session: StrategySession,
               screen) -> None:
    """heavy 观察跑壳:壳桩只替「与本锁无关的读屏点」(observe_full 假
    回执 plane=1 r=2 / 布局与部署读桩空)——晶矿读口与 giftbox 检测跑
    真实路径(read_ore_sights 刻意不桩 = 晶矿链回归面;桩集形态 =
    test_node_chain heavy 跑壳同款)。"""
    from sr_od.application.currency_war.obs import cw_observe_full as ofm

    gs = game_state_of(session)

    def _fake_observe_full(ctx, scr, **kw):
        gs.observe(gs.node, NodeKey(plane=1, round_num=2, kind='prep'),
                   evidence='t', sig=_SIG)
        return {
            'bench_view': None, 'deployed_rows': None,
            'read_receipt': SimpleNamespace(plane=1, round_num=2, level=None),
            'node_slots': None,
            'owned_equips': None, 'occupied_equips': None,
            'substate': {},
        }

    monkeypatch.setattr(ofm, 'observe_full', _fake_observe_full)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op = CwScreenPrep(test_context)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr2, s, a, **k: SimpleNamespace(
                            is_success=False))
    monkeypatch.setattr(op, '_reconcile_tracking',
                        lambda bv, dr, scr2: (None, None, None))
    monkeypatch.setattr(prep_mod, 'row_area_centers', lambda ctx, name: [])
    monkeypatch.setattr(prep_mod, 'read_deploy_cap', lambda ctx, scr2: None)
    monkeypatch.setattr(prep_mod, 'read_deployed_count',
                        lambda ctx, scr2: None)

    run_node(test_context, op, lambda: op._observe(True, screen=screen))


def test_hook_writes_giftbox_on_box_frame(test_context, monkeypatch) -> None:
    """调用点触发即写:盒帧 heavy 观察 → giftbox_sight 落 (12,)(真实检测
    生成路径:模板资产 + 徽章 OCR 全真,不桩生成端)。evidence 非空且含
    本帧序位注记(fake 回执锚定 p1-r2)。"""
    if not test_context.has_screen(_SCREEN, 'reward_giftbox_phantom'):
        pytest.skip(
            f'存档截图缺失:screens/{_SCREEN}/reward_giftbox_phantom.webp')
    frame = test_context.load_screen(_SCREEN, 'reward_giftbox_phantom')
    session = cw4_session()

    _run_heavy(test_context, monkeypatch, session, frame)

    gs = game_state_of(session)
    assert gs.giftbox_sight.value == (12,), 'heavy 段调用点触发即写'
    assert gs.giftbox_sight.source == 'observation', '观察通道写入'
    assert gs.giftbox_sight.evidence == 'giftbox#p1-r2', \
        'evidence 非空含序位(prov 时间线锚)'


def test_hook_zero_write_and_ore_chain_on_boxless_frame(
        test_context, monkeypatch) -> None:
    """零写路径 + 晶矿链回归:无盒帧(晶矿球同区)heavy 观察 →
    giftbox_sight 保持原值(检测零命中 → 写入口 no-op 零写,滞留语义),
    晶矿链真实读口照常写(spheres count>0,链回归零扰动)。"""
    if not test_context.has_screen(_SCREEN, 'reward_spheres_8'):
        pytest.skip(f'存档截图缺失:screens/{_SCREEN}/reward_spheres_8.webp')
    frame = test_context.load_screen(_SCREEN, 'reward_spheres_8')
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.giftbox_sight, (7,), evidence='giftbox#p1-r1', sig=_SIG)

    _run_heavy(test_context, monkeypatch, session, frame)

    assert gs.giftbox_sight.value == (7,), '零命中 → 零写,域原值保持(滞留)'
    assert gs.giftbox_sight.evidence == 'giftbox#p1-r1', '无新写(来源保持)'
    assert gs.spheres.value is not None and gs.spheres.value.count > 0, \
        '晶矿链真实读口照常写(回归零扰动)'
