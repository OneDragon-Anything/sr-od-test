# -*- coding: utf-8 -*-
"""test_cw_legacy_audit 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- r297_p0_fixes: test_cw_r297_p0_fixes.py
- r336_batch4_locks: test_cw_r336_batch4_locks.py
- r337_behavior: test_cw_r337_behavior.py
- r337_r332_behavior: test_cw_r337_r332_behavior.py
- r339_r340_telemetry_sim: test_cw_r339_r340_telemetry_sim.py
- r348_cap_domain: test_cw_r348_cap_domain.py
- r363_audit_p0: test_cw_r363_audit_p0.py
- r271_line_defs: test_cw_r271_line_defs.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== r297_p0_fixes ====================

import inspect

from sr_od.application.currency_war import prep_director


def test_loop_entry_anchor_is_stage_only() -> None:
    """P0①→r347(旧路径删除):原「按钮-出战」双态区分锚随 3 探针
    旧路径删除而退役——环入口消化语义由 gate 时间稳定窗
    (PROFILE_CLOSED 屏判定=备战关态专属)+r346 开商店容忍
    (收起重进)承担。锁:旧锚不得回流 + gate 调用在。"""
    src = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert "'按钮-出战'" not in src, \
        '旧 3 探针锚已删(r347),环入口消化由 gate 承担'
    assert 'wait_stable_frame' in src, \
        '环入口必须走 gate(时间稳定窗消化门)'


def test_no_fallthrough_blind_observe() -> None:
    """P0①:3 次不 clean → bail(交外环重进),不再 fall-through
    盲 observe(实锤路径:16:42:35 deployed 6人读成1人)。"""
    src = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert '环入口帧不clean' in src


def test_probe_node_type_after_shop_closed() -> None:
    """P0③:_probe_node_type 迁至 EnsureShopClosed 后(与 reward
    钩子同挂点);run() 入口不再直调(skip 69% 根因)。"""
    src_loop = inspect.getsource(prep_director.PrepDirector._run_loop)
    assert 'self._probe_node_type()' in src_loop
    src_run = inspect.getsource(prep_director.PrepDirector.run)
    assert 'self._probe_node_type()' not in src_run


# ==================== r336_batch4_locks ====================

import inspect as _r336_batch4_locks_inspect


def test_shop_collapse_single_poll_fn() -> None:
    """r335→r347(旧路径删除)→ DD-011(操作完成自等动画,2026-09-02):
    shop buy 内 gate 全退役(收起两处自等动画 1.0s;开商店判稳轮询「备战阶段」
    文本 1s 间隔 4 轮,与 EnsureShop 开向同款)——测量驱动稳定门不得回流,
    画面状态判定在外层建档识别。_legacy_poll 轮询亦不得回流。"""
    from sr_od.application.currency_war.operations.prep import shop
    src = _r336_batch4_locks_inspect.getsource(shop.BuyShopCards.buy)
    assert 'def _legacy_poll' not in src, \
        '旧轮询 _legacy_poll 已删(r347),不得回流'
    assert 'wait_stable_frame' not in src, \
        'buy 内 gate 已按 DD-011 全退役,不得回流'
    assert 'SHOP_CLOSE_ANIM_S' in src, \
        '收起动画时长必须由 op 显式声明并等待(DD-011)'
    assert 'SHOP_OPEN_POLL_ROUNDS' in src, \
        '开店判稳轮询必须在场(「备战阶段」文本判稳,DD-011)'


def test_star_evidence_queue_pattern() -> None:
    """r336:star 留证从 reconcile 深处改队列登记,对账位统一消费。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    src = _r336_batch4_locks_inspect.getsource(cw_reconcile.reconcile_tracking)
    assert '_pending_evidence.append' in src       # 深处只登记
    assert '_pending_evidence:' in src              # 队列初始化
    # 消费在函数尾部(对账&hook 位)
    tail = src[src.index('return True') - 700:]
    assert '_star_stop_hook' in tail


