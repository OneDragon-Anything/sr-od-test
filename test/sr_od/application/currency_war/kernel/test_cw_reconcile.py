"""星级抖动门辖区锁面(kernel/cw_reconcile.py ``_gate_star_jitter``):门只对
logic_rand 以外的基线保旧,随机态基线星差直采。

锁的设计约定(cw_reconcile.py 门注释块第 3 层;病灶 = run_20261124_030405
位面 1 第 3 轮停机,死因链 = 随机态基线幻影 ★2 被门保旧 → observe 整表写回
洗成 observation → 确定写落观察态基座不再升格 → 第二次实读真失配 andon):
1. 随机态基线星差:门后副本 = 实读星、候选表空、observe 落 logic_rand_outcome
   (零真失配、零 andon),披露行 verdict 前缀 = STAR_ADOPT_RAND_BASELINE_PREFIX
   且 char / slot / domain / source 透传;两域(bench / deployed)同构;
2. 观察态基线同名多星抖动:保旧 + 连续两帧采新不变(披露行前缀 =
   STAR_HOLD_JITTER_PREFIX;采新不产行);
3. 逻辑态基线星差:仍保旧一帧;保旧窗内落确定写者第二帧真失配照报
   (检出网原样);
4. 合成特效窗优先于来源判定:窗内随机态基线仍保旧(前缀 =
   STAR_HOLD_WINDOW_PREFIX,零采新行),撤窗后直采。

披露行契约锁:test 1 / 2 / 4 以 monkeypatch 捕手 ``_conflict``(门内以 4 位置
参数 + kwargs 调用,捕手须收 ``*a, **k``);测试环境 obs_event_board 为 None
本就不落 journal 行,监控脚本筛选键在此处锁。搭建口径:session = 可弱引用的
普通类实例(候选旁表 WeakKeyDictionary 随对象回收);局状态容器建立即带
开局种子(logic_rand 空视图),断言前先 ``consume_defect_sink()`` 清场。
"""

from __future__ import annotations

import numpy
import pytest

from sr_od.application.currency_war.kernel import cw_observe, cw_reconcile
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    Unit,
    consume_defect_sink,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    set_reconcile_andon_hook,
)


class _Sess:
    """局身份(普通类实例,可弱引用 → 候选旁表走 WeakKeyDictionary 主路)。"""


_SIG_LOGIC = ChannelSig(family='logic_action', actor='test')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep',
                      screen='货币战争-备战', mode='read')


def _u(char_id: str, star: int = 1) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star))


_E = BenchSlot(kind='empty')


def _slot(view: BenchView, slot: int) -> str:
    """bench 视图某物理槽(1 基)的 ``角色★星`` 文案(断言用)。"""
    u = view.slots[slot - 1].unit
    return f'{u.char_id}★{u.star}'


# journal run_20261124_030405 v301:采样落位后模型账面(槽 5 幻影 ★2、槽 6 长夜月)。
_V301 = BenchView(slots=[_u('波提欧'), _u('灵砂'), _u('火花'), _u('景元'),
                         _u('黑天鹅', 2), _u('长夜月'), _E,
                         _u('真珠'), _u('瓦尔特')], capacity=9)
# v333 heavy 实读:槽 5 黑天鹅 ★1(星差)、槽 6 黑天鹅 ★1(身份差)。
_TRUTH1 = BenchView(slots=[_u('波提欧'), _u('灵砂'), _u('火花'), _u('景元'),
                           _u('黑天鹅'), _u('黑天鹅'), _E,
                           _u('真珠'), _u('瓦尔特')], capacity=9)


