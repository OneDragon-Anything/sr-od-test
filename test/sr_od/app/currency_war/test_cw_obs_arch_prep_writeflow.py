# -*- coding: utf-8 -*-
"""统一观察架构·实机半边写入流对拍夹具(试点步骤 1;设计正本 =
docs/develop/currency_war/design/统一观察架构-画面op基类设计.md §9.1 主门
(b)腿「写入流分域夹具对拍」+ §2.3 实机实现 = 识别链映射表;sim 半边 =
步骤 2 辖域,本文件不涉及)。

夹具链路(§9.1-B2 实机半边):**固定帧源(桩化 reader 形态)→ 实机适配器
payload → BoardState 全帧对拍(回归 pin 钉 payload)**。

- 固定帧源 = 与现役在册行为锁**同源**的桩化 reader 形态:reader 桩直接
  复用 ``test_cw_board_state._patch_clean_readers``(单一源,禁复制漂移;
  其真读值面在 test_observation_feed_wires_board_state 已锁)——轻视觉
  域(球/箱/典籍/占用像素)在 pd_mod 命名空间桩空;
- 被测链 = 真实 ``CwScreenPrep._observe(heavy=True)``(实机适配器①的
  封口内容:observe_full + read_game_state 漏斗 + BoardState 观察写端)
  经五段生命周期 run_lifecycle 驱动(段1 observe → 段2 reconcile);
- 对拍口径 = BoardState 全帧快照(值/来源/evidence 三元)逐字段对
  回归 pin;pin 面覆盖 prep_clean 帧触达的全部建模域 + 未触达域的
  恒 None 断言(禁静默新写端)。

被锁语义的保绿面(试点批交付对照表载体):P2-1 备战席空集 = 失读非全空
(carry,不写「9 槽全空」观察)/ P3-10 合成升星特效窗内观察顺延(两态制
ADR-0651 等价形态:窗内读数不可信 → 本帧不写观察,保 logic 投影值)
——两者经本夹具在**新路径**上钉住。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_game_ports import (
    action_sink,
    observation_source,
)
from sr_od.application.currency_war.kernel.cw_board_state import (
    Field,
    NodeKey,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    BenchChar,
    DeferSpheres,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.app.currency_war._cw_helpers import make_prep_round_director
from test.sr_od.app.currency_war.test_cw_board_state import (
    _patch_clean_readers,
)


def _fixed_bench() -> list[BenchChar]:
    """固定帧源·备战席身份(2 占 + 7 空;真值与 fake_p1 锚同族)。"""
    return [BenchChar(slot=1, char_id='希儿', star=2, faction='?'),
            BenchChar(slot=2, char_id='景元', star=1, faction='?')]


def _make_director(test_context: SimpleNamespace,
                   monkeypatch: pytest.MonkeyPatch,
                   bench_chars: list[BenchChar],
                   *,
                   merge_effect_window: bool = False) -> CwScreenPrep:
    """实机适配器夹具装配:裸 ctx(全部 area rect 缺失 → 真读链自然失读,
    同 _feed_ctx 口径)+ 固定帧源桩 + 真实 _observe 经五段驱动。

    执行侧 tracked 账对账(`_reconcile_tracking`)不在本夹具辖域
    (执行侧装配源 = 尾批,ADR-0530),桩化防漂。
    """
    from sr_od.application.currency_war import currency_war_config as cfg_mod
    from sr_od.application.currency_war.kernel import cw_reconcile
    from sr_od.application.currency_war.obs import cw_arbitration
    from sr_od.application.currency_war.obs import cw_observe_full
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )

    session = SimpleNamespace(last_streak=0, active_strategies=[])
    ctx = SimpleNamespace(
        cw_match=SimpleNamespace(
            session=session,
            strategy=SimpleNamespace(
                decide_prep_screen=lambda sess, cfg: [DeferSpheres()])),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda **kw: []),
        current_instance_idx=99,
    )
    d = CwScreenPrep.__new__(CwScreenPrep)   # 免 SrContext(读屏全桩,同 gate_hooks 装配)
    d.ctx = ctx
    d._bench_pts = []   # 槽位中心惰性读的初值面(__init__ 桩;裸 ctx 恒空读)

    # 环入口序列桩(离线;清场/收起/补采/光标泊位/截屏 = 读图域,固定帧源代答)
    monkeypatch.setattr(d, '_clear_entry_overlays', lambda: None)
    monkeypatch.setattr(d, '_try_collapse_open_shop', lambda: False)
    monkeypatch.setattr(d, '_takeover_collect_if_needed', lambda m, s: None)
    monkeypatch.setattr(d, 'park_cursor', lambda: None)
    monkeypatch.setattr(d, 'screenshot', lambda: None)
    monkeypatch.setattr(d, 'round_by_find_area',
                        lambda screen, s, a, **k: SimpleNamespace(is_success=False))
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    monkeypatch.setattr(d, '_reconcile_tracking',
                        lambda bench, deployed, screen=None: None)
    # config 面(决策段输入;本夹具只辖观察/对账两段,桩型即可)
    monkeypatch.setattr(cfg_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace())

    # —— 固定帧源(桩化 reader 形态;heavy 状态半复用在册同源桩)——
    _patch_clean_readers(monkeypatch)
    # 轻视觉域:球/箱/典籍/占用像素(pd_mod 命名空间导入面)
    monkeypatch.setattr(pd_mod, 'read_reward_spheres', lambda ctx_, screen: [])
    monkeypatch.setattr(pd_mod, 'read_supply_boxes', lambda ctx_, screen: [])
    monkeypatch.setattr(pd_mod, 'cw_identity_obs_read_tomes',
                        lambda ctx_, screen: [])
    monkeypatch.setattr(pd_mod, 'slot_occupied', lambda screen, x, y: False)
    # heavy 身份半:observe_full 产固定身份 + 真实 read_game_state 漏斗状态
    monkeypatch.setattr(pd_mod, 'ensure_portrait_templates',
                        lambda ctx_: {'stub': True})

    def _fake_observe_full(ctx_, screen, *, tier='', source='', op=None,
                           shop_open=False, session=None) -> dict:
        return {'state': _read_game_state(ctx_),
                'bench_chars': list(bench_chars),
                'deployed_chars': [],
                'substate': {}}

    def _read_game_state(ctx_):
        from sr_od.application.currency_war.obs.cw_observation import (
            PHASE_PREP_CLEAN,
            read_game_state,
        )
        return read_game_state(ctx_, None, phase=PHASE_PREP_CLEAN)

    monkeypatch.setattr(cw_observe_full, 'observe_full', _fake_observe_full)
    # cap/deploy 计数读(桩值与身份半同源:2 部署 = cap 5(=level,ADR-0281 常态))
    monkeypatch.setattr(pd_mod, 'read_deploy_cap', lambda ctx_, screen: 5)
    monkeypatch.setattr(pd_mod, 'read_deployed_count', lambda ctx_, screen: 2)
    # 双源仲裁:桩值恒一致(paddle 2 = cv 0 + 帧源无前排区 → 判据面在本夹具
    # 不可评,仲裁分歧走 cw_arbitration 自辖的行为锁)
    monkeypatch.setattr(cw_arbitration, 'arbitrate',
                        lambda key, values: (2, 'match', False))
    # 合成升星特效窗门(P3-10):用例参数化(默认无窗 → 正常核对)
    monkeypatch.setattr(cw_reconcile, 'is_merge_effect_window',
                        lambda screen: merge_effect_window)
    return d


def _frame_snapshot(bs) -> dict[str, tuple]:
    """BoardState 全帧快照:Field 域名 → (值, 来源, evidence) 三元。"""
    snap: dict[str, tuple] = {}
    for f in dataclasses.fields(bs):
        val = getattr(bs, f.name, None)
        if isinstance(val, Field):
            snap[f.name] = (val.value, val.source, val.evidence)
    return snap


#: 回归 pin(回归钉 payload):prep_clean 帧 + 固定备战席身份的预期全帧。
#: 值面 = _patch_clean_readers 的真读值(该面由 test_observation_feed_
#: wires_board_state 在读链侧同源锁);来源/evidence 面 = §2.1 来源四分类
#: (hp 开局先验 = prior:adr-0559,ADR-0559)。
_PIN_FRAME: dict[str, tuple] = {
    'node': (NodeKey(plane=1, round_num=4, kind='battle'), 'observation', None),
    'gold': (20, 'observation', None),
    'level': (5, 'observation', None),
    'xp': ((2, 8), 'observation', None),
    'hp': (82, 'prior', 'prior:adr-0559'),
    'board': ({'列车同行': 2}, 'observation', None),
}


def test_prep_writeflow_full_frame_pin(test_context: SimpleNamespace,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """主门(b)实机半边:固定帧源 → 实机适配器 → BoardState 全帧对拍。

    判据:①pin 面逐字段(值/来源/evidence 三元)对拍——写入流任一环
    节(读链/写闸/来源标注)漂移即红;②未被 prep_clean 帧触达的域恒
    None(禁静默新写端);③备战席观察写端:P2-1 语义(非空集 → observe,
    槽位保序)。"""
    d = _make_director(test_context, monkeypatch, _fixed_bench())
    sess = d.ctx.cw_match.session
    # fast_sleep(README 第 6 条):终结出口 round_success(wait=1.0)的轮间
    # 等待是 op 框架真 sleep(实测每 run 2×0.5s),mock 画面下纯属空等。
    with fast_sleep():
        d.run_lifecycle()
    bs = board_state_of(sess)
    snap = _frame_snapshot(bs)
    for name, expected in _PIN_FRAME.items():
        got = snap.get(name)
        assert got == expected, (
            f'写入流对拍失配[{name}]:预期 {expected!r} 实得 {got!r}')
    # 未触达域恒 None(prep_clean spec 外 + 空值中继闸,§2.1)
    for name in ('streak', 'level_up_cost', 'enemy_difficulty', 'shop',
                 'active_strategies', 'active_env', 'plane_bosses',
                 'enemy_affixes', 'selected_difficulty', 'settlement'):
        assert snap[name][0] is None, (
            f'[{name}] 不该被本帧写入(禁静默新写端),实得 {snap[name]!r}')
    # 备战席观察写端:槽位保序(下标 i = 物理槽 i+1,§3.2.5)+ 来源 observation
    bench_val, bench_src, _ev = snap['bench']
    assert bench_src == 'observation'
    assert [s.unit.char_id if s.kind == 'unit' else None
            for s in bench_val.slots] == ['希儿', '景元'] + [None] * 7
    # 段序:观察 → 对账(夹具辖前两段;decide 由桩脚本交回)
    assert d._lifecycle_trace[:2] == ['observe', 'reconcile'], (
        f'五段段序漂移:{d._lifecycle_trace}')


def test_prep_writeflow_empty_bench_is_miss_not_clear(
        test_context: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P2-1(批次二落地审)经新路径钉住:备战席空集 = 失读非全空 →
    carried 处置(从未读过 = 保持 None),禁把「9 槽全空」当 observation
    入记录(席空数派生误报 free=9/挂起合成升星预期被空视图误清)。"""
    d = _make_director(test_context, monkeypatch, [])
    with fast_sleep():
        d.run_lifecycle()
    bs = board_state_of(d.ctx.cw_match.session)
    # 处置②(§2.2:字段从未读过 → 保持 None):空集经 bench_view_from_obs
    # 返 None → carry 对未写字段为 no-op → 值恒 None(Field 默认 source
    # 无义,断言只看值与「无写入发生」)。
    assert bs.bench.value is None, (
        '空集 = 失读(P2-1):禁写「9 槽全空」观察,未读过的字段保持 None')


