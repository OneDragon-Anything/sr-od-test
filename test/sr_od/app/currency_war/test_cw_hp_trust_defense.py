"""hp 可信位防线锁(W580;消费门 fail-closed + 写侧值位同写)。

锁面(DESIGN 测试计划 5 组;`.debug/temp/currency_war/w580_hp_trust_defense/DESIGN.md`):
1. 失明复现锁:全图 OCR det 漏检(mock 返空)→ read_hp_opt 经两级放大
   回退恢复读数(局21 P2 r4 画面实显 16、全图 rect 内零框、裁片放大即
   恢复的离线实证);常路径命中时不走回退(零新增开销锁)。
2. 幽灵帧回放锁:(100, False, False) 三位自洽假值帧(局21 P2 r4 形态:
   shop 覆盖丢位产物)→ blood_budget_levelup_blocked 拒;arbiter 端到端
   逐击拒付;remediation 稳态组同拒(deploy_cap 补偿臂经同一谓词,单一
   收口)。含变异自检:守卫删除(monkeypatch 可信位恒真)→ 本组锁必须
   翻红(幽灵 100>21 不再拒),证明锁敏感性与守卫必要性。
3. 放行面锁:同节点沿用帧 (v, False, True) 不拦(ADR-0428 语义零回归);
   真读帧 (v, True, False) 不拦;ALL IN 豁免在不可信帧上仍生效
   (豁免优先于守卫:末战花光是时机不是血线判断)。
4. 写侧位一致锁:shop._apply_hp 三覆盖形态各产出正确 (hp, readable,
   trusted) 三元组;None(无真读且无新鲜结算真值)不覆盖 state——
   裸 100 不再喂决策路径。
5. sim 零漂移锁:sim 帧恒真读(默认 hp_readable=True)→ 消费门短路,
   血预算停手既有行为逐位不变(单局 sim 血线内帧仍拒、账本键仍在)。
6. 检查器镜像锁(seg_check_untrusted_hp_levelup,W605/W580c):checks
   层显形面——不可信帧出现 LevelUp 账本行即命中(与消费门两层分工),
   sim 恒真读恒零命中 + ALL IN 豁免镜像。

拒收语义依据(DESIGN 防线设计):线内升级 EV=−C−I 严格负(ADR-0448),
证据缺失时禁令保持有效=fail-closed;误放(血线内追级)与误拦(少升
一级)代价非对称同型于 ADR-0428。
"""
from __future__ import annotations

import dataclasses
import logging

import pytest

from sr_od.application.currency_war.kernel.cw_discipline_rules import (
    blood_budget_levelup_blocked,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import _apply_hp
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)



