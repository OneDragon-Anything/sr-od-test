"""部署 cap 板满门三锁(迭代 2026-09-18-prep-obs-retirement 阶段 3.1)。

事故形态 = match_g_20260918_023823(定谳见 .debug/temp/incidents/
20260918-reconcile/rootcause-reopen.md 案一):板满 3/3 时决策帧黑板名单
一拍陈旧(2 人),cap 门槛按 2/3 放行第 4 拖,游戏静默拒收 → 账实失配停局。
修后部署输入改容器现读 + 显式板满门(``_deploy_cap_full_gate``,占用数
口径),门拒因 ``deploy_cap_full`` 落 cw4_counters 计划级分键(帧级去重)。
"""
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_comp,
    cw4_gs,
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_game_state import BenchSlot, Unit
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def _bs(name: str, slot: int) -> BenchSlot:
    """容器占席条目(P4 载体迁移:MandateFrame 直构面)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=1))


def _full_board_session():
    """容器 3/3 满板(上阵前 3 人)+ 备战席候选;返回 (session, gs)。"""
    session = cw4_session(cw4_comp())
    gs = cw4_gs(session, deploy_cap=3, bench=[cw4_bc('艾丝妲')],
                front_row=[Unit(char_id='丹恒·饮月', star=1),
                           Unit(char_id='卡芙卡', star=1),
                           Unit(char_id='杰帕德', star=1)])
    return session, gs


def _stale_frame(round_num: int = 2):
    """陈旧决策帧:黑板名单仍是 2 人(缺刚上场的第 3 人)——事故帧形态。
    P4 容器形:bench = 占席条目,deployed = 行域 Unit。"""
    return mandate.MandateFrame(
        gold=10, level=3,
        bench=[_bs('艾丝妲', slot=1)],
        deployed=[Unit( char_id='丹恒·饮月', star=1),
                  Unit( char_id='卡芙卡', star=1)],
        deploy_cap=3, node_type=None, stop_flag=False,
        k_members=(), round_num=round_num)


def test_cap_full_stale_frame_emits_nothing():
    """事故形态锁:容器 3/3 满 + 决策帧黑板 2 人(陈旧)→ 零拖拽发射、放行 False。"""
    session, gs = _full_board_session()
    frame = _stale_frame()
    assert mandate._deployable(frame, session, gs) is False
    out: list = []
    mandate._emit_deploy_moves(out, frame, session, gs, 'm1_test')
    assert out == []


def test_cap_roomy_stale_container_still_deploys():
    """陈旧视图锁:容器 2/3 未满时照常产出部署(换源不改坏正常路径);
    容器名单为部署输入真值——板满判定读容器而非帧。"""
    session = cw4_session(cw4_comp())
    gs = cw4_gs(session, deploy_cap=3, bench=[cw4_bc('艾丝妲')],
                front_row=[Unit(char_id='丹恒·饮月', star=1),
                           Unit(char_id='卡芙卡', star=1)])
    stale = _stale_frame()
    assert mandate._deployable(stale, session, gs) is True
    out: list = []
    mandate._emit_deploy_moves(out, stale, session, gs, 'm1_test')
    assert len(out) == 1


def test_cap_full_counter_frame_dedup():
    """拒因台账锁:板满帧 → cw4_counters['deploy_cap_full'] 计数,同帧
    (plane, round) 去重;跨帧(round 推进)再计。"""
    session, gs = _full_board_session()
    counters = state_of(session).cw4_counters
    assert mandate._deploy_cap_full_gate(session, gs, _stale_frame()) is True
    assert counters.get('deploy_cap_full') == 1
    # 同帧重复判定(同次备战访问内 M1/M5/wanted 臂多次过门)不再计数
    assert mandate._deploy_cap_full_gate(session, gs, _stale_frame()) is True
    assert counters.get('deploy_cap_full') == 1
    # 轮次推进 = 新帧,再计
    assert mandate._deploy_cap_full_gate(session, gs, _stale_frame(round_num=3)) is True
    assert counters.get('deploy_cap_full') == 2