def test_prep_writeflow_merge_window_defers_observe(
        test_context: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P3-10 经新路径钉住(两态制 ADR-0651 等价形态):合成升星特效窗内
    星读不可信(门后保旧星,reconcile_tracking 防抖同口径)→ 备战席观察
    **本帧不写**——bench 保 BuyCard 的 logic 投影值,且不产生「投影 vs
    窗内旧星读数」的观察失配缺陷行(噪声抑制语义保留);下帧干净帧实读
    覆盖:一致 = 零缺陷行,失配 = 投影 bug 留证修码。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        ChannelSig,
        BenchView,
        bench_view_of_slots,
        consume_defect_sink,
        set_defect_sink,
    )
    d = _make_director(test_context, monkeypatch, _fixed_bench(),
                       merge_effect_window=True)
    sess = d.ctx.cw_match.session
    # 预置 BuyCard 合成升星投影(两态制:write_logic 直写;期望 = 星级
    # 抬升面,与 _fixed_bench 的窗内旧星读数必失配)
    bs = board_state_of(sess)
    proj: BenchView = bench_view_of_slots(
        [BenchChar(slot=1, char_id='希儿', star=3, faction='?'),
         BenchChar(slot=2, char_id='景元', star=1, faction='?')])
    bs.write_logic(bs.bench, proj, produced_by='BuyCard',
                   sig=ChannelSig(family='logic_action', actor='TestSigWriter',
                                  mode='compute'))
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        with fast_sleep():
            d.run_lifecycle()
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert bs.bench.value is proj and bs.bench.source == 'logic', (
        '特效窗内观察不写:bench 保持 logic 投影值(P3-10 两态等价)')
    assert rows == [], '窗内不产生观察失配缺陷行(噪声抑制语义保留)'