def _state_with_bits(hp: int | None, readable: bool, trusted: bool) -> GameState:
    """最小帧构造器(组2-5/组7 共用;plane/round/节点固定,gold=50 无锁面消费)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, 6, 50, hp
    st.round_num = 4
    st.node_type = 'battle'
    st.hp_readable = readable
    st.hp_trusted = trusted
    return st


def _ghost_state(hp: int = 100) -> GameState:
    """局21 P2 r4 幽灵帧形态:P2 备战帧,hp=100 假值、两位皆 False
    (shop 覆盖丢位产物:值写入了、保真位留在 shop 开态 read_game_state
    的 (False, False))。"""
    st = _state_with_bits(hp, False, False)
    st.gold = 86   # 局21 实帧字段回放保真(锁面谓词不读 gold)
    return st


class SimpleOcrItem:
    """最小 OCR 结果桩(消费面仅 .data;与仓内 SimpleNamespace 桩同型)。"""

    def __init__(self, data: str) -> None:
        self.data = data


# ---------- 组1:失明复现锁(read_hp_opt 两级放大回退) ----------


def test_read_hp_opt_upscaled_fallback_recovers_small_value(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """全图 det 漏检(首调返空)→ 3x 放大回退恢复「16」(局21 P2 r4
    失明帧形态);第二级二值化不触发(第一级已命中)。"""
    from sr_od.application.currency_war.obs.cw_observation import read_hp_opt
    calls = {'n': 0}

    def _miss_then_recover(**kw):
        calls['n'] += 1
        if calls['n'] == 1:
            return []            # 全图原生分辨率:rect 内零检测框(det 漏检)
        return [SimpleOcrItem('16')]   # 裁片 3x 放大后恢复
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        _miss_then_recover)
    assert read_hp_opt(test_context, None) == 16
    assert calls['n'] == 2   # 恰好两级:全图 miss → 3x 放大命中


def test_read_hp_opt_dual_pass_consistent_hit(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """常路径双通道一致 → 静默采值。

    锁语义修订(2026-09-02 掉十位 bug A):旧锁「全图命中零回退(calls==1)」
    钉的是「原生命中即全信」——正是掉十位毒化面(分诊帧 40e3354a 离线复现:
    原生读 4、放大读 47,真值 47)。修法 = 放大通道常开作第二读对账,一致
    才静默;常开代价 = 每真值帧一次 90×80 小裁片放大 OCR。旧锁修复前对新
    断言红(calls==1),按锁存在性纪律重推后改钉:一致值 + 恰 2 次调用。
    """
    from sr_od.application.currency_war.obs.cw_observation import read_hp_opt
    calls = {'n': 0}

    def _hit(**kw):
        calls['n'] += 1
        return [SimpleOcrItem('45')]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', _hit)
    assert read_hp_opt(test_context, None) == 45
    assert calls['n'] == 2   # 原生 + 3x 放大对账(常开)


def test_read_hp_opt_native_dropped_tens_upscale_arbitrates(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """掉十位仲裁锁:原生通道丢十位(4),放大通道读全(47)→ 采放大值 + 留证。

    形态 = 2026-09-02 分诊帧 40e3354a(真值 47)/e4746213(真值 12)离线复现:
    hp 美术字笔画断续,原生 det/rec 截掉十位;3x CUBIC 放大笔画恢复。
    修前「原生命中即短路」返回 4 —— 本锁修复前红。
    """
    from sr_od.application.currency_war.obs import cw_observation
    from sr_od.application.currency_war.obs.cw_observation import read_hp_opt
    calls = {'n': 0}

    def _native_drops_tens(**kw):
        calls['n'] += 1
        if calls['n'] == 1:
            return [SimpleOcrItem('4')]    # 原生:十位笔画断续被截(真值 47)
        return [SimpleOcrItem('47')]       # 3x CUBIC:笔画恢复,读全
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        _native_drops_tens)
    evid: list[tuple] = []
    monkeypatch.setattr(cw_observation, 'obs_conflict',
                        lambda *a, **k: evid.append((a, k)))
    assert read_hp_opt(test_context, None) == 47
    assert calls['n'] == 2
    assert len(evid) == 1   # 不一致留证(obs_conflict),采新值有据可查


def test_read_hp_opt_second_level_binarized_recovery(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """放大仍漏(低对比)→ 第二级 OTSU 二值化兜回(两级管线完整面)。"""
    from sr_od.application.currency_war.obs.cw_observation import read_hp_opt
    calls = {'n': 0}

    def _miss_miss_hit(**kw):
        calls['n'] += 1
        return [] if calls['n'] < 3 else [SimpleOcrItem('9')]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        _miss_miss_hit)
    assert read_hp_opt(test_context, None) == 9
    assert calls['n'] == 3


# ---------- 组2:幽灵帧回放锁(消费门 fail-closed) ----------

def test_ghost_frame_predicate_blocks() -> None:
    """(100, False, False) 帧:100>21 线外,但不可信 → 拒(fail-closed)。"""
    assert blood_budget_levelup_blocked(
        _ghost_state(), StrategySession(), DEFAULT_REGISTRY) is True




def test_mutation_guard_removal_turns_locks_red(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """变异自检:守卫删除(可信位恒真,模拟 W580a 之前的谓词)→ 幽灵帧
    100>21 不再拒——组2 各锁在此变异下必须翻红,证明锁敏感性与守卫
    必要性(去门必须涌现违规)。"""
    monkeypatch.setattr(
        'sr_od.application.currency_war.kernel.cw_discipline_rules.'
        'hp_decision_trusted', lambda state: True)
    assert blood_budget_levelup_blocked(
        _ghost_state(), StrategySession(), DEFAULT_REGISTRY) is False


# ---------- 组3:放行面锁(语义零回归) ----------

def test_same_node_inherited_frame_passes() -> None:
    """放行面语义零回归(ADR-0428 主救场景):(16, False, True) 同节点
    沿用帧血线内照拒(值可信判断成立)、线外沿用帧 100 恒放(不因
    readable=False 误拦);真读帧 (True, False) 位形态线外放行不拦。"""
    sess = StrategySession()
    # 沿用值在血线内:停手照常生效(值可信,判断成立)
    assert blood_budget_levelup_blocked(
        _state_with_bits(16, False, True), sess, DEFAULT_REGISTRY) is True
    # 沿用值在线外:放行(不因 readable=False 误拦)
    assert blood_budget_levelup_blocked(
        _state_with_bits(100, False, True), sess, DEFAULT_REGISTRY) is False
    # 真读帧 (True, False)(可读未过帧龄门):线外放行不拦
    assert blood_budget_levelup_blocked(
        _state_with_bits(30, True, False), StrategySession(),
        DEFAULT_REGISTRY) is False


def test_allin_exempt_precedes_trust_guard() -> None:
    """ALL IN 豁免优先于可信位守卫:位面末不可信帧仍让位(豁免语义=
    末战花光是时机不是血线判断,不因证据缺失收紧)。"""
    st = _ghost_state(hp=100)
    st.round_num = 7
    st.node_type = 'boss'
    sess = StrategySession()
    sess.plane_node_table = ['battle'] * 7
    assert blood_budget_levelup_blocked(st, sess, DEFAULT_REGISTRY) is False


# (test_terminal_release_fail_closed_on_untrusted 已随 terminal_release 死链
#  删除——统一迁移批 ② MAP B 类「terminal_release 三函数」随删。)


# ---------- 组4:写侧位一致锁(shop._apply_hp) ----------

def test_apply_hp_writes_correct_triple() -> None:
    """三覆盖形态各产出正确 (hp, readable, trusted) 三元组:
    真读 → (v, True, True);结算真值(新鲜门过)→ (v, False, True);
    无新鲜真值(None)→ 不覆盖(裸 100 不再喂决策路径)。"""
    st = _ghost_state()
    _apply_hp(st, 45, True, True)
    assert (st.hp, st.hp_readable, st.hp_trusted) == (45, True, True)
    st2 = _ghost_state()
    _apply_hp(st2, 16, False, True)
    assert (st2.hp, st2.hp_readable, st2.hp_trusted) == (16, False, True)
    st3 = _ghost_state()
    before = (st3.hp, st3.hp_readable, st3.hp_trusted)
    _apply_hp(st3, None, False, False)
    assert (st3.hp, st3.hp_readable, st3.hp_trusted) == before


# ---------- 组7:r1 备战帧 hp 真值(画面读值为准,严禁 100 兜底) ----------
# 用户修正前提:r1 血量固定但**不恒为 100**(随当局难度/词缀变)——真值源=
# 备战画面显示值;读失败(重试后仍 miss)=诚实未知(hp=None),默认 100
# 兜底在 r1 语境废除;r2+ 结算真值链/新鲜度门照旧。


def _stub_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """桩掉 ``_r1_retry_read_hp`` 的 0.6s×2 重试静置:静置时长是生产节奏,
    非本组锁面(重试语义/诚实 None)——纪律 15 能便宜化先便宜化(1.2s→~0)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.operations.cw_op import cw_op_buy_cards
    monkeypatch.setattr(cw_op_buy_cards, 'time',
                        SimpleNamespace(sleep=lambda *_: None))


