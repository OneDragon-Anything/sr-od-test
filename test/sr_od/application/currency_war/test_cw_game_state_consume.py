"""GameState 消费切换批回归锁(迁移批次二;设计正本 =
docs/develop/sr_od/application/currency_war/
changes/2026-09-11-unified-state/details/GameState-数据结构设计.md,下称「设计」)。

锁面 = 批次二任务书件:§3.4 单次逻辑写入口(申报豁免写端,合同正本在
批一文件)/§3.3.6-8 刷新执行事实组(付费/免费闸/下限 0/evidence 轮键
一锁)/§3.2.6 board 下档派生单一源(ADR-0488 同键供给)/§3.5.1 结算
覆盖写端(四形态一锁)。断言全部按设计语义写;批一回归锁正本在
test_cw_game_state.py。

退役面(审计判决删除):§3.3.1 cost_source 三值归并消费组(src 零调用)、
§6.2+§8.8 局终归档快照锁(零调用)、relay 正写形态锁(game_state 侧
正本辖)、bench_is_full 同键供给锁(派生面已由席空数锁辖)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    apply_settlement_cover,
    board_next_tier_of,
    consume_defect_sink,
    game_state_of,
    set_defect_sink,
)

# ---- W1 sig 铺满 helper(测试写入口签名必填,ADR-0634;actor 已登记)----
from sr_od.application.currency_war.kernel.cw_game_state import (  # noqa: E402
    ChannelSig as _ChannelSig,
)


def _sig() -> _ChannelSig:
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _lsig() -> _ChannelSig:
    """渠道②签名(logic_action 族;逻辑写入/confirm)。"""
    return _ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _hsig() -> _ChannelSig:
    """渠道③签名(logic_hook 族;relay 中继)。"""
    return _ChannelSig(family='logic_hook', actor='TestSigWriter',
                       mode='compute')


# ============================================================ 共用 helper

# (§8.7 消费适配器锁族(game_state_view/strategy_input_state 语义 7 锁)
#  已随 kernel/cw_bs_view 文件退役同批删除(波 5b 双删;锁与所辖面同批
#  退役,test_cw_replay_session_restore 先例)——适配器消费切换后生产
#  直调=0,文件本体删除,视图语义无消费面可锁。)


# ============================================================ §3.4 单次逻辑写入口
# (write_logic 直写合同正本 = test_cw_game_state.py::test_write_logic_direct_write_immediately_readable;
#  观察赢+失配留证正本(含一致静默反腿)= 同文件
#  test_observe_over_logic_mismatch_emits_defect_row;此处不重复。)

# ============================================================ §3.3.6-8 刷新执行事实组
# (2026-09-18 迁入裁决:计数组住效果账本 ActiveEffectInventory,写端 =
#  刷新上报函数统一触发;效果账本直测 = test_cw_game_state 账本面,
#  本锁保留计数语义面,载体换账本属性。)


def test_refresh_execution_paid_and_free_frame_gates() -> None:
    """§3.3.6-8 刷新执行主锁(三腿一锁):①付费刷新 = paid+1 ∧ total+1
    (付费帧不动免费余额);②免费帧闸 = 免费帧不进付费累计(长线利好
    触发计数载体禁混入免费刷),消耗免费余额 + total 照计;③免费余额
    下限 0(计数器单调域,禁负值漂移)。载体 = 效果账本
    ``gs.effects.record_refresh``(原 Field 版 record_refresh_execution
    随迁入裁决退役;evidence 轮键面随 Field 通道退役)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.record_refresh(free=False)
    assert gs.effects.refresh_paid == 1
    assert gs.effects.refresh_total == 1
    assert gs.effects.free_refresh_balance == 0, '付费帧不动免费余额'
    # ②/③ 免费帧闸:效果发放预置余额后免费刷新消耗
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs2.effects.grant_free_refreshes(1)
    bs2.effects.record_refresh(free=True)
    assert bs2.effects.refresh_paid == 0, '免费帧禁写付费计数'
    assert bs2.effects.free_refresh_balance == 0, '免费余额消耗,下限 0'
    assert bs2.effects.refresh_total == 1, '全量计数含免费'
    bs2.effects.record_refresh(free=True)
    assert bs2.effects.free_refresh_balance == 0, '免费余额下限 0(禁负值漂移)'


# ============================================================ §3.2.6 派生单一源(ADR-0488)


