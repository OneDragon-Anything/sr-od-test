"""sim 策略卡赠礼条件两条效果条目节点窗腿测试(镜像 src = sim/cw_sim_backend.py
的 _begin_node_window 赠礼腿;kernel 触发函数直构面 =
kernel/cw_gain_chain/test_check_strategy_gift_grants.py,本文件锁 sim
窗口接线与世界真值落地面)。

测试面依据 = 迭代设计 designs/T-283-mi-zhi-lvren.md(定稿)§4 锁 4
+ 七裁决点全部默认案(经族级授权自动收口,判定 = designs/REVIEW-T283.md):

- 预种持卡 + 板面 4 巡海游侠 → 下一节点窗开(P1r2 = reward):效果条目1 发
  2★黄泉(携星间旅人星徽入栏)+ 效果条目2 发 1★波提欧,封账两条效果条目复合键并存;
- 窗口重放零双发(_begin_node_window 二次进入,_window_begun_pos 守卫
  整段早退)+ done 闩双层幂等。

驱动形态 = _enter_node_window 直通点。装配/写序记录助手 = 本文件自带
同语义副本(test_sim_backend._backend/_record_all_writes 先例;助手
fixture 不可跨文件 import 故自带,同目录 _isolate_defect_buffer 副本
同款纪律)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GIFT_LEG_FACTION_COUNT,
    STRATEGY_GIFT_LEG_NEXT_REWARD_NODE,
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    bench_units_of,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SimBackend,
)
from sr_od.application.currency_war.sim.cw_sim_ports import (
    install_sim_backend,
    uninstall_sim_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '迷之旅人'

#: 巡海游侠注册表全员四名(上阵即达判据档位 4)。
_RAIDER_FOUR = ('乱破', '不死途', '黄泉', '波提欧')

_SIG = ChannelSig(family='logic_action', actor='TestGiftSimChain',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='TestGiftSimChain')


def _backend(seed: int = 31) -> SimBackend:
    """构造 + 装配(含 kernel 事件钩子订阅;调用方负责 uninstall;
    RunConfig 沿 test_sim_backend._CFG 同形 A8 难度基线)。"""
    backend = SimBackend(seed=seed,
                         cfg=RunConfig(selected_difficulty='A8',
                                       enemy_difficulty=108))
    install_sim_backend(backend)
    return backend


def _record_all_writes(gs: GameState,
                       monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录写序(透传真实现
    零行为变化;test_sim_backend._record_all_writes 同语义副本)。"""
    calls: list[tuple[str, str, str | None, ChannelSig]] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((channel, gs._field_name(target), evidence, sig))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            calls.append(('obs', gs._field_name(target), evidence, sig))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap_logic(gs.write_logic,
                                                        'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return calls


@pytest.fixture
def _prep_backend():
    """装配后端至 P1r1 备战窗 + 持卡获得(调用方负责 uninstall;驱动
    形态先例 = 同目录 test_strategy_node_char_grant_sim_chain)。"""
    b = _backend(31)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    gain_invest_strategy(b.gs, None, _CARD, rand=False, sig=_SIG)
    yield b
    uninstall_sim_backend()


def _seed_board(b) -> None:
    """板面直置 4 巡海游侠(上阵 = 参与判据;容器直置 = sim 测试域
    既有形态,test_strategy_conditional_grant_sim_chain 同源)。"""
    front = [Unit(char_id=n, star=1) for n in _RAIDER_FOUR]
    b.gs.observe(b.gs.deployed,
                 DeployedView(front_slots=front, back_slots=[]),
                 sig=_SIG_OBS)


def _units(gs: GameState) -> list[tuple[str, int]]:
    return [(u.char_id, u.star) for u in bench_units_of(gs)]


def test_both_legs_fire_in_next_window(_prep_backend) -> None:
    """锁 4 主锁:持卡 + 板面 4 巡海 → 下一节点窗(P1r2 = reward)→
    效果条目1 2★黄泉 + 徽入栏 + 效果条目2 1★波提欧,封账两条效果条目复合键并存(世界真值,
    使用面天然可消费)。"""
    b = _prep_backend
    gs = b.gs
    _seed_board(b)
    assert gs.strategy_grants_done.value == (), '前置:开局空底座'
    b._enter_node_window((1, 2))
    units = _units(gs)
    assert ('黄泉', 2) in units, f'效果条目1 备战 2★黄泉: {units}'
    assert ('波提欧', 1) in units, f'效果条目2 备战 1★波提欧: {units}'
    assert '星间旅人星徽' in (gs.equips.value or []), '携带装备入栏'
    assert gs.strategy_grants_done.value == (
        f'{_CARD}#{STRATEGY_GIFT_LEG_FACTION_COUNT}',
        f'{_CARD}#{STRATEGY_GIFT_LEG_NEXT_REWARD_NODE}',
    ), '两条效果条目封账并存(效果条目1 先评、效果条目2 同窗 reward 命中)'


def test_window_replay_no_double_grant(_prep_backend,
                                       monkeypatch: pytest.MonkeyPatch
                                       ) -> None:
    """锁 4 幂等:同节点窗重放(_begin_node_window 二次进入)→ 零新增
    写行、发放物不双发(窗口幂等守卫 + done 闩双层)。"""
    b = _prep_backend
    gs = b.gs
    _seed_board(b)
    b._enter_node_window((1, 2))
    units0 = _units(gs)
    equips0 = list(gs.equips.value or [])
    calls = _record_all_writes(gs, monkeypatch)
    b._begin_node_window()
    assert calls == [], '窗重放出现新增写行'
    assert _units(gs) == units0, '窗重放双发'
    assert list(gs.equips.value or []) == equips0, '徽双发'
    assert len(gs.strategy_grants_done.value) == 2, '封账不追加'
