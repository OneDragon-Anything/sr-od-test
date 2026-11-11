"""羁绊档位条件发放 sim 全链轻量局测试(镜像 src 主断言对象 = T-41
特邀专家:加拉赫击破档分支经 sim 后端全链;按流程级测试落位本目录,引擎
驱动助手 import 自 sim/test_sim_backend.py〔已登记超限拆分债文件,禁追加,
只 import 复用不改;先例 = 本目录 test_env_expert_invite_sim_chain.py〕)。

测试面依据 = 迭代 本文件锁面申报§4 锁 4(§2.3/§2.4 落地形态):
- 加拉赫环境 + 击破阵容部署过 2 档 → equips 出现以太钻头(库尾追加)+
  done 封账 bond_tier_2(实机(live)和模拟器(sim)两边同链:deployed 逻辑写 → 值回调级联 →
  尾部门外必查 → 发放原语,零 sim 私有接入调用);
- 对照局(无环境)同操作零发放。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _backend,
    _env_pick_backend,
    _seed_and_pick_env,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SimBackend,
    uninstall_backend,
)

_SIG = ChannelSig(family='logic_action', actor='SimBackendTest',
                  mode='compute')

_ENV = '特邀专家:加拉赫'
_EQUIP = '以太钻头'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(前清防他测残留、后清防本测外泄——沿
    sim/test_sim_backend 同名 fixture 先例,fixture 不可跨文件 import
    故本文件自带同名同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _deploy_pair(gs) -> None:
    """击破阵容部署过 2 档(deployed 逻辑写 = 板面动作同口,值回调级联
    自动触发羁绊档位判据;乱破/大丽花均为击破出身)。"""
    gs.write_logic(gs.deployed, _dvs([Unit(char_id='乱破', star=1),
                                      Unit(char_id='大丽花', star=1)], []),
                   produced_by='test', evidence='t:deploy', sig=_SIG)


def test_bond_tier_grant_fires_in_sim(_isolate_defect_buffer) -> None:
    """目标局(T-41 设计 §4 锁 4):选特邀专家:加拉赫 → 击破部署过
    2 档 → equips 出现以太钻头 + done 封账(发放分支与状态副本事实同状态容器,
    live/sim 同链)。"""
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _ENV)
        assert gs.active_env.value == _ENV, '选卡事实前置'
        _deploy_pair(gs)
        assert gs.equips.value is not None \
            and gs.equips.value[-1] == _EQUIP, \
            f'库尾追加以太钻头: {gs.equips.value!r}'
        assert (_ENV, 'bond_tier_2') in (gs.env_grants_done.value or ()), \
            f'done 封账: {gs.env_grants_done.value!r}'
    finally:
        uninstall_backend()


def test_no_env_control_zero_grant(_isolate_defect_buffer) -> None:
    """对照局(无环境)同操作零发放:同 seed 同部署,无环境即无表条目,
    equips 零以太钻头、done 零 bond_tier 键。"""
    b: SimBackend = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        assert not gs.active_env.value, '无环境前置'
        _deploy_pair(gs)
        assert _EQUIP not in (gs.equips.value or []), \
            f'对照局零发放: {gs.equips.value!r}'
        done = gs.env_grants_done.value or ()
        assert not [k for _e, k in done if k.startswith('bond_tier_')], \
            f'对照局零 done: {done!r}'
    finally:
        uninstall_backend()