def test_board_next_tier_of_matches_registry_formula() -> None:
    """§3.2.6/§8.8 准入③:下档阈值派生 = 注册表 tiers 取 >count 最小档;
    obs computed 支委托本源(结构锁:函数体调用 kernel 单一源,禁第三份
    推导;旧 sim 键对拍随 sim 重做删除面退役——新引擎写容器,无该键)。"""
    from sr_od.application.currency_war.data.cw_factions import FACTIONS
    board = {'列车同行': 2, '持续伤害': 0}
    expect = {}
    for f, c in board.items():
        tiers = FACTIONS[f].tiers if f in FACTIONS else ()
        nt = next((t for t in tiers if t > c), 0)
        if nt:
            expect[f] = nt
    assert board_next_tier_of(board) == expect
    assert board_next_tier_of({}) == {}


# ============================================================ §3.5.1 结算覆盖写端


def test_settlement_cover_writes_truth_group() -> None:
    """§3.5.1 结算覆盖写端四形态一锁:①胜局 = observation 真值组(hp/
    streak 带方向/gold·level·xp 仅胜局)+ settlement 结构同步落;
    ②败局页无收入面板(gold/level/xp 缺席不写),hp/streak 真值照覆;
    ③hp 失读(结算页 OCR miss)不写(不可信帧不写,§2.2 写入闸),不清
    既有正式值;④progress_delta 带符号真值落 settlement 结构(胜局正/
    败局负;battle_wait 调用点传参为接线半,本锁辖函数半)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    apply_settlement_cover(gs, hp_after=76, streak_after=4,
                           killed=True, gold=23, level=6, xp=(3, 10))
    assert gs.hp.value == 76 and gs.hp.source == 'observation'
    assert gs.streak.value == 4, '带方向真值(正=连胜)'
    assert gs.gold.value == 23 and gs.level.value == 6
    assert gs.xp.value == (3, 10)
    s = gs.settlement.value
    assert s is not None and s.hp_after == 76 and s.killed is True
    # ② 败局页
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    apply_settlement_cover(bs2, hp_after=41, streak_after=-2, killed=False)
    assert bs2.hp.value == 41 and bs2.streak.value == -2
    assert bs2.gold.value is None and bs2.level.value is None
    assert bs2.xp.value is None
    assert bs2.settlement.value.gold is None
    # ③ hp 失读不写
    bs3 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs3.observe(bs3.hp, 80, sig=_sig())
    apply_settlement_cover(bs3, hp_after=None, streak_after=None)
    assert bs3.hp.value == 80 and bs3.hp.source == 'observation'
    # ④ progress_delta 带符号
    bs4 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    apply_settlement_cover(bs4, hp_after=76, streak_after=4, killed=True,
                           progress_delta=2, gold=23)
    assert bs4.settlement.value is not None \
        and bs4.settlement.value.progress_delta == 2
    apply_settlement_cover(bs4, hp_after=70, streak_after=-1, killed=False,
                           progress_delta=-22)
    assert bs4.settlement.value.progress_delta == -22, '败局负增量照落'


# ============================================================ 扩单件 3:§2.1 载体中继收敛
# (test_relay_skips_fields_with_official_value 第二刀移入
#  test_cw_game_state.py::test_relay_unit_gate_truth_table 的「已有正式值
#  跳过」腿——relay 单元锁同域归并,断言腿零丢失。)


# ============================================================ 扩单件 1:合成升星预期写端(§3.2.18 修法 a)


def test_detect_merge_upgrade_signature() -> None:
    """§3.2.18 修法 a 触发判定:同名最高星被抬升 = 合成签名(星级只经
    合成上升);普通买新卡/无变化 → False。种子 = 生产同形快照
    (_NS(bench=占席条目, deployed=行域 Unit),与 buy_card 升星腿同构)。"""
    from types import SimpleNamespace as _NS

    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        Unit,
        detect_merge_upgrade,
    )

    def _b(slot: int, name: str, star: int) -> BenchSlot:
        return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star,
                                                slot=slot))

    def _mk(bench, deployed=None):
        return _NS(bench=list(bench), deployed=list(deployed or []))

    c1 = _b(1, '花火', 1)
    c2 = _b(2, '花火', 1)
    c3 = _b(3, '花火', 1)
    cur = _mk([c1, c2, c3])
    proj = _mk([_b(1, '花火', 2)])
    assert detect_merge_upgrade(cur, proj) is True, '3 合 1 → 同名最高星抬升'
    assert detect_merge_upgrade(cur, _mk([c1, c2, c3])) is False, '无变化'
    assert detect_merge_upgrade(
        _mk([c1]), _mk([c1, _b(2, '花火', 1)]),
    ) is False, '普通买新卡不抬最高星'
    deployed_old = _mk([], [Unit(char_id='希儿', star=1, slot=1)])
    deployed_new = _mk([], [Unit(char_id='希儿', star=2, slot=1)])
    assert detect_merge_upgrade(deployed_old, deployed_new) is True, \
        '合成域 = 全场(bench+deployed)'


def test_merge_projection_direct_write_and_observe_wins() -> None:
    """§3.2.18 修法 a 两态制形态(ADR-0651):CwActionBuyCardParam 合成升星投影经
    write_logic **直写 bench**(策略器立即可读);下一备战帧实读覆盖
    (观察赢)——一致静默,失配 = 投影 bug 缺陷留证后修推算代码。
    投影视图构造 = 容器写侧单一源 bench_view_of_working(工作槽表直构)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        Unit,
        bench_view_of_working,
    )
    consume_defect_sink()

    def _view(star: int):
        table = [BenchSlot(kind='unit',
                           unit=Unit(char_id='花火', star=star, slot=1))]
        return bench_view_of_working(table + [None] * 8)

    proj_view = _view(2)
    real_view = _view(2)
    # 一致路径:逻辑直写 → 字段立即可读;同值实读覆盖 = 静默
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.bench, proj_view, produced_by='CwActionBuyCardParam', sig=_lsig())
    assert gs.bench.value is proj_view and gs.bench.source == 'logic', \
        '投影直写:策略器立即可读(ADR-0651)'
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.bench, real_view, sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert rows == [], '投影与实读一致 = 零缺陷行'
    assert gs.bench.source == 'observation', '实读后来源翻 observation(正常)'
    # 失配路径:观察赢覆盖真值 + 缺陷留证(失配 = 推算 bug,修推算代码)
    bs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    bs2.observe(bs2.bench, real_view, sig=_sig())
    bs2.write_logic(bs2.bench, _view(1),
                    produced_by='CwActionBuyCardParam', sig=_lsig())
    rows2: list[dict] = []
    set_defect_sink(rows2.append)
    try:
        bs2.observe(bs2.bench, real_view, sig=_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows2) == 1, '失配留证(kind=observe_vs_logic_mismatch)'
    assert rows2[0]['kind'] == 'observe_vs_logic_mismatch'
    assert rows2[0]['ts'], '缺陷行补 ts(迭代 2026-09-16-unified-obs-reconcile 新行形状)'
    assert bs2.bench.value == real_view \
        and bs2.bench.source == 'observation', \
        '观察赢:实读覆盖逻辑值(推算 bug 不挂账,留证修码)'