# ==================== 旧路径代表锁(并存窗专用,退役批随删)====================
# 架构设计 §9.1 并存期(试点步骤 1):生产缺省装配(端口 None)实际在跑
# cw_screen_prep.run 的旧路径分支,而四份备战行为锁全部经缺省装配点走新
# 路径——旧路径回归无锁能红 = 并存窗覆盖缺口。本节补 2 条**不装端口**
# 的代表锁:各断言一个关键行为(签名写点/收起探针恰一次),断言面与
# 在册新路径锁同语义、仅去掉端口桩走原生 run(),禁在本节加新语义。
# 退役时机 = 旧路径退役批:旧路径删除时本节整节随删,勿迁移。


def test_legacy_path_prep_records_action_signature(
        test_context: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """旧路径签名写点代表锁:不装分流桩端口(= 生产缺省装配)时,备战
    单轮 run() 旧路径决策出口写 ``exec_state_of(session).last_prep_action_sig``
    (环级无进展守卫动作腿的唯一写点)。与 test_cw_no_progress_guard 的
    签名写点锁同语义断言(该锁经缺省装配走新路径),本锁补旧路径半边:
    窗口内任何提交改坏旧路径决策出口时本锁红,全量不绿。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        OpenShop,
    )

    d, _match, session = make_prep_round_director(
        test_context, monkeypatch, [OpenShop(read_only=True)],
        install_dispatch_ports=False)
    # 确走旧分支判别(统一观察架构设计 §9.1 并存期;装配点 =
    # cw_screen_prep.run 按两端口在场与否分流):端口被上游污染在场时,
    # 本节代表锁的断言面(新旧路径同语义)会静默变新路径锁且全量仍绿
    # ——run 前断言装配判据入参为两端口 None,并桩记新路径入口证其零调用。
    lifecycle_calls: list[int] = []
    monkeypatch.setattr(d, 'run_lifecycle',
                        lambda *a, **k: lifecycle_calls.append(1))
    assert (observation_source(), action_sink()) == (None, None), (
        '游戏端口在场(上游污染/装配泄漏):本锁辖的已不是旧路径分支')
    with fast_sleep():
        enter_running_state(test_context)
        try:
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert not lifecycle_calls, (
        'run() 经装配点走了新路径 run_lifecycle(旧路径代表锁失义)')
    assert exec_state_of(session).last_prep_action_sig == ('OpenShop',), (
        f'旧路径决策出口须写动作批签名:'
        f'{exec_state_of(session).last_prep_action_sig!r}')


def test_legacy_path_entry_collapse_probe_once(
        test_context: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """旧路径收起探针代表锁:不装分流桩端口时,备战单轮入口的开店态
    收起探针**恰一次**,单轮交回外循环(交回语义由外循环每轮重识别保证)。
    与 test_cw_gate_hooks 的 test_prep_round_entry_collapse_once 同语义
    断言(该锁经缺省装配走新路径),本锁补旧路径半边:窗口内旧路径入口
    序列回归(探针丢失/多次/不交回)时本锁红。"""
    collapse_calls: list[bool] = []

    def _fake_collapse() -> bool:
        collapse_calls.append(True)
        return True

    d, _match, _session = make_prep_round_director(
        test_context, monkeypatch, [DeferSpheres()],
        install_dispatch_ports=False)
    # 确走旧分支判别(同上条代表锁:装配点分流污染防护,§9.1 并存期)。
    lifecycle_calls: list[int] = []
    monkeypatch.setattr(d, 'run_lifecycle',
                        lambda *a, **k: lifecycle_calls.append(1))
    assert (observation_source(), action_sink()) == (None, None), (
        '游戏端口在场(上游污染/装配泄漏):本锁辖的已不是旧路径分支')
    monkeypatch.setattr(d, '_try_collapse_open_shop', _fake_collapse)
    with fast_sleep():
        enter_running_state(test_context)
        try:
            rr = d.run()
        finally:
            reset_running_state(test_context, d)
    assert not lifecycle_calls, (
        'run() 经装配点走了新路径 run_lifecycle(旧路径代表锁失义)')
    assert collapse_calls == [True], f'收起探针应恰调一次,实得 {collapse_calls}'
    assert '交回外循环' in (rr.status or ''), f'单轮须交回外循环:{rr.status!r}'


# ==================== 选卡调用面单一源守卫(BoardState 迁移收尾) ====================

def test_box_card_pick_single_source_wiring() -> None:
    """选卡决策区单一源守卫(墓碑 + 接线双角):``PrepActionExecutor
    ._default_box_card`` 是 pick 族调用面最后一个切到 BoardState 消费视图
    的接入点(prep_actions 内单一源宣言注释;设计正本 = docs/develop/
    currency_war/design/BoardState-数据结构设计.md §8.7 批次二,单一源
    本体 = kernel/cw_bs_view.strategy_input_state)。

    - 墓碑角(否定式 + 退役背书):选卡决策区禁回落 ``last_state or
      GameState`` 直读字面——被删的 cw_screen_supply.pick_box_card 原本
      同款直读,迁移批已切除;该第二源回流 = BoardState 观察流旁路
      (失读帧 carry 语义/记录模型全部绕过),全量照绿但单一源纪律破;
    - 接线角:同区必须仍含 strategy_input_state 调用——接入点静默脱落
      是回归直读的另一形态(换写法绕开墓碑字面),与墓碑角成对堵死;
    - 变异自检:``decide_box_card`` 在场断言钉住扫描对象是选卡决策区
      本体,防 getsource 抓错函数后双断言恒真空转。
    """
    import inspect

    from sr_od.application.currency_war.prep_actions import PrepActionExecutor

    src = inspect.getsource(PrepActionExecutor._default_box_card)
    assert 'decide_box_card' in src, '扫描锚失守:getsource 未取到选卡决策区'
    assert 'last_state or GameState' not in src, (
        '选卡决策区回落 last_state or GameState() 直读第二源'
        '(BoardState 单一源纪律破,观察流被旁路)')
    assert 'strategy_input_state(' in src, (
        '选卡决策区单一源接入点脱落(strategy_input_state 未被调用,'
        '回归直读同罪)')
