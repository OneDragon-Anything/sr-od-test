"""sim 策略延时发放窗口腿测试(镜像 src = sim/cw_sim_backend.py 的
_begin_node_window 策略发放腿;kernel 原语单元面 =
kernel/cw_gain_chain/test_discharge_due_strategy_grants.py,本文件锁
sim 窗口接线与世界真值落地面)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 4(sim 端到端
形态)与锁 5 同源幂等申报 + T-107 展开卡批(designs/T-107-rencai-jili-plus.md
§4 锁 3 参数化 +本卡变体):
- 到点(本 advance 递减到 0)同窗发放:装备栏 +1 员工投影仪 + 队列弹除
  + 到点留证披露键(值 = 触发卡@frame:发放物,姊妹双卡参数化:人才
  激励 / 人才激励+)+ 发放写行 sig 组 'sim:strategy_grant';
- 未到点零发放(队列悬置递减,装备栏零动,披露键缺席);
- 同节点窗重放(_window_begun_pos 守卫)整段跳过不双发。

驱动形态 = _enter_node_window 直通点(锚定补推路径真形态:观察锚定 →
推进 tick 递减 → 返回后开窗,递减先于发放的时序由真实路径承载);
引擎驱动助手 import 自 sim/test_sim_backend.py(在册超限拆分债文件,
禁追加,只 import 复用不改)。"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _backend,
    _record_all_writes,
)

from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    STRATEGY_DELAYED_GRANT_FIRED,
    uninstall_backend,
)

_CARD = '人才激励'
_ITEM = '员工投影仪'

_EVIDENCE_PREFIX = 'strategy_grant_due'


@pytest.fixture
def _prep_backend():
    """装配后端至 P1r1 备战窗(调用方负责 uninstall;驱动形态先例 =
    同目录 test_strategy_encounter_battle_grant_sim_chain)。"""
    b = _backend(7)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    return b


def _seed_queue(b, queue: tuple) -> None:
    b.gs.write_logic(b.gs.pending_strategy_grants, queue,
                     produced_by='test-seed', evidence='t:queue', sig=_SIG)


@pytest.mark.parametrize('card', [_CARD, '人才激励+'])
def test_due_grants_equipment_in_window(
        _prep_backend, monkeypatch: pytest.MonkeyPatch,
        card: str) -> None:
    """到点同窗发放(锁 4 sim 端到端,姊妹双卡参数化:种子队列按卡名
    经真实注册表查行):种子队列 remaining=1 → 进 (1,2) 窗(锚定补推
    先递减 1→0,再开窗)→ 装备栏 +1 员工投影仪 + 队列弹除 + 披露键
    <卡名>@1-2:员工投影仪 + 发放写行 sig 组 'sim:strategy_grant'
    (与环境 'sim:env' 分组)。"""
    b = _prep_backend
    try:
        gs = b.gs
        equips_before = list(gs.equips.value or [])
        _seed_queue(b, ((card, 1),))
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert gs.equips.value == equips_before + [_ITEM], \
            f'装备栏: {gs.equips.value}'
        assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
        assert b.disclosures[STRATEGY_DELAYED_GRANT_FIRED] \
            == f'{card}@1-2:{_ITEM}', f'留证披露: {b.disclosures}'
        rows = [c for c in calls
                if c[2] is not None and c[2].startswith(_EVIDENCE_PREFIX)]
        fields = sorted({c[1] for c in rows})
        assert fields == ['equips', 'pending_strategy_grants'], \
            f'发放写行字段面漂移: {rows}'
        for c in rows:
            assert c[3].family == 'logic_action' \
                and c[3].group_id == 'sim:strategy_grant', \
                f'sig 组漂移: {c}'
    finally:
        uninstall_backend()


def test_not_due_zero_grant_queue_only_decrement(_prep_backend) -> None:
    """未到点(锁 4 反面):remaining=2 → 进 (1,2) 窗只递减 2→1(kernel
    tick 腿),零发放零弹除,披露键缺席。"""
    b = _prep_backend
    try:
        gs = b.gs
        equips_before = list(gs.equips.value or [])
        _seed_queue(b, ((_CARD, 2),))
        b._enter_node_window((1, 2))
        assert gs.pending_strategy_grants.value == ((_CARD, 1),), \
            f'队列: {gs.pending_strategy_grants.value}'
        assert gs.equips.value == equips_before, '未到点误入栏'
        assert STRATEGY_DELAYED_GRANT_FIRED not in b.disclosures, \
            '未到点误发留证'
    finally:
        uninstall_backend()


def test_window_replay_guard_no_double_grant(
        _prep_backend, monkeypatch: pytest.MonkeyPatch) -> None:
    """窗重放守卫(锁 5 幂等):同节点窗重放(_begin_node_window 二次
    进入,_window_begun_pos 守卫整段早退)→ 零新增写行,装备栏不双发。"""
    b = _prep_backend
    try:
        gs = b.gs
        _seed_queue(b, ((_CARD, 1),))
        b._enter_node_window((1, 2))
        assert gs.equips.value.count(_ITEM) == 1, '前置:首窗已发放'
        calls = _record_all_writes(gs, monkeypatch)
        b._begin_node_window()   # 同节点窗重放(直构)
        assert gs.equips.value.count(_ITEM) == 1, '窗重放双发'
        assert calls == [], '窗重放出现新增写行'
    finally:
        uninstall_backend()
