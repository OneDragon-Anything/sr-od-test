"""T-83/ADR-0609:P2 备战时点节点条台账写点③行为锁(构造场景锁)。

病灶(p26 标定语料 P2 备战轮台账 miss 18/24 实证,判读源 =
p26_calibration/CONDITION_TABLE.md §1.1 覆盖面披露):PlaneNodeLedger
原两个写入端在正常局只覆盖 P1——写点②(投资环境选择后重读,
``cw_screen_invest_env._refresh_node_ledger``)只在开局 1-1 前触发;
写点①(位面详情采集 ``CwScreenPlaneIntel``)仅接管局触发
(``_takeover_collect_if_needed`` 的 briefing_bosses 空门)。P2/P3 节点
序列恒缺 → p26 备战帧采样(读链 = ``ledger_node_type`` 查「当前轮」)
与 flow 掉血回落查表全 miss。实机 4 局对照钉死结构性根因:正常局
P1 每轮命中、P2 r1-r6 全 miss;接管局(session 重建,写点① 触发)
P2 反而命中——写入端缺位,非识别失败。

修复 = 备战帧 heavy 观察(``CwScreenPrep._probe_node_type``,每备战帧
已在读节点行序列)加写点③:读数按位合并进 session 权威表。对齐语义:
槽 idx(0-based)= 该位面第 idx+1 轮(cw_node_reader「槽 i = 第 1+i 轮」)
与台账 seq 下标同基零换算;current 槽已由 ``read_node_sequence`` 的
OCR 标签带位置覆盖填值 → 备战查表「当前轮」从本位面首个 clean 备战帧
起命中;投资环境变异窗内不写(与三票校验豁免窗同语义);None 位保旧
(合并语义,past 槽不覆盖历史非 None 读数)。

变异红证 = 临时删除写点③调用 → 本文件全部用例翻红(验证记录见交付
报告);离线宿主 = test_cw_obs_chain._make_director 同款
(object.__new__ 免 SrContext,真核直调)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.obs.cw_observation as cw_observation
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    get_node_ledger,
    ledger_node_type,
    ledger_update_plane,
)
from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)

# ===== 测试基建 =====


def _slot(idx: int, state: str, node_type: str | None) -> NodeSlot:
    """节点槽合成(idx 0-based 左→右;state=past/current/upcoming)。"""
    return NodeSlot(idx=idx, cx=idx * 100, cy=40, state=state,
                    node_type=node_type, hu_dist=None)


def _p2_frame_slots() -> list[NodeSlot]:
    """P2 r3 备战帧形态:5 槽,past×2(变暗读 None)+ current(OCR 标签
    覆盖 'battle')+ upcoming×2(Hu 命中)。即 read_node_sequence 出口
    真实形状(含 current 的 OCR 覆盖)。"""
    return [_slot(0, 'past', None),
            _slot(1, 'past', None),
            _slot(2, 'current', 'battle'),
            _slot(3, 'upcoming', 'reward'),
            _slot(4, 'upcoming', 'encounter')]


def _make_prep(monkeypatch: pytest.MonkeyPatch,
               session: StrategySession,
               slots: list[NodeSlot],
               plane: int = 2,
               round_num: int = 3) -> CwScreenPrep:
    """免 ctx 构造 CwScreenPrep + 读屏替身(obs_chain._make_director 同款)。

    read_node_sequence 替身产出合成槽序;采集钩子 stub(不落盘);
    last_state = 合成帧(plane/round = 写点③位面键与「当前轮」锚,
    生产真值 = 备战环 heavy 观察先于 probe 落 last_state);传入
    screen=object() 走「透传帧」路径,零截图。
    """
    d = object.__new__(CwScreenPrep)
    session.last_state = GameState(plane=plane, round_num=round_num)
    d.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    monkeypatch.setattr(cw_observation, 'read_node_sequence',
                        lambda ctx, screen: slots)
    monkeypatch.setattr(d, '_capture_unrecognized_node_icons',
                        lambda *a, **k: None)
    return d


# ===== 锁 1(核心):P2 备战轮节点条必有 =====


def test_p2_empty_ledger_prep_frame_fills_current_round(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P2 台账空(正常局病灶形态)→ 备战帧 probe 后 p26 读链必命中。

    红证 = 删除写点③后 ``ledger_node_type`` 返回 None(与实机 miss
    18/24 同形态)。断言面即 p26 钩子读链本体(recorder 采样同源调用),
    「台账落了」不是目的,「当前轮查表有值」才是行为承诺。"""
    sess = StrategySession()
    assert ledger_node_type(sess, 2, 3) is None, '前置:病灶形态台账应空'
    d = _make_prep(monkeypatch, sess, _p2_frame_slots())
    d._probe_node_type(screen=object())
    # p26 读链:备战 r3 帧 → seq[2] = current 槽 OCR 覆盖值
    assert ledger_node_type(sess, 2, 3) == 'battle', \
        'P2 备战轮节点条 miss(写点③未生效或对齐错位)'
    # upcoming 位同帧入表(Hu 值),按 idx 对齐零漂移
    assert ledger_node_type(sess, 2, 4) == 'reward'
    assert ledger_node_type(sess, 2, 5) == 'encounter'