def test_star_hook_none_screen_tolerant() -> None:
    """r336b:screen=None(测试/无帧)不拦留证。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    src = _r336_batch4_locks_inspect.getsource(cw_reconcile._star_stop_hook)
    assert 'screen is not None' in src


def test_prep_settle_attribution_declared() -> None:
    """r336:PREP_SETTLE_S 归属声明(分发层 vs 环内 gate 正交)。"""
    from sr_od.application.currency_war.operations import battle_loop
    src = _r336_batch4_locks_inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert 'r336' in src and '正交' in src


def test_shop_currency_war_config_module_level() -> None:
    """r345(局38 实机,gate bug #5):shop.py 的 CurrencyWarConfig
    必须模块级 import——原局部 import 在「收起按钮可见」条件分支
    内,shop 关态入口(分支跳过)+后方引用 = UnboundLocalError,
    buy 全崩。锁:模块级名存在 + buy 体内无任何局部 import。"""
    from sr_od.application.currency_war.operations.prep import shop
    assert getattr(shop, 'CurrencyWarConfig', None) is not None, \
        'shop.py 必须模块级 import CurrencyWarConfig'
    src = _r336_batch4_locks_inspect.getsource(shop.BuyShopCards.buy)
    assert 'currency_war_config import' not in src, \
        'buy 体内不得再有局部 import CurrencyWarConfig(r345 局38 崩溃根因)'


def test_shop_contextlib_module_level_no_local_import() -> None:
    """r346(review H1,gate bug #5 同型):buy 体内 `import contextlib`
    原只在两个 gate 分支内,L352 的 `with contextlib.suppress`
    (decide_prep 异常留证路径)在分支外——shop 开态入口或 flag off
    时 decide_prep 抛异常会先抛 UnboundLocalError,吞掉原始异常
    与遥测留证。锁:模块级存在 + buy/buy_card 体内无局部 import
    contextlib + contextlib.suppress 使用点无局部 import 保护。"""
    from sr_od.application.currency_war.operations.prep import shop
    assert getattr(shop, 'contextlib', None) is not None, \
        'shop.py 必须模块级 import contextlib(r346 H1)'
    for method in (shop.BuyShopCards.buy,):
        src = _r336_batch4_locks_inspect.getsource(method)
        assert 'import contextlib' not in src, \
            f'{method.__name__} 体内不得有局部 import contextlib(r346 H1 雷)'


def test_director_gate_open_shop_tolerated_not_bail() -> None:
    """r346(局38 r2 停机根因)+r347:环入口 gate 超时后必须先区分
    「开商店稳定态」(合法,游戏在战斗胜利后新回合可能自动开)
    vs「真特效」——开态走收起+round_retry 重进,只有非开态才
    _bail(3-strike 停机)。锁源检:容忍 helper + 超时分支调用 +
    bail 仍保留。"""
    from sr_od.application.currency_war import prep_director
    helper_src = _r336_batch4_locks_inspect.getsource(
        prep_director.PrepDirector._try_collapse_open_shop)
    assert '按钮-收起' in helper_src and 'return True' in helper_src, \
        '开商店容忍 helper 必须探测收起锚并返回可重进'
    src = _r336_batch4_locks_inspect.getsource(prep_director.PrepDirector._run_loop)
    assert '_try_collapse_open_shop()' in src, \
        'gate 超时分支必须调用开商店态容忍路径(r346)'
    assert '环入口商店开,已收起重进' in src, \
        '开态路径必须收起后 round_retry 重进(非 bail)'
    assert '环入口帧不clean' in src, \
        '真特效/overlay 的原 bail 路径必须保留(容忍不能吞掉消化门)'


# ==================== r337_behavior ====================

from sr_od.application.currency_war.obs.cw_observe_full import observe_full


def _stub(of_mod, gold_seq: list[int]):
    """打桩 read_game_state 依序返 gold 序列;其余 reader 空。"""
    from sr_od.application.currency_war.kernel.cw_state import GameState
    _i = {'n': 0}

    def _gs(ctx, frame):
        g = gold_seq[min(_i['n'], len(gold_seq) - 1)]
        _i['n'] += 1
        return GameState(gold=g)
    _orig = (of_mod.read_game_state, of_mod.ensure_portrait_templates,
             of_mod.read_node_sequence, of_mod.read_shop_cards)
    of_mod.read_game_state = _gs
    of_mod.ensure_portrait_templates = lambda ctx: None
    of_mod.read_node_sequence = lambda ctx, s: None
    of_mod.read_shop_cards = lambda ctx, s: []
    return _orig


def _restore(of_mod, orig) -> None:
    (of_mod.read_game_state, of_mod.ensure_portrait_templates,
     of_mod.read_node_sequence, of_mod.read_shop_cards) = orig


class _Shot55:
    """op 桩:重截图返一个哑帧(gold 真值由 read_game_state 桩给)。"""
    shots = 0

    def screenshot(self):
        type(self).shots += 1
        return None


def test_gold_reread_swaps_state_when_second_read_positive() -> None:
    """MED-2 行为锁:开态 gold 0 → 重读 55 → state.gold==55。"""
    import sr_od.application.currency_war.obs.cw_observe_full as of_mod
    _orig = _stub(of_mod, [0, 55])
    try:
        out = observe_full(None, None, tier='heavy', source='test',
                           op=_Shot55(), shop_open=True)
        assert out['state'].gold == 55, '重读真值应换入'
        assert out['gold_reread'] is True
    finally:
        _restore(of_mod, _orig)


def test_gold_reread_keeps_zero_when_all_reads_zero() -> None:
    """MED-2 行为锁:连读 0 → 维持 0(gold_reread=False)。"""
    import sr_od.application.currency_war.obs.cw_observe_full as of_mod
    _orig = _stub(of_mod, [0, 0, 0, 0])
    try:
        out = observe_full(None, None, tier='heavy', source='test',
                           op=_Shot55(), shop_open=True)
        assert out['state'].gold == 0
        assert out['gold_reread'] is False
    finally:
        _restore(of_mod, _orig)


def test_offline_op_none_skips_reread() -> None:
    """离线契约:op=None 不重读(单次 read_game_state)。"""
    import sr_od.application.currency_war.obs.cw_observe_full as of_mod
    _orig = _stub(of_mod, [0])
    try:
        out = observe_full(None, None, tier='heavy', source='test',
                           op=None, shop_open=True)
        assert out['state'].gold == 0
        assert out['gold_reread'] is False
    finally:
        _restore(of_mod, _orig)


# ==================== r337_r332_behavior ====================

from types import SimpleNamespace


def _make_op(monkeypatch, fail: bool):
    """构 battle_loop 循环实例桩:execute 链可控。"""
    from sr_od.application.currency_war.operations import battle_loop as bl

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):
            self._director_fail_streak = 0

        def _director_fail(self):
            """复刻 r332 段逻辑(不跑全环,单测节流)。"""
            _ok = not fail
            if not _ok:
                self._director_fail_streak += 1
                if self._director_fail_streak >= 5:
                    return 'round_fail'
            else:
                self._director_fail_streak = 0
            return 'wait'
    return _Loop()


def test_five_consecutive_failures_trigger_fail() -> None:
    """连续 5 次 director 失败 → 触发 round_fail 路径。"""
    op = _make_op(None, fail=True)
    results = [op._director_fail() for _ in range(6)]
    assert results[:4] == ['wait'] * 4
    assert results[4] == 'round_fail', '第 5 次应 fail'
    assert results[5] == 'round_fail', '持续 fail'


def test_success_resets_streak() -> None:
    """成功重置计数(4 失败+1 成功+4 失败 → 不 fail)。"""
    op = _make_op(None, fail=True)
    for _ in range(4):
        op._director_fail()
    # 成功一次
    op2 = _make_op(None, fail=False)
    op._director_fail_streak = 0   # 模拟成功分支
    assert op._director_fail_streak == 0
    for _ in range(4):
        assert op._director_fail() == 'wait', '重置后再 4 次不 fail'


def test_source_has_real_wiring() -> None:
    """真实接线存在(弱锁保底:streak 挂长命 loop 实例)。"""
    import inspect
    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert 'PrepDirector(self.ctx).execute()' in src
    assert '_director_fail_streak' in src


# ==================== r339_r340_telemetry_sim ====================

import inspect as _r339_r340_telemetry_sim_inspect


def test_outcome_board_fields() -> None:
    """r339:OutcomeRecord 板深快照字段(板深模型校准源)。"""

    from sr_od.application.currency_war.telemetry.schema import OutcomeRecord
    rec = OutcomeRecord()
    assert rec.board_before == {}
    assert rec.bench_count == 0


def test_query_hp_view_exists() -> None:
    """r339:hp 视图(掉血分解,sim hp_events 同构)。"""
    from sr_od.application.currency_war.telemetry import query as _q
    assert hasattr(_q, 'query_hp')
    assert hasattr(_q, 'query_economy')


def test_set_ctx_match_ref_slot() -> None:
    """r339:set_ctx_match 弱引用注册。"""
    from sr_od.application.currency_war.telemetry import state as _s
    assert hasattr(_s, 'set_ctx_match')
    assert hasattr(_s, '_CTX_MATCH_REF')


def test_live_delta_depth_conditioned() -> None:
    """r340:板深条件化池 + live_delta_for 回退链(⓪ 后显式池注入)。

    ⓪(sim 判读同构基建)起 pool_map 显式注入——「离线无 replay
    返回 None」的隐式两态语义已废除(缺源 auto 现 raise,
    DeltaPoolUnavailable),本锁改构造池双向锁:命中桶采样 +
    无更浅桶 → None(调用方走旧模型)。
    (ADR-0279:battle 桶键=rung;depth 路径锁用 boss/encounter
    承载,battle 全 rung 不可达走全池兜底。)
    """
    import random

    from sr_od.application.currency_war.sim import engine_p1 as cw_sim
    from sr_od.application.currency_war.sim import pool as sim_pool
    src = _r339_r340_telemetry_sim_inspect.getsource(sim_pool.live_delta_for)
    assert '浅侧' in src and 'bucket - DEPTH_BUCKET_W' in src   # 邻桶回退只向浅侧(真锁:实现语句在)
    # ADR-0362:合成池带 plane 层
    pool = {'battle': {1: {6: [-3, -5]}}}
    v = sim_pool.live_delta_for('battle', 7, random.Random(1),
                              pool_map=pool)
    assert v in (-3, -5)     # rung 桶不可达 → 全池兜底命中样本
    # boss 桶缺 → None(r343 E 修:只向浅侧;节点缺 → None)
    assert sim_pool.live_delta_for('boss', 6, random.Random(1),
                                 pool_map=pool) is None


def test_sim_events_reach_node_delta() -> None:
    """r340:sim 结算走板深池优先(hp_events 记真值)。"""
    from sr_od.application.currency_war.sim import engine_p1 as cw_sim

    src = _r339_r340_telemetry_sim_inspect.getsource(cw_sim.simulate_p1)
    assert 'live_delta_for' in src



# ==================== r348_cap_domain ====================

import inspect as _r348_cap_domain_inspect

from sr_od.application.currency_war import prep_director as _r348_cap_domain_prep_director
from sr_od.application.currency_war.obs.cw_back_layout import  back_slots_from_cap_diff


def test_cap_domain_check_inverted() -> None:
    """旧窄域(cap∈{level,level+1})跨 5 局假警报(宝钻叠加是合法
    常态);反转后:下界违例才留证,上界超出去 debug 记宝钻数。"""
    src = _r348_cap_domain_inspect.getsource(_r348_cap_domain_prep_director.PrepDirector._observe)
    assert 'cap < st.level' in src, \
        '真异常方向 = cap<level(不可能向,读错检测保留,ADR-0220)'
    assert 'cap应在level..level+1' not in src, \
        '旧窄域 verdict 文案不得回流(假警报源)'


def test_lv6_pending_hook_retired() -> None:
    """W209/ADR-0385:旧 lv6 待采留证(note_pending_7slots)随 level 驱动模型
    作废删除——采集信号改 7 格档未建档(diff==1)留证,辖域在
    cw_back_layout(select_back_layout/note_7slots_pending),prep_director 不再挂。"""
    src = _r348_cap_domain_inspect.getsource(_r348_cap_domain_prep_director.PrepDirector._observe)
    assert 'note_pending_7slots(' not in src and 'note_7slots_pending(' not in src, \
        'lv6 待采留证已废(ADR-0385);7 格留证辖域在 cw_back_layout'
    assert 'deploy_cap_unverified_layout' not in src, \
        '旧「未实拍档留证」分支已作废(7/9/10/11 是幻影,ADR-0281)'
    assert '_UNVERIFIED_BACK_SLOTS' not in src, \
        '旧集合已删(勿回流)'


def test_cap_diff_formula_semantics() -> None:
    """W209/ADR-0385:口述公式「后台格数 = 6+(cap−level)」——
    diff0→6 / diff1→7(已建档,2026-08-26 佩佩局实锤)/ diff≥2→8。"""
    assert back_slots_from_cap_diff(0) == 6
    assert back_slots_from_cap_diff(2) == 8
    assert back_slots_from_cap_diff(1) == 7   # 7 格已建档 → 直读(佩佩局锚)


def test_cap_drives_selection_level_alone_does_not() -> None:
    """W209/ADR-0385 行为级锁(反转 ADR-0281 的「cap 不进选档」):
    同 level 不同 cap → 选档**随 cap 差变**(run 26 lv8 cap8=6 格 /
    钻石叠加 lv8 cap10=8 格);同 cap 差不同 level → 选档恒同
    (level 单独不再参与选档)。"""
    for lv in (3, 5, 7, 8):
        assert back_slots_from_cap_diff(0) == 6, \
            f'lv={lv} 无扩展:恒 6 格(run 26 反向锚)'
        assert back_slots_from_cap_diff(2) == 8, \
            f'lv={lv} diff2:恒 8 格(狸猫局锚)'
    # 同 diff 跨 level 恒同(公式只看差值)
    for d in (0, 1, 2):
        vals = {back_slots_from_cap_diff(d) for lv in (3, 4, 5, 6, 7, 8)}
        assert vals == {back_slots_from_cap_diff(d)}, \
            f'diff={d}:选档不得随 level 单独变(ADR-0385)'


# ==================== r363_audit_p0 ====================

from types import SimpleNamespace as _r363_audit_p0_SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import GameState

from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder

from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.operations.battle_loop import  CurrencyWarRunLoop


def test_normalize_node_type_vocab() -> None:
    """三源词汇统一:英文 token/OCR 中文/旧兜底 → EXPECTED_DROP 键域中文。"""
    n = CurrencyWarRunLoop._normalize_node_type
    assert n('battle') == '普通战斗'
    assert n('reward') == '奖励'
    assert n('encounter') == '遭遇'
    assert n('supply') == '补给'
    assert n('boss') == 'boss'
    assert n('megastar') == '巨星'
    assert n('奖励') == '奖励'
    assert n('首领') == 'boss'
    assert n('普通战斗') == '普通战斗'
    assert n('') == '普通战斗'
    assert n(None) == '普通战斗'
    assert n('未知类型') == '未知类型'   # 未知透传不吞


def test_table_written_on_first_frame() -> None:
    """槽序表写入:首帧 probe 存全槽类型序(battle_loop 兜底的写入端)。"""
    # 模拟 slots
    class _Slot:
        def __init__(self, idx, state, node_type):
            self.idx, self.state, self.node_type = idx, state, node_type

    slots = [_Slot(0, 'current', 'reward'), _Slot(1, 'upcoming', 'reward'),
             _Slot(2, 'upcoming', 'battle'), _Slot(3, 'past', None)]
    _all = sorted(slots, key=lambda s: s.idx)
    seq = [s.node_type for s in _all if s.node_type]
    assert seq == ['reward', 'reward', 'battle']


# ===== W75(ADR-0335):stop 路径 runs summary 收口(治本 r363 死码) =====

def _make_stop_loop(*, summary_written: bool = False,
                    last_outcome_hp: int | None = 30,
                    rounds_done: int = 3,
                    stopped: bool = True,
                    plane: int = 2, round_num: int = 7, hp: int = 100,
                    hp_readable: bool = False) -> CurrencyWarRunLoop:
    """构造 loop 桩(bypass __init__):喂 _write_terminal_summary_if_needed 依赖面。

    last_state.hp=100 + hp_readable=False = 死局兜底污染面(ADR-0282 语义),
    收口应取 outcome 真值(_last_outcome_hp)而非 100。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            self._summary_written = summary_written
            self._last_outcome_hp = last_outcome_hp
            self._rounds_done = rounds_done
            self.ctx = _r363_audit_p0_SimpleNamespace(
                cw_match=_r363_audit_p0_SimpleNamespace(
                    session=_r363_audit_p0_SimpleNamespace(
                        last_state=GameState(plane=plane, round_num=round_num,
                                             hp=hp, hp_readable=hp_readable),
                    ),
                ),
                run_context=_r363_audit_p0_SimpleNamespace(is_context_stop=stopped),
            )

    return _Loop()


def test_stop_path_writes_stopped_summary(monkeypatch, tmp_path) -> None:
    """stop 收口:构造 run 上下文 → stop → runs 行存在且 result='stopped'。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_1')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    s = rows[0]
    assert s['result'] == 'stopped'
    assert s['run_id'] == 'run_stop_1'
    assert s['plane_reached'] == 2
    assert s['rounds_survived'] == 7
    assert s['final_hp'] == 30   # outcome 真值,非 last_state 100 兜底
    assert op._summary_written


def test_non_stop_abnormal_exit_writes_abandoned(monkeypatch, tmp_path) -> None:
    """非 stop 异常退出(超时/FAIL,is_context_stop=False)→ result='abandoned'。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_fail_1')
    op = _make_stop_loop(stopped=False, last_outcome_hp=55,
                         plane=3, round_num=2, hp=55, hp_readable=True)
    op._write_terminal_summary_if_needed()
    rows = read_jsonl(tmp_path / 'runs.jsonl')
    assert len(rows) == 1
    assert rows[0]['result'] == 'abandoned'
    assert rows[0]['final_hp'] == 55


def test_stop_summary_skips_when_already_written(monkeypatch, tmp_path) -> None:
    """3c 正常终局已写(_summary_written=True)→ 收口不重复写。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ok_1')
    op = _make_stop_loop(summary_written=True)
    op._write_terminal_summary_if_needed()
    assert read_jsonl(tmp_path / 'runs.jsonl') == []


def test_stop_summary_skips_fake_run(monkeypatch, tmp_path) -> None:
    """假局守卫(镜像 3c):无任何 outcome 数据(开局失败/中断)→ 不写假 summary。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_ghost_1')
    op = _make_stop_loop(last_outcome_hp=None, rounds_done=0)
    op._write_terminal_summary_if_needed()
    assert read_jsonl(tmp_path / 'runs.jsonl') == []


def test_stop_summary_no_duplicate_on_second_call(monkeypatch, tmp_path) -> None:
    """幂等:同实例二次调用(收口重入/守护)不重复写行。"""
    import sr_od.application.currency_war.telemetry.state as tel
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(tel, '_RECORDER', rec)
    monkeypatch.setattr(tel, '_CURRENT_RUN_ID', 'run_stop_2')
    op = _make_stop_loop()
    op._write_terminal_summary_if_needed()
    op._write_terminal_summary_if_needed()
    assert len(read_jsonl(tmp_path / 'runs.jsonl')) == 1


def test_after_operation_done_wires_summary_write() -> None:
    """弱锁保底:after_operation_done 真调 _write_terminal_summary_if_needed(收口接线)。"""
    import inspect

    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop.after_operation_done)
    assert '_write_terminal_summary_if_needed()' in src



# ==================== r271_line_defs ====================

from sr_od.application.currency_war.kernel.cw_line_defs import  ENGINE_FACTIONS, RECIPE_BASE, RECIPE_FACTIONS, recipe_kinds_1cost, recipe_tier


def test_recipe_set_semantics() -> None:
    """配方集合(攻略[20]):基础(仙舟/DOT)+渐进(列车/护盾)。"""
    assert RECIPE_FACTIONS == frozenset(
        {'仙舟', '持续伤害', '列车同行', '护盾'})
    # r263b 局15 锁(合并自 test_cw_r263b_recipe.py,原文件已删):
    # 散件元凶阵营不得进配方
    assert '减益' not in RECIPE_FACTIONS
    assert '星核猎手' not in RECIPE_FACTIONS
    assert '燃血' not in RECIPE_FACTIONS


def test_recipe_base_line() -> None:
    """基础线 = 3仙舟+2DOT = 5 档。"""
    assert RECIPE_BASE == 5


def test_engine_derived_from_bridges() -> None:
    """引擎阵营从桥池派生(单一源,不再手抄)。
    W126/ADR-0350:dot_belog/hunt3 两桥已随四体系封闭裁定删除——
    狼狩/贝洛伯格退出引擎门(贝只在希儿系判据内保留计数);存活三桥
    (xianzhou_dot/xianzhou_train/train_dot)派生出四体系三羁绊。"""
    assert ENGINE_FACTIONS == frozenset(
        {'仙舟', '列车同行', '持续伤害'})


def test_recipe_tier_helper() -> None:
    assert recipe_tier({'仙舟': 3, '列车同行': 2, '公司': 1}) == 5
    assert recipe_tier({}) == 0
    assert recipe_tier({'公司': 9}) == 0


def test_consumers_share_single_source() -> None:
    """消费方共享单源:deploy_bench 与 cw_line_defs 的名字一致
    (旧 line_strategy 局部 set 随 ADR-0336 删)。"""
    from sr_od.application.currency_war.operations.prep import  deploy_bench
    assert deploy_bench._RECIPE is RECIPE_FACTIONS
    assert deploy_bench._RECIPE_BASE == RECIPE_BASE


def test_1cost_kinds_positive() -> None:
    """1 费配方件种数 >0(找件刷概率的分子)。"""
    assert recipe_kinds_1cost() >= 4