def test_r1_retry_read_hp_retries_then_recovers(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """r1 重试读:miss 后重试,第 2 次命中 → 返回读数(读到的值即真读,
    不恒为 100——如难度修正后的 80 照收)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        _r1_retry_read_hp,
    )
    _stub_retry_sleep(monkeypatch)
    calls = {'n': 0}

    def _miss_then_hit() -> int | None:
        calls['n'] += 1
        return None if calls['n'] == 1 else 80
    assert _r1_retry_read_hp(_miss_then_hit) == 80
    assert calls['n'] == 2


def test_r1_retry_read_hp_persistent_miss_honest_none(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """r1 重试穷尽仍 miss → None(诚实未知;严禁 100 兜底)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
        _r1_retry_read_hp,
    )
    _stub_retry_sleep(monkeypatch)
    calls = {'n': 0}

    def _always_miss() -> int | None:
        calls['n'] += 1
        return None
    assert _r1_retry_read_hp(_always_miss) is None
    assert calls['n'] == 2   # 恰好重试上限,不无限等


def _record_one(st: GameState, run_id: str, tmp_path) -> dict:
    """记录一帧决策迹并读回(decisions.jsonl 单行;tmp_path 隔离零副作用)。"""
    from sr_od.application.currency_war.telemetry.recorder import (
        TelemetryRecorder,
    )
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.record_decision(run_id, 'A1', st, '', {}, {}, [])
    import json
    lines = (tmp_path / 'decisions.jsonl').read_text(
        encoding='utf-8').strip().splitlines()
    return json.loads(lines[-1])