@pytest.fixture(autouse=True)
def _clean_defect_board() -> None:
    """缺陷行缓冲进程级共享:用前取走残留、用后清空,防跨测试串染。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


@pytest.fixture
def conflict_log(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple, dict]]:
    """``_conflict`` 捕手:每项 = (位置参数元组 ``(field, old, new, screen)``,
    kwargs 字典)。门内无 try 包裹、按模块全局名查得,改模块属性即截获。"""
    rec: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(cw_reconcile, '_conflict',
                        lambda *a, **k: rec.append((a, k)))
    return rec


def _star_calls(rec: list[tuple[tuple, dict]]) -> list[tuple[tuple, dict]]:
    """只取星级门披露行(``field == 'star'``;tracking 纠漂行另算)。"""
    return [r for r in rec if r[0][0] == 'star']


def test_rand_baseline_star_diff_adopts_read_and_closes_as_rand_outcome(
        conflict_log: list[tuple[tuple, dict]]) -> None:
    """随机态基线链剧本复放(v301 → v333/v337 → v407-v421 → v440/v442):
    首帧门后槽 5 = 实读 ★1、候选表空;observe 落 logic_rand_outcome、来源翻
    observation 且槽 5 = ★1;确定写链来源 logic 且槽 5 仍 ★1;第二次实读与
    逻辑态同值 → 零失配行、零 andon。deployed 域一段同构。披露行契约:首帧
    恰一条 star 行,verdict 前缀 = 采新-随机态基线 且含「字段来源 logic_rand」,
    source / char / slot / domain 透传;全程零条「保旧-星级抖动门」。"""
    session = _Sess()
    gs = game_state_of(session)
    andon: list[dict] = []
    set_reconcile_andon_hook(andon.append)
    try:
        gs.write_logic_rand(gs.bench, _V301, produced_by='CwActionCollectOreParam',
                            evidence='proj_ore_reward_char#ore3', sig=_SIG_LOGIC)
        assert gs.bench.source == 'logic_rand'
        # 第一次 heavy 读
        _, b1, _ = cw_reconcile.reconcile_tracking(
            session, _TRUTH1, DeployedView(), screen=None, source='director')
        assert _slot(b1, 5) == '黑天鹅★1', '随机态基线星差须直采实读星'
        assert _slot(b1, 6) == '黑天鹅★1'
        assert cw_reconcile._star_gate_pending(session) == {}
        gs.observe(gs.bench, b1, sig=_SIG_OBS)
        rows = consume_defect_sink()
        assert [r['kind'] for r in rows] == ['logic_rand_outcome'], rows
        assert rows[0]['field'] == 'bench'
        assert gs.bench.source == 'observation'
        assert _slot(gs.bench.value, 5) == '黑天鹅★1', \
            '观察写回值须为实读真值,不得含保旧猜测星(洗白)'
        # 确定写链(v407-v421 形态:卖槽 6 买景元、卖槽 8 买灵砂,槽 5 原样沿用)
        slots = list(gs.bench.value.slots)
        slots[5] = _u('景元')
        slots[7] = _u('灵砂')
        gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                       produced_by='test', evidence='proj_buy_place', sig=_SIG_LOGIC)
        assert gs.bench.source == 'logic'
        assert _slot(gs.bench.value, 5) == '黑天鹅★1'
        # 第二次 heavy 读 = 逻辑态(v440 / v442 帧)
        truth2 = BenchView(slots=list(gs.bench.value.slots), capacity=9)
        _, b2, _ = cw_reconcile.reconcile_tracking(
            session, truth2, DeployedView(), screen=None, source='director')
        gs.observe(gs.bench, b2, sig=_SIG_OBS)
        assert consume_defect_sink() == [], '第二次实读与逻辑态同值须零行'
        assert andon == [], '随机态基线链全程不得触发停机钩子'
        star_calls = _star_calls(conflict_log)
        assert len(star_calls) == 1, star_calls
        (field, old, new, _screen), kw = star_calls[0]
        assert (field, old, new) == ('star', 2, 1)
        assert kw['verdict'].startswith(cw_reconcile.STAR_ADOPT_RAND_BASELINE_PREFIX)
        assert '字段来源 logic_rand' in kw['verdict']
        assert kw['source'] == 'director'
        assert kw['char'] == '黑天鹅'
        assert kw['slot'] == 5
        assert kw['domain'] == 'bench'
        # deployed 域:采晶矿未变标记翻来的随机态基线,同星差同链
        gs.write_logic_rand(
            gs.deployed,
            DeployedView(front_slots=[None, Unit(char_id='忘归人', star=2), None, None],
                         back_slots=[None] * 6),
            produced_by='CwActionCollectOreParam',
            evidence='proj_ore_mark_deployed#ore1', sig=_SIG_LOGIC)
        _, _, d1 = cw_reconcile.reconcile_tracking(
            session, BenchView(),
            DeployedView(front_slots=[None, Unit(char_id='忘归人', star=1), None, None],
                         back_slots=[None] * 6),
            screen=None, source='director')
        assert d1.front_slots[1] == Unit(char_id='忘归人', star=1)
        assert cw_reconcile._star_gate_pending(session) == {}
        star_calls = _star_calls(conflict_log)
        assert len(star_calls) == 2, star_calls
        _, kw = star_calls[1]
        assert kw['verdict'].startswith(cw_reconcile.STAR_ADOPT_RAND_BASELINE_PREFIX)
        assert kw['char'] == '忘归人'
        assert kw['domain'] in ('front', 'back')
        assert kw['slot'] == 2, 'slot = 子表下标 + 1(前排第 2 槽)'
        assert not any(kw['verdict'].startswith(cw_reconcile.STAR_HOLD_JITTER_PREFIX)
                       for _, kw in _star_calls(conflict_log)), \
            '随机态基线上门不得保旧'
    finally:
        set_reconcile_andon_hook(None)


def test_observation_baseline_jitter_still_holds_two_frames(
        conflict_log: list[tuple[tuple, dict]]) -> None:
    """观察态基线同名多星抖动(门的原病灶形态)行为不变:首帧星差保旧 + 登记
    候选 + 披露行(前缀 = 保旧-星级抖动门);次帧同读采新、候选表空、不产行。"""
    session = _Sess()
    gs = game_state_of(session)
    base = BenchView(slots=[_E, _E, _E, _E, _u('黑天鹅', 2), _u('黑天鹅')]
                     + [_E] * 3, capacity=9)
    jit = BenchView(slots=[_E, _E, _E, _E, _u('黑天鹅'), _u('黑天鹅')]
                    + [_E] * 3, capacity=9)
    gs.observe(gs.bench, base, sig=_SIG_OBS)
    consume_defect_sink()   # 开局种子 → 真值的首个 observe 落 logic_rand_outcome
    assert gs.bench.source == 'observation'

    _, b1, _ = cw_reconcile.reconcile_tracking(
        session, jit, DeployedView(), screen=None, source='director')
    assert _slot(b1, 5) == '黑天鹅★2', '观察态基线单帧星差须保旧'
    assert cw_reconcile._star_gate_pending(session) == {('bench', 5, '黑天鹅'): 1}, \
        '候选键 = (域, 物理槽号, 规范名)'
    star_calls = _star_calls(conflict_log)
    assert len(star_calls) == 1, star_calls
    (field, old, new, _screen), kw = star_calls[0]
    assert (field, old, new) == ('star', 2, 1)
    assert kw['verdict'].startswith(cw_reconcile.STAR_HOLD_JITTER_PREFIX)
    assert kw['source'] == 'director'

    _, b2, _ = cw_reconcile.reconcile_tracking(
        session, jit, DeployedView(), screen=None, source='director')
    assert _slot(b2, 5) == '黑天鹅★1', '连续两帧同值须采新'
    assert cw_reconcile._star_gate_pending(session) == {}
    assert len(_star_calls(conflict_log)) == 1, '采新不产披露行'


def test_logic_baseline_star_diff_still_holds_one_frame_then_reports() -> None:
    """逻辑态基线星差行为不变:首帧保旧 + observe 零失配行;保旧窗内再落
    确定写(同值)后次帧采新 → observe 落 observe_vs_logic_mismatch 且 andon
    一次(真失配迟两帧报出,检出网原样)。"""
    session = _Sess()
    gs = game_state_of(session)
    truth = BenchView(slots=[_E] * 4 + [_u('黑天鹅')] + [_E] * 4, capacity=9)
    claim = BenchView(slots=[_E] * 4 + [_u('黑天鹅', 2)] + [_E] * 4, capacity=9)
    gs.observe(gs.bench, truth, sig=_SIG_OBS)
    consume_defect_sink()
    gs.write_logic(gs.bench, claim, produced_by='test', evidence='proj_test',
                   sig=_SIG_LOGIC)
    assert gs.bench.source == 'logic'

    andon: list[dict] = []
    set_reconcile_andon_hook(andon.append)
    try:
        _, b1, _ = cw_reconcile.reconcile_tracking(
            session, truth, DeployedView(), screen=None, source='director')
        assert _slot(b1, 5) == '黑天鹅★2', '逻辑态基线单帧星差须保旧一帧'
        gs.observe(gs.bench, b1, sig=_SIG_OBS)
        assert consume_defect_sink() == [], '保旧副本等值写回须零失配行'
        gs.write_logic(gs.bench, gs.bench.value, produced_by='test',
                       evidence='proj_test2', sig=_SIG_LOGIC)
        assert gs.bench.source == 'logic'
        _, b2, _ = cw_reconcile.reconcile_tracking(
            session, truth, DeployedView(), screen=None, source='director')
        assert _slot(b2, 5) == '黑天鹅★1'
        gs.observe(gs.bench, b2, sig=_SIG_OBS)
        kinds = [r['kind'] for r in consume_defect_sink()]
        assert kinds == ['observe_vs_logic_mismatch'], kinds
        assert len(andon) == 1, '逻辑态基线上的真失配须照报停机'
    finally:
        set_reconcile_andon_hook(None)


def test_merge_effect_window_outranks_rand_baseline_adoption(
        conflict_log: list[tuple[tuple, dict]],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """特效窗优先于来源判定:窗内随机态基线仍保旧(副本槽 5 = ★2、候选表空、
    披露行前缀 = 保旧-合成特效窗,零采新行);撤窗后再读直采(副本槽 5 = ★1,
    采新行此刻才出现)。次序一错(来源判定排到 frozen 之前)窗内不可信读数
    就会直采入账。screen 须传非 None 哑帧(None 直接放行,窗分支不可达);
    cw_shot_unique 打桩 no-op(测试零真实副作用)。"""
    monkeypatch.setattr(cw_observe, 'cw_shot_unique', lambda image, label: None)
    session = _Sess()
    gs = game_state_of(session)
    gs.write_logic_rand(gs.bench, _V301, produced_by='CwActionCollectOreParam',
                        evidence='proj_ore_reward_char#ore3', sig=_SIG_LOGIC)
    dummy = numpy.zeros((2, 2, 3), dtype=numpy.uint8)
    cw_reconcile.set_merge_effect_gate(lambda _screen: True)
    try:
        _, b_in, _ = cw_reconcile.reconcile_tracking(
            session, _TRUTH1, DeployedView(), screen=dummy, source='director')
    finally:
        cw_reconcile.set_merge_effect_gate(None)
    assert _slot(b_in, 5) == '黑天鹅★2', '窗内读数不可信,随机态基线亦须保旧'
    assert cw_reconcile._star_gate_pending(session) == {}
    assert gs.bench.source == 'logic_rand'
    in_window = _star_calls(conflict_log)
    assert len(in_window) == 1, in_window
    _, kw = in_window[0]
    assert kw['verdict'].startswith(cw_reconcile.STAR_HOLD_WINDOW_PREFIX)

    _, b_out, _ = cw_reconcile.reconcile_tracking(
        session, _TRUTH1, DeployedView(), screen=dummy, source='director')
    assert _slot(b_out, 5) == '黑天鹅★1', '撤窗后随机态基线星差须直采'
    assert cw_reconcile._star_gate_pending(session) == {}
    after = _star_calls(conflict_log)
    assert len(after) == 2, after
    _, kw = after[1]
    assert kw['verdict'].startswith(cw_reconcile.STAR_ADOPT_RAND_BASELINE_PREFIX)