def test_prep_ledger_plane_alignment_uses_last_state_plane(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """位面键 = last_state.plane(P2 帧 → seq_by_plane[2],禁误落 P1)。"""
    sess = StrategySession()
    d = _make_prep(monkeypatch, sess, _p2_frame_slots())
    d._probe_node_type(screen=object())
    ledger = get_node_ledger(sess)
    assert ledger is not None and 2 in ledger.seq_by_plane, 'P2 序列未落表'
    assert 1 not in ledger.seq_by_plane, 'P2 帧读数误落 P1 键'
    assert ledger.seq_source.get(2) == 'prep_row', '写入来源标错'


# ===== 锁 2:变异窗守卫(合法变异不落表)=====


def test_env_grace_window_blocks_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """投资环境变异窗内节点行合法变异中 → 不写(与三票校验豁免窗同语义)。

    红证 = 删守卫后变异中序列被当真值落表。窗过期后同帧读数正常入表
    (守卫是时间窗,不是永久拒绝)。"""
    import time as _time

    sess = StrategySession()
    d = _make_prep(monkeypatch, sess, _p2_frame_slots())
    ledger = get_node_ledger(sess)
    assert ledger is not None
    ledger.env_grace_until = _time.monotonic() + 30.0
    d._probe_node_type(screen=object())
    assert ledger_node_type(sess, 2, 3) is None, \
        '变异窗内写表(变异中序列被当真值)'
    ledger.env_grace_until = 0.0
    d._probe_node_type(screen=object())
    assert ledger_node_type(sess, 2, 3) == 'battle', '窗过期后未恢复写入'


# ===== 锁 3:None 位保旧(合并语义,past 槽不洗历史值)=====


def test_none_slots_preserve_existing_values(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """预置 plane_detail 源全量序 → 备战帧 past 位 None 不覆盖非 None 旧值。

    承重 = ledger_update_plane 按位合并语义在写点③链路上的兑现:备战行
    只补「本帧可读位」,永不把已识别位洗成 None。"""
    sess = StrategySession()
    ledger_update_plane(sess, 2,
                        ['battle', 'reward', None, None, 'encounter'],
                        'plane_detail')
    d = _make_prep(monkeypatch, sess, _p2_frame_slots())
    d._probe_node_type(screen=object())
    assert get_node_ledger(sess).seq_by_plane[2] == \
        ['battle', 'reward', 'battle', 'reward', 'encounter'], \
        '合并结果漂移(None 位应保旧,非 None 位按帧覆盖)'


# ===== 锁 4:P1 幂等(已有值位读数一致 → 无害重写)=====


def test_p1_existing_ledger_stays_consistent(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P1 已有台账(开局环境选择写入)→ 备战帧同值重写幂等,值不漂移。

    辖修复零回归:写点③在 P1 上叠写不改变 P1 判读面(p26 P1 命中率
    修复前已 59/60,不因本批变化)。"""
    sess = StrategySession()
    ledger_update_plane(sess, 1,
                        ['reward', 'reward', 'battle', None, 'supply'],
                        'prep_row')
    # P1 r3 帧:current='battle'(与预置一致),upcoming 读数照常入表
    slots = [_slot(0, 'past', None),
             _slot(1, 'past', None),
             _slot(2, 'current', 'battle'),
             _slot(3, 'upcoming', 'battle'),
             _slot(4, 'upcoming', 'supply')]
    d = _make_prep(monkeypatch, sess, slots, plane=1)
    d._probe_node_type(screen=object())
    seq = get_node_ledger(sess).seq_by_plane[1]
    assert seq == ['reward', 'reward', 'battle', 'battle', 'supply']
    assert ledger_node_type(sess, 1, 3) == 'battle'


# ===== 锁 5:轮位对齐门(漏检圆错位帧拒写,落地审建议修)=====


def test_misaligned_current_slot_frame_rejected(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """检测圆中段漏检 → 槽枚举序整体左移 → current 槽 idx 与 round_num 失配
    → 拒写本帧(错位合并会把类型写错绝对位且 past 位不可自愈)。

    构造:r3 帧(应 current@idx2)漏检 idx1 圆,current 落在 idx1(左移一
    位),upcoming 随之左移且末槽缺。红证 = 删轮位对齐门 → 台账落错位序
    [None,'battle','reward',None](current 类型进 r2 位)。正对照 = 下一
    帧(检测恢复,对齐)照常写入,拒写是帧级不丢位面。"""
    sess = StrategySession()
    # 错位形态:枚举序 4 槽(current@idx1,末槽缺)
    misaligned = [_slot(0, 'past', None),
                  _slot(1, 'current', 'battle'),
                  _slot(2, 'upcoming', 'reward')]
    d = _make_prep(monkeypatch, sess, misaligned)
    d._probe_node_type(screen=object())
    assert ledger_node_type(sess, 2, 3) is None, '错位帧被写入(轮位对齐门失守)'
    assert 2 not in get_node_ledger(sess).seq_by_plane, '错位帧整序入表'
    # 下一帧检测恢复(对齐形态)→ 正常写入,位面不因单帧拒写丢失
    d2 = _make_prep(monkeypatch, sess, _p2_frame_slots())
    d2._probe_node_type(screen=object())
    assert ledger_node_type(sess, 2, 3) == 'battle', '对齐帧未恢复写入'