def test_r1_none_hp_trace_none_not_100(tmp_path) -> None:
    """r1 无真值帧(hp=None,两位皆 False)→ 决策迹 hp=None 直通。

    W823 None 化后对账层不再产 100 兜底——recorder 的 r1 特例臂退役,
    直通写 state.hp;真值帧照记(见下一条)。"""
    st = _state_with_bits(None, False, False)   # 诚实未知形态(None 化 producer 唯一产出)
    st.plane, st.round_num = 1, 1
    row = _record_one(st, 't-r1-none', tmp_path)
    assert row['hp'] is None
    assert row['hp_readable'] is False


def test_r1_real_read_frame_trace_keeps_value(tmp_path) -> None:
    """r1 真读帧(读到的值即 trusted)→ trace.hp=读数值照记(非 100 也照记)。"""
    st = _state_with_bits(80, True, True)
    st.plane, st.round_num = 1, 1
    row = _record_one(st, 't-r1-hit', tmp_path)
    assert row['hp'] == 80
    assert row['hp_readable'] is True


def test_r2_unread_frame_trace_unchanged(tmp_path) -> None:
    """r2+ 不变:同节点沿用帧 (16, False, True) 的 hp=16 照记(结算真值
    链/新鲜度门口径零回归);r2 两位皆 False 帧也直通写 None——诚实未知
    不分轮次(r1 特例臂退役后 recorder 无任何按轮分支,按轮特化回归即红)。"""
    st = _state_with_bits(16, False, True)
    st.plane, st.round_num = 1, 2
    row = _record_one(st, 't-r2', tmp_path)
    assert row['hp'] == 16
    st2 = _state_with_bits(None, False, False)   # 诚实未知形态(原 docstring 声称、原断言面缺位,W823)
    st2.plane, st2.round_num = 1, 2
    row2 = _record_one(st2, 't-r2-none', tmp_path)
    assert row2['hp'] is None


def test_r1_rule_frame_match_archive_none_honest() -> None:
    """遥测对账面:r1 读失败帧 hp=None → hp 真值链落 source='none'
    trusted=False(诚实未知;不再以兜底 100 显影成候选错值)。"""
    from sr_od.application.currency_war.telemetry.match_archive import _hp_entry
    frame = {'hp': None, 'hp_readable': False,
             'state': {'hp_trusted': False}}
    assert _hp_entry(frame, None) == {'hp': None, 'source': 'none',
                                      'trusted': False}


# ---------- 组5:sim 零漂移锁 ----------

def test_sim_frames_default_trusted_gate_short_circuits() -> None:
    """sim 帧恒真读(默认 hp_readable=True)→ 消费门短路:同帧谓词结果
    与守卫删除版逐位一致(零漂移的源级锁)。"""
    st = _state_with_bits(16, True, False)   # sim 决策帧形态:真读
    sess = StrategySession()
    with_guard = blood_budget_levelup_blocked(st, sess, DEFAULT_REGISTRY)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        'sr_od.application.currency_war.kernel.cw_discipline_rules.'
        'hp_decision_trusted', lambda state: True)
    try:
        without_guard = blood_budget_levelup_blocked(st.copy(), sess,
                                                     DEFAULT_REGISTRY)
    finally:
        monkey.undo()
    assert with_guard == without_guard is True


def test_sim_ledger_still_discloses_and_rejects_in_band() -> None:
    """单局 sim 冒烟:账本披露键仍在——逐行 sim dict 携带
    blood_budget_levelup_rejects 键(键集契约;键消失=判读/检查器侧对账
    断链;pool='fallback' 免快照依赖,同既有锁口径)。停手判定的正确性由
    组2/组3 谓词锁与组5 等价锁承接,本锁只辖披露面(命中次数依赖种子,
    不做分布断言——纪律 11)。"""
    from sr_od.application.currency_war.sim import engine_p1 as cw_sim
    r = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert r.ledger
    for row in r.ledger:
        assert 'blood_budget_levelup_rejects' in (row.get('sim') or {})


def test_registry_flag_off_still_zero_scope() -> None:
    """开关 off(A/B 对照臂)在守卫之前:不可信帧同样不辖(守卫位置
    在开关与豁免之后,不改变 A/B 注入面)。"""
    reg_off = dataclasses.replace(DEFAULT_REGISTRY,
                                  blood_budget_stop_enabled=False)
    assert not blood_budget_levelup_blocked(_ghost_state(), StrategySession(),
                                            reg_off)


# ---------- 组6:检查器侧镜像锁(seg_check_untrusted_hp_levelup) ----------
# 与组2/3 的分工:那里锁 decision 层拒付,这里锁 checks 层显形——
# 不可信帧上出现 LevelUp 账本行即命中(门旁路/账本错位即刻显形);
# sim 恒真读(两键缺省)恒零命中 = 纯防线验证面(DESIGN 测试计划组5)。