# ============================================================ 扩单件 4:parse_streak 失读 None 化(§8.8)


def test_streak_miss_semantics_parse_and_observation_half() -> None:
    """streak 失读两腿并一(合并原 test_parse_streak_miss_is_none_real_
    zero_is_zero / test_settlement_observation_half_preserves_streak_on_
    miss,断言腿逐条保留):

    - 解析腿(§8.8):失读 → None(与 read_hp 100 假值同型消除);
      '连胜×0' = 真 0(方向真值,fixture 核实 2026-08-11),两者分写;
    - 消费腿(失读守卫):obs.streak None → session.last_streak 跳过沿用
      (旧行为失读写 0 = 连胜/连败假复位);真值照写。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import (
        parse_streak,
    )
    # 解析腿
    assert parse_streak(['挑战结束', '数据统计']) is None, '失读非 0'
    assert parse_streak(['连胜×0']) == 0, '真 0 保留'
    assert parse_streak(['连败×2']) == -2
    # (消费腿已随终态契约 §B 迁容器:结算带符号真值由 apply_settlement_cover
    #  直写 gs.streak,session.last_streak 退役——失读跳过语义由覆盖写端
    #  None 守卫承载,见 fields.md §3.2.12/§3.5.1。)


# ============================================================ 批次二返工批修复锁(P2-1/P3-x)

def test_bench_read_empty_is_miss_not_full(monkeypatch) -> None:
    """P2-1:备战席 SIFT 空集 = 失读(overlay 残留/动画帧/识别退化)≠实席
    全空——读链直产(P6,原观察写端值构造器空集守卫移驻读链)零占用返
    None(调用方走 carried,§2.2 处置①;宁缺勿造),禁把「9 槽全空」当
    observation 入记录(席空数派生误报 free=9/挂起合成升星预期被空视图
    误清);非空 = 槽位保序视图 + 占位件 kind 识别期细分 + SIFT 身份胜出;
    越界条目丢弃(读链漂移)。"""
    from sr_od.application.currency_war.obs import cw_identity_obs as obs
    # 空读:零命中 + 零占槽物品 → None(禁合成全空视图)
    monkeypatch.setattr(obs, 'identify_slots', lambda *a, **k: [])
    monkeypatch.setattr(obs, '_ctx_slots', lambda ctx, prefix, count: [])
    monkeypatch.setattr(obs, '_bench_item_kind_by_slot',
                        lambda ctx, screen: {})
    assert obs.read_bench_view(object(), object(), object()) is None, \
        '空集 = 失读,禁合成全空视图'
    # 非空 = 槽位保序视图;越界条目不落槽;占位物品 kind 细分,SIFT 身份胜出
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    view = obs._bench_view_of(
        [Unit(char_id='花火', star=2, slot=2),
         Unit(char_id='越界角色', star=1, slot=0),    # 越界:丢弃
         Unit(char_id='越界角色2', star=1, slot=11)],  # 越界:丢弃
        {1: 'tome', 2: 'supply_box'})
    assert view is not None
    assert [s.kind for s in view.slots] == ['tome', 'unit'] + ['empty'] * 7, \
        '槽位保序(物理槽 1=典籍,2=角色);越界条目不落槽;占槽物品只填空槽'
    assert view.slots[1].unit is not None and view.slots[1].unit.star == 2


# (三审整删)原 test_prep_bench_obs_miss_guard_and_tome_choice_wiring
# 「接线存在性烟雾」(getsource 字符串在场四断言:备战观察写端接线/
# _gs_obs.carry/特效窗门/chosen_tome 写端)——源码扫描形态(README 禁止
# 清单,判据「红时哪个运行行为坏了」答不出)。守卫函数行为半由
# test_bench_read_empty_is_miss_not_full 辖;特效窗门行为半由
# test_merge_effect_window_gate_default_off_and_injectable 辖;op 装配面
# 接线归 review 与代码规范。


def test_merge_effect_window_gate_default_off_and_injectable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P3-10:特效窗判定读口——screen=None/槽缺省关恒 False(核对放行,
    与既有门 best-effort 语义同向);注入后按实现判定(monkeypatch 还原)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile

    assert cw_reconcile.is_merge_effect_window(None) is False, \
        'screen=None 不拦(离线/测试注入态)'
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME', None,
                        raising=False)
    assert cw_reconcile.is_merge_effect_window(object()) is False, \
        '槽缺省关(未装配)= 核对放行'
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: True, raising=False)
    assert cw_reconcile.is_merge_effect_window(object()) is True, \
        '窗内 = 顺延核对信号'
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: False, raising=False)
    assert cw_reconcile.is_merge_effect_window(object()) is False


# ============================================================ 四事件屏 chosen_* 接线锁(设计 §3.4.5 余屏写端)

def _op_with_session(op_cls: type, sess: object) -> object:
    """``__new__`` 绕过 op 构造(SrContext 全量依赖不可裸建);只喂四屏
    chosen 记录面读取的唯一 ctx 依赖面 = cw_match.session。"""
    op = op_cls.__new__(op_cls)
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
    return op


def _chosen_rows() -> dict:
    """chosen 记录面表行(遭遇/专家/祈愿三案;每行 = op 类 + chosen 字段
    + 真选调用 + 期望值 + fallback 调用集;supply 暂存生命周期独立成案,
    见下)。遭遇臂 = 动作侧发射即写(遭遇扩围批:写端迁
    ``kernel/cw_action_report/pick_encounter.py``,真选/fallback 经 report
    函数直调,payload 槽前置播种模拟入口观察)。"""
    from sr_od.application.currency_war.kernel.cw_action_report.pick_encounter import (
        report_action_pick_encounter_param,
    )
    from sr_od.application.currency_war.kernel.cw_events import EncounterOption
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        EncounterPayload,
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickEncounterParam,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_encounter,
        cw_screen_expert_invite,
        cw_screen_wish_trial,
    )

    opts = [EncounterOption(idx=0, difficulty=1, rewards=['金币×2']),
            EncounterOption(idx=1, difficulty=3, rewards=['随机4费×3'])]
    bonds: list[str | None] = ['仙舟', None, '贝洛伯格', None]
    _sig = ChannelSig(family='logic_action', actor='test', mode='compute')

    def _enc_report(op, idx: int, *, seed: bool) -> None:
        gs = game_state_of(op.ctx.cw_match.session)
        if seed:
            gs.write_logic(gs.encounter, EncounterPayload(options=list(opts)),
                           produced_by='test', sig=_sig)
        report_action_pick_encounter_param(
            gs, CwActionPickEncounterParam(idx=idx), _sig)

    return {
        'encounter': {
            'op_cls': cw_screen_encounter.CwScreenEncounter,
            'field': 'chosen_encounter',
            'pick': lambda op: _enc_report(op, 1, seed=True),
            'expected': (3, '随机4费×3'),
            'fallbacks': [
                lambda op: _enc_report(op, 1, seed=False),   # payload 离屏(观察层失约)
                lambda op: _enc_report(op, 5, seed=True)],   # idx 越界(盲选防御)
        },
        'expert': {
            'op_cls': cw_screen_expert_invite.CwScreenExpertInvite,
            'field': 'chosen_expert',
            'pick': lambda op: op._record_chosen_expert(0, bonds),
            'expected': '仙舟',
            'fallbacks': [
                lambda op: op._record_chosen_expert(-1, bonds),   # 现金为王兜底
                lambda op: op._record_chosen_expert(9, bonds),    # 越界(防御面)
                lambda op: op._record_chosen_expert(1, bonds)],   # 羁绊缺失(防御面)
        },
        'wish': {
            'op_cls': cw_screen_wish_trial.CwScreenWishTrial,
            'field': 'chosen_wish',
            'pick': lambda op: op._record_chosen(['累计刷新10次', '', ''], 0),
            'expected': '累计刷新10次',
            'fallbacks': [
                lambda op: op._record_chosen(None, 0),            # objective 未读到
                lambda op: op._record_chosen(['', '难度3+战斗'], 0),  # 选中槽文本空
                lambda op: op._record_chosen(['累计刷新10次'], 7)],    # 越界
        },
    }


@pytest.mark.parametrize('case_id', list(_chosen_rows()))
def test_chosen_record_face_true_pick_only(case_id: str) -> None:
    """四事件屏 chosen_* 记录面真值表一锁(§3.4.5 余屏写端;三案表驱动
    并一,合并原 test_encounter_chosen_written_on_true_pick_only /
    test_expert_chosen_written_on_card_pick_only /
    test_wish_chosen_written_with_objective_text_only,断言腿逐条保留;
    supply 暂存生命周期独立成案见下):

    - 真选写:值 = 原名口径(遭遇 = (难度档, 奖励文本) / 专家 = 卡羁绊
      原文名 / 祈愿 = objective 原文名),source=logic(单次逻辑写入);
    - fallback(无会话/候选未读到/越界/羁绊缺失/选中槽文本空)不写;
      专家「现金为王」兜底不写——该事实由 ConfirmExpertCash +4 金到账
      登记通道承载,照旧不动;真选守卫照 chosen_tome 式。
    (三审拆半:原 getsource 字符串在场扫描腿删——写端接线在位/落地验真
    后写的调用时点面归 review 与代码规范;本锁辖记录面行为半。)"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    row = _chosen_rows()[case_id]
    sess = StrategySession()
    op = _op_with_session(row['op_cls'], sess)
    row['pick'](op)
    fld = getattr(game_state_of(sess), row['field'])
    assert fld.value == row['expected'], f'{case_id}: 真选值 = 原名口径'
    assert fld.source == 'logic', f'{case_id}: 单次逻辑写入(source=logic)'
    # fallback 帧(全新会话):逐个不写
    sess2 = StrategySession()
    op2 = _op_with_session(row['op_cls'], sess2)
    for fallback in row['fallbacks']:
        fallback(op2)
    assert getattr(game_state_of(sess2), row['field']).value is None, \
        f'{case_id}: fallback 不写'


# (test_supply_chosen_written_from_stash_after_exit_only 删:补给选定
#  中转暂存宿主已随执行层状态类目退役,stash 写法语义消亡;
#  「确认即写 chosen_supply」行为锁迁 test_cw_obs_arch_event_screens_
#  step3.py 驱动真选分支承重。)


# (test_expert_chosen_written_on_card_pick_only /
#  test_wish_chosen_written_with_objective_text_only 已表驱动并入上方
#  test_chosen_record_face_true_pick_only,断言腿零丢失。)