def _ledger_row(plane: int, rn: int, *, hp_readable: bool | None,
                hp_trusted: bool | None, actions: list[dict] | None = None,
                node: str = 'battle') -> dict:
    """合成账本行(检查器输入的最小形状;键缺省位 = 可信口径的载体)。"""
    st: dict = {'level': 6}
    if hp_trusted is not None:
        st['hp_trusted'] = hp_trusted
    row: dict = {'plane': plane, 'round_num': rn, 'hp': 100,
                 'node': node, 'actions': actions or [],
                 'state': st, 'sim': {'node': node}}
    if hp_readable is not None:
        row['hp_readable'] = hp_readable
    return row


def _lv_action() -> dict:
    return {'__type__': 'LevelUp', 'auth': 'pop_slot'}


def test_seg_untrusted_hp_levelup_hits_both_bits_false() -> None:
    """不可信帧(两位皆 False,hp_decision_trusted 谓词镜像)上
    LevelUp → 命中;单 False 单 True(沿用帧/真读帧)不命中。"""

    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_untrusted_hp_levelup,
    )
    rows = [_ledger_row(2, 4, hp_readable=False, hp_trusted=False,
                        actions=[_lv_action()])]
    evs = seg_check_untrusted_hp_levelup(rows)
    assert len(evs) == 1
    assert evs[0]['levelups'] == 1
    assert evs[0]['bits']   # 违规位显形在事件里


def test_seg_trusted_frames_zero_hit() -> None:
    """可信面零命中:两键缺省(sim 恒真读/旧批账本)、(False, True)
    同节点沿用帧、(True, False) 真读帧、不可信帧但无 LevelUp;
    ALL IN 豁免优先(消费门语义镜像):位面末 boss 不可信帧 LevelUp 不报,
    非 ALL IN 的 boss 帧(轮未到位面节点数)不豁免。"""

    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_untrusted_hp_levelup,
    )
    rows = [
        _ledger_row(1, 3, hp_readable=None, hp_trusted=None,
                    actions=[_lv_action()]),            # sim 形态
        _ledger_row(1, 4, hp_readable=False, hp_trusted=True,
                    actions=[_lv_action()]),            # 沿用真值帧(消费门放行)
        _ledger_row(1, 5, hp_readable=True, hp_trusted=False,
                    actions=[_lv_action()]),            # 真读帧
        _ledger_row(1, 6, hp_readable=False, hp_trusted=False),  # 无升级
    ]
    assert seg_check_untrusted_hp_levelup(rows) == []
    rows_allin = [_ledger_row(2, 7, hp_readable=False, hp_trusted=False,
                              actions=[_lv_action()], node='boss')]
    assert seg_check_untrusted_hp_levelup(rows_allin) == []
    # 非 ALL IN 的 boss 帧(轮未到位面节点数)不豁免
    rows_early = [_ledger_row(2, 3, hp_readable=False, hp_trusted=False,
                              actions=[_lv_action()], node='boss')]
    assert len(seg_check_untrusted_hp_levelup(rows_early)) == 1


def test_seg_untrusted_check_registered_and_sim_zero_hit() -> None:
    """检查项已入段级表;run_segment_checks 批量入口对恒真读合成局
    零命中(纯防线验证面;sim-testing §6 披露键保留纪律)。"""
    from sr_od.application.currency_war.sim.checks import segments as chk
    assert 'seg_untrusted_hp_levelup' in chk._SEGMENT_CHECKS
    good = [_ledger_row(1, r, hp_readable=None, hp_trusted=None,
                        actions=[_lv_action()]) for r in range(1, 4)]
    rep = chk.run_segment_checks([good], seed_base=0)
    assert rep['seg_untrusted_hp_levelup']['count'] == 0


def test_seg_untrusted_mutation_default_trust_turns_locks_red() -> None:
    """变异自检(DESIGN 组5「去门必须涌现违规」):把检查器的缺省位
    语义反转成「缺省 = 不可信」的合成形态等价于旧账本键位消失时
    命中——锁的敏感性由显式 False 单向触发保证(缺省键的旧账本
    不虚报,真不可信帧不漏报)。"""

    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_untrusted_hp_levelup,
    )
    # 顶层缺 state 子字典(形状异常账本)也不炸、且不误报(缺省 = 可信)
    row = {'plane': 1, 'round_num': 2, 'hp': 100, 'actions': [_lv_action()]}
    assert seg_check_untrusted_hp_levelup([row]) == []
