"""效果账本域测试(机制主题文件):账本桥·板面重写通道 + 节点边界推进。

被测机制(按节):
- **apply_board_rewrite 锚定通道行为**(通道择道单一源 =
  ``cw_game_state.anchor_aware_write``;通道规则「未锚定 → 随机态」,
  语义域 = 容器正本 game_state/fields.md「开局种子底座」节):人力
  重组双臂(种子未闩 → logic_rand / 置闩 → logic)、静默覆盖臂
  (未闩零失配行落 logic_rand_outcome,置闩失配网生效)、回归臂
  (UPGRADE_ALL 零容器写 / 非板面条目零动作 / burst 桥 Field 发放);
- **效果推进段 tick_effect_boundary**(结算真值收口后只剩账本推进/
  刷新发放/异常边界三判据;2026-10-12-abolish-node-ordinal §3.2 起
  生效序位 = (位面, 轮) 元组键):None 守卫 / 推进+到账 / 吞异常;
- **清盘 → 再买 → 前排部署交互**(清盘后规范形空视图不崩,清盘写
  保持单写)。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    BOARD_REWRITE_UPGRADE_ALL,
    ActiveEffectInventory,
    apply_board_rewrite,
    grant_bench_unit_cascade,
    spawn_equip_bench_unit,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    apply_effect_burst_grant,
    consume_defect_sink,
    game_state_of,
    tick_effect_boundary,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')

_SELL_ALL = STRATEGY_EFFECTS['人力重组']


def _seeded_gs() -> GameState:
    """种子容器(经 game_state_of 缓存单例支冷建,与生产局容器同构)。"""
    return game_state_of(StrategySession())


def _u(cid: str, star: int = 1, equips: list[str] | None = None) -> Unit:
    """单位直构(装备跟单位对象)。"""
    return Unit(char_id=cid, star=star, equips=list(equips or []))


def test_sell_all_channel_dual_arm_by_anchor() -> None:
    """人力重组双臂(通道规则「未锚定 → 随机态」):种子容器(未闩)
    SELL_ALL 清空写恰三行 source=logic_rand(未验证推算走随机态,首观察
    静默覆盖);置闩(测试专口直赋)后同路径 source=logic(确定面)。"""
    # 臂 1:种子容器(未闩)→ 清空写走随机态
    gs = _seeded_gs()
    assert gs.deployed.source == 'logic_rand', '前置:冷建含种子底座'
    seq_before = gs.write_seq
    report = apply_board_rewrite(gs, _SELL_ALL)
    assert report is not None
    assert report.cleared_fields == ('deployed', 'bench'), \
        '种子后两门全开(行域合卷 = deployed 单字段),两域各一行清空写'
    assert report.refund_gold == 0 and report.sold_units == 0, \
        '种子空底座无可出售面,退款零'
    assert gs.write_seq - seq_before == 2, '恰好两行清空写'
    assert gs.deployed.source == 'logic_rand'
    assert gs.bench.source == 'logic_rand'
    # 臂 2:置闩后同路径 → 按现语义 write_logic
    gs2 = _seeded_gs()
    gs2.prep_anchored = True
    report2 = apply_board_rewrite(gs2, _SELL_ALL)
    assert report2 is not None
    assert report2.cleared_fields == ('deployed', 'bench')
    assert gs2.deployed.source == 'logic'
    assert gs2.bench.source == 'logic'


def test_sell_all_silent_override_unanchored_mismatch_after_anchor() -> None:
    """静默覆盖臂:未闩清空写(随机态)被观察以不同值覆盖 → 零失配
    三分流行、差异落 logic_rand_outcome(首观察静默覆盖);置闩后同场景
    (确定面清空写)被观察覆盖 → observe_vs_logic_mismatch 缺陷行
    (失配网未盲)。"""
    other_view = BenchView(
        slots=[BenchSlot(kind='unit',
                         unit=Unit(char_id='停云', star=1))]
        + [BenchSlot(kind='empty')] * 8, capacity=9)
    # 未闩臂:随机态清空写 → 观察覆盖静默
    gs = _seeded_gs()
    apply_board_rewrite(gs, _SELL_ALL)
    consume_defect_sink()
    gs.observe(gs.bench, other_view, sig=_SIG_OBS)
    kinds = [r['kind'] for r in consume_defect_sink()]
    assert 'observe_vs_logic_mismatch' not in kinds, '未锚定期首观察零失配行'
    assert 'logic_rand_outcome' in kinds, '随机态差异落 logic_rand_outcome'
    # 闩臂:确定面清空写 → 观察覆盖产真失配行
    gs2 = _seeded_gs()
    gs2.prep_anchored = True
    apply_board_rewrite(gs2, _SELL_ALL)
    consume_defect_sink()
    gs2.observe(gs2.bench, other_view, sig=_SIG_OBS)
    kinds2 = [r['kind'] for r in consume_defect_sink()]
    assert 'observe_vs_logic_mismatch' in kinds2, '锚定后失配网原样生效'


def test_upgrade_all_and_other_bridges_unchanged() -> None:
    """回归臂:全员晋升(UPGRADE_ALL)零容器写不变(替换面随机,报告作
    负写端留证);非板面重写条目过桥零动作;burst 桥(免费刷新剩余次数,
    2026-09-21 Field 化后 = 容器字段 write_logic)正常发放。"""
    gs = _seeded_gs()
    seq_before = gs.write_seq
    report = apply_board_rewrite(gs, STRATEGY_EFFECTS['全员晋升'])
    assert report is not None
    assert report.rewrite == BOARD_REWRITE_UPGRADE_ALL
    assert report.cleared_fields == ()
    assert report.refund_gold == 0 and report.sold_units == 0
    assert report.partial_read is False
    assert gs.write_seq == seq_before, 'UPGRADE_ALL 零容器写(随机面观察收口)'
    # 非板面重写条目 → None 零动作(零 Field 写)
    assert apply_board_rewrite(gs, STRATEGY_EFFECTS['固定理财']) is None
    assert gs.write_seq == seq_before
    # burst 桥:免费刷新剩余次数 Field 登记(2026-09-21 Field 化:效果
    # 账本 int 升格容器字段,桥 write_logic 落一行 Field 写)
    seq_before_burst = gs.write_seq
    apply_effect_burst_grant(gs, STRATEGY_EFFECTS['固定理财'])
    assert gs.free_refresh_left.value == 2, 'None 基 = 0 起算'
    assert gs.free_refresh_left.source == 'logic'
    assert gs.write_seq > seq_before_burst, 'burst 桥落 Field 行'


# ============================================================ 效果推进段(tick_effect_boundary)

def test_none_guard_skips_whole_segment() -> None:
    """判据①:effective None → 整段跳过——在册效果零发放(「未观察不当真
    进节点」守卫,禁虚耗余期/虚累余额;现码 cw_loop 禁令随迁)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_key=(1, 5))
    tick_effect_boundary(gs)
    assert gs.free_refresh_left.value is None, '未观察 = 不发放(零 Field 行)'
    assert gs.node_hist_pos is None


def test_advances_and_grants() -> None:
    """判据②:生效序位推进 → 账本 advanced + 刷新剩余次数 Field 到账。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_key=(1, 5))
    gs.node_hist_pos = (1, 6)
    tick_effect_boundary(gs)
    assert gs.free_refresh_left.value == 2, '每进节点 +2(双手狸活载体)'


def test_segment_swallows_exceptions(monkeypatch) -> None:
    """异常边界:段内失败吞 Exception 记 warning 不上抛(不毒化派生链)。"""

    def _boom(node_key):
        raise RuntimeError('probe')

    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.node_hist_pos = (2, 3)
    monkeypatch.setattr(type(gs.effects), 'advance_node', _boom)
    tick_effect_boundary(gs)   # 不上抛即判据


# ============================================================ 清盘 → 再买 → 前排部署交互

_M31_SIG_LOGIC = ChannelSig(family='logic_action', actor='MandateV1Strategy',
                            mode='compute')


def test_board_rewrite_clear_then_front_deploy_no_crash() -> None:
    """清盘 → 再买 → 前排部署不崩(交互测试):EffectLedgerBridge 全场出售
    清空后视图 = 规范形空视图(front_slots 定长 4),后续 deploy_move
    前排直址落位不 IndexError;清盘写本身保持单写。

    测试卫生:未锚定清盘走 write_logic_rand,下方 bench 再观察覆盖
    异值 → 一行 logic_rand_outcome 入进程级缺陷缓冲(预期内,非安灯)
    ——用例末尾 consume_defect_sink 排水,防跨用例顺序依赖红。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=_u('停云'))]
        + [BenchSlot(kind='empty')] * (BENCH_CAPACITY_DEFAULT - 1),
        capacity=BENCH_CAPACITY_DEFAULT), sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(
        front_slots=[_u('银枝'), None, None, None],
        back_slots=[_u('刃'), None, None, None, None, None]), sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)

    report = apply_board_rewrite(gs, STRATEGY_EFFECTS['人力重组'])
    assert report is not None and 'deployed' in report.cleared_fields

    view = gs.deployed.value
    assert len(view.front_slots) == 4, '清盘后 front_slots 恒定长 4(规范形不变量)'
    assert all(u is None for u in view.front_slots)
    assert all(u is None for u in view.back_slots), '两排全空(语义清盘)'

    # 清盘 → 再买(落席)→ 前排部署:不崩 + 落位正确。
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=_u('甲'))]
        + [BenchSlot(kind='empty')] * 8,
        capacity=BENCH_CAPACITY_DEFAULT), sig=_SIG_OBS)
    report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front',
                                    to_slot=4, faction=''),
        _M31_SIG_LOGIC)
    assert gs.deployed.value.front_slots[3].char_id == '甲', \
        '前排 4 号直址落位(清盘后规范形视图上不崩)'
    consume_defect_sink()   # 排水:logic_rand_outcome 行不跨用例泄漏


# ============================================================ 合并升星触发发放腿
# (T-26 量子同频契约:grant_bench_unit_cascade 采集发火 + spawn_equip_
# bench_unit 拷贝臂反向锁;设计 = 该迭代 designs/T-26-liangzi-tongpin-
# qiyue.md §2.4 条 2/§4.6 同构腿/§4.8。)

_POOL = ('符玄', '希儿')


def _merge_contract_gs(bench_entries: list[Unit]) -> GameState:
    """量子同频契约激活 + bench 按参组装(直构容器,观察种子)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='unit', unit=u)
                                     for u in bench_entries]
    slots += [BenchSlot(kind='empty')] * (BENCH_CAPACITY_DEFAULT
                                          - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_SIG_OBS)
    gs.observe(gs.active_env, '量子同频契约', sig=_SIG_OBS)
    return gs


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_grant_bench_unit_cascade_fires_merge_grant(
        seeded_merge_provider) -> None:
    """补给单位腿发火时序锁(T-26 设计 §4.6 同构腿):2×1★花火在席,
    grant_bench_unit_cascade('花火') 补齐三连 → 级联合并 2★ 产物,级联
    写毕后发火 → bench 终态 = 产物 + 发放角色并存(发放名 = 注入槽
    种子现算;pick_supply/装备获得后果两消费面同点覆盖)。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = _merge_contract_gs([_u('花火'), _u('花火')])
    result = grant_bench_unit_cascade(gs, '花火', 1)
    assert result.placed and result.merge_steps == 1, \
        f'入席 + 一级合并: {result}'
    assert _bench_units(gs) == [('花火', 2), (expected, 1)], \
        f'合并产物 + 发放角色并存: {_bench_units(gs)}'


def test_spawn_equip_bench_unit_no_facts_no_grant(
        seeded_merge_provider) -> None:
    """拷贝臂反向锁(T-26 设计 §4.8):银狼族单位经 spawn_equip_bench_unit
    入席(数据拷贝仪计数臂腿,直写首空槽无级联无事实采集)→ 花火三连
    进度不被消费、零合并零发放——「无漏发靠穿戴门」前提的回归面
    (YINLANG_WEAR_ALLOWLIST 扩圈时本锁与披露 6 共同构成最短证伪路径)。"""
    gs = _merge_contract_gs([_u('花火'), _u('花火')])
    seq_before = gs.write_seq
    placed = spawn_equip_bench_unit(gs, '银狼', 1, 0)
    assert placed is True, '拷贝臂腿入席'
    assert _bench_units(gs) == [('花火', 1), ('花火', 1), ('银狼', 1)], \
        '直写落位:无级联合并(花火仍 2 只)、无发放角色'
    assert gs.write_seq - seq_before == 1, '恰一行入席写,零发放腿'


@pytest.fixture
def seeded_merge_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子;本模块发放腿场景下防真随机漂移),
    必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(20261016))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


# ============================================================ 利息累计账
# (T-27 公司契约条件腿,设计 = 迭代设计稿 T-27-gongsi-qiyue §2.2 + §4.2;
# 宿主先例 = refresh 两计数 2026-09-18 用户裁定「计数住效果账本」。)


def test_record_interest_earned_accumulates_and_rejects_negative() -> None:
    """利息累计账单口(record_interest_earned,T-27 设计 §4.2):多笔
    累加单调递增;0 合法(息 0 轮照常过单口,保持「每收入刻必过单口」
    写端纪律);负数拒收 raise(单调累计账无递减语义,
    bump_equip_progress 同款防线)。"""
    inv = ActiveEffectInventory()
    assert inv.interest_earned == 0, '开局零基线'
    inv.record_interest_earned(5)
    inv.record_interest_earned(3)
    inv.record_interest_earned(0)
    assert inv.interest_earned == 8, '多笔累加(含 0 增量)'
    with pytest.raises(ValueError, match='非负'):
        inv.record_interest_earned(-1)
    assert inv.interest_earned == 8, '拒收后账面不变'


def test_record_ore_open_accumulates_and_rejects_nonpositive() -> None:
    """晶矿开启计数单口(record_ore_open,T-29 设计 §2.2 + §4 锁 2):
    多笔累加单调递增(批内开成点数一次入账);n=0/负数炸(单调计数器
    无递减语义,bump_equip_progress 同款防线),拒收后账面不变;与
    refresh 双计数隔离(同族直挂计数器互不串账)。"""
    inv = ActiveEffectInventory()
    assert inv.ore_open_total == 0, '开局零基线'
    inv.record_ore_open(2)
    inv.record_ore_open(1)
    assert inv.ore_open_total == 3, '多笔累加'
    for bad in (0, -1):
        with pytest.raises(ValueError, match='须为正数'):
            inv.record_ore_open(bad)
    assert inv.ore_open_total == 3, '拒收后账面不变'
    # 与 refresh 隔离(计数载体先例 refresh_total/paid 互不串账)
    assert inv.refresh_total == 0 and inv.refresh_paid == 0, \
        '晶矿开启入账零串账 refresh'
    inv.record_refresh(free=False)
    assert inv.ore_open_total == 3, '刷新入账零串账晶矿开启'


# ============================================================ 实例号保真(T-30)


def test_worn_transform_keeps_uid_and_guard_still_blocks() -> None:
    """特权赋予卡换装保 uid(T-30 设计 §4 锁 10,V2-1 修法回归锁):被锁
    实例(uid=1)经 transform_worn_equip_to_privilege 同实体变换后 uid
    保持(伪 replace 手动新构造曾清零 uid → sim 守卫提前放行),守卫
    仍拦其直部署。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        transform_worn_equip_to_privilege,
    )
    from sr_od.application.currency_war.kernel.cw_env_grants import (
        deploy_lock_block_reason,
    )
    _WORN = '遗器耦合器'
    target = Unit(char_id='流萤', star=1, equips=[_WORN], uid=1)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=target)] + \
        [BenchSlot(kind='empty')] * 8
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    out = transform_worn_equip_to_privilege(gs, target, _WORN)
    assert out == _WORN + '·特权', '特权名返回(后缀映射)'
    replaced = [s.unit for s in gs.bench.value.slots
                if s is not None and s.kind == 'unit' and s.unit is not None]
    assert replaced[0].equips == [_WORN + '·特权'], '装备已变换'
    assert replaced[0].uid == 1, '实例号随行(同实体变换)'
    # 守卫仍拦(锁记录在册 + 生效序位 < 解锁序位)
    gs.observe(gs.node_pos, (1, 7), sig=_SIG_OBS)
    gs.write_logic(gs.env_grant_deploy_locks, (('流萤', 1, (1, 9)),),
                   produced_by='test-seed',
                   sig=ChannelSig(family='logic_action', actor='test-seed',
                                  mode='compute'))
    assert deploy_lock_block_reason(gs, replaced[0]) == \
        'deploy_locked:流萤#uid1#unlock1-9', '换装后守卫仍拦'


# ============================================================ 条件形态专家触发
# (T-42 特邀专家:银狼,设计 = 迭代 2026-09-23-invest-effects-calc
# designs/T-42-teyao-zhuanjia-yinlang.md §4 锁 4:平行桥渠道——入席 +
# 级联 + 触发发放腿全毕后判据一次,桥尾追加;数据拷贝仪Max 确定性通道
# 送 1★银狼LV.999 即现役可达获得。)

_ENV_YINLANG = '特邀专家:银狼'


def _expert_env_gs(bench_entries: list[Unit]) -> GameState:
    """特邀专家:银狼局容器(bench 按参组装 + active_env 观察种子)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [BenchSlot(kind='unit', unit=u)
                                     for u in bench_entries]
    slots += [BenchSlot(kind='empty')] * (BENCH_CAPACITY_DEFAULT
                                          - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_SIG_OBS)
    gs.observe(gs.active_env, _ENV_YINLANG, sig=_SIG_OBS)
    return gs


def test_equip_consequence_lv999_unlocks_expert() -> None:
    """装备获得后果确定性通道(设计 §4 锁 4 条 1):数据拷贝仪Max →
    1★银狼LV.999 入席(获得事实)+ 桥尾判据解锁银狼入商店;解锁 write
    行 evidence = 入席 evidence 族后缀(获得 provenance 可辨)。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        apply_equip_acquire_consequence,
    )
    gs = _expert_env_gs([])
    report = apply_equip_acquire_consequence(gs, '数据拷贝仪Max')
    assert report.performed and report.granted == '银狼LV.999', \
        f'银狼LV.999 入席: {report}'
    assert _bench_units(gs) == [('银狼LV.999', 1)], '获得事实入席'
    assert gs.unlocked_experts.value == ('银狼',), '桥尾判据解锁'
    assert gs.unlocked_experts.evidence == 'equip_acquire#expert_unlock', \
        'evidence 族后缀(入席 evidence 派生)'


def test_grant_bench_unit_cascade_lv999_unlocks_expert() -> None:
    """桥直调(设计 §4 锁 4 条 2):grant_bench_unit_cascade('银狼LV.999')
    → 入席 + 解锁(桥尾判据与后果通道同点,任意发放面一律承接)。"""
    gs = _expert_env_gs([])
    result = grant_bench_unit_cascade(gs, '银狼LV.999', 1)
    assert result.placed, '入席成功'
    assert _bench_units(gs) == [('银狼LV.999', 1)]
    assert gs.unlocked_experts.value == ('银狼',), '解锁写入'


def test_bridge_reject_no_trigger() -> None:
    """席满拒落不触发(设计 §4 锁 4 条 3):bench 满(无空槽)→
    placed=False 早退,早退路径不经桥尾判据 → 零解锁写。"""
    full_bench = [_u(n) for n in ('希儿', '符玄', '花火', '停云', '刃',
                                  '杰帕德', '娜塔莎', '丹恒', '三月七')]
    gs = _expert_env_gs(full_bench)
    seq_before = gs.write_seq
    result = grant_bench_unit_cascade(gs, '银狼LV.999', 1)
    assert result.placed is False and result.detail == 'bench_full', \
        f'席满拒落: {result}'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写(早退不经判据)'
    assert gs.write_seq == seq_before, '拒落零写'


# ============================================================ 占位注记渲染器
# (G 组摘要 = GiftGrant 发放形状字段全量渲染,10 字段中 9 渲染 +
# sell_value_note 显式排除;正本 = game_state/fields.md §5.2 效果缺口与
# 载体登记,语义 = 「概念股族模式卡登记约定」——在册裸「GiftGrant」
# 标记债(非渲染字段条目只露裸标记)同批清偿,裸标记回归 = 红。
# 族展开第二实例 = 燃血概念股 / 第三实例 = 能量概念股 / 第四实例 = 列车
# 同行概念股 / 第五实例 = 银河学者概念股 / 第六实例 = 贝洛伯格概念股 /
# 第七实例 = 星间旅人概念股 / 第八实例 = 仙舟概念股
# (概念股族展开卡登记约定):通用渲染器
# 对新登记自动生效零渲染器改动,cases 既有条目段断言不动 = 既有 notes
# 逐字不变回归面。)


def test_portal_placeholder_grant_shape_full_fields() -> None:
    """占位注记全字段段锁(fields.md §5.2 效果缺口与载体登记:渲染
    登记形状静态值,不渲染运行期采样身份):在册代表卡逐段断言——
    追击概念股 随机[阵营追击@1星]+随机装备[简易](阵营轴首例,渲染
    格 = 阵营<名>@<星>星)/ 燃血概念股 随机[阵营燃血@1星]+随机装备[简易]
    (族展开第二实例,概念股族展开卡登记约定——登记行零渲染器改动,
    通用渲染器自动生效)/ 能量概念股 随机[阵营能量@1星]+随机装备[简易]
    (族展开第三实例,同上自动生效)/ 列车同行概念股 随机[阵营列车同行
    @1星]+随机装备[简易](族展开第四实例,同上自动生效)/ 银河学者概念股
    随机[阵营银河学者@1星]+随机装备[简易](族展开第五实例,同上自动生效)/
    贝洛伯格概念股 随机[阵营贝洛伯格@1星]+随机装备[简易](族展开第六
    实例,同上自动生效)/ 星间旅人概念股 随机[阵营星间旅人@1星]+随机装备
    [简易](族展开第七实例,同上自动生效)/ 仙舟概念股 随机[阵营仙舟@1星]
    +随机装备[简易](族展开第八实例,同上自动生效)/
    火药味 道具段
    (数量 = 元素重复逐元素)/ 红钻贵族 即时装备段 / 人才引进 随机[4费@1星]
    段(费用轴渲染格)/ 特权阶级 定时道具段(件@节点键)/ 人才储备 开局
    替换段——任一卡退化为裸「GiftGrant」标记 = 本锁红(裸标记债回归)。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        _portal_placeholder_spec,
    )
    cases = {
        '追击概念股': ('随机[阵营追击@1星]', '随机装备[简易]'),
        '燃血概念股': ('随机[阵营燃血@1星]', '随机装备[简易]'),
        '能量概念股': ('随机[阵营能量@1星]', '随机装备[简易]'),
        '列车同行概念股': ('随机[阵营列车同行@1星]', '随机装备[简易]'),
        '银河学者概念股': ('随机[阵营银河学者@1星]', '随机装备[简易]'),
        '贝洛伯格概念股': ('随机[阵营贝洛伯格@1星]', '随机装备[简易]'),
        '星间旅人概念股': ('随机[阵营星间旅人@1星]', '随机装备[简易]'),
        '仙舟概念股': ('随机[阵营仙舟@1星]', '随机装备[简易]'),
        '火药味': ('道具[简易武装箱、简易武装箱]',),
        '红钻贵族': ('即时装备[红钻]', '道具[简易武装箱]'),
        '人才引进': ('随机[4费@1星]',),
        '特权阶级': ('定时道具[特权武装箱@2-1]',),
        '人才储备': ('随机[3费@1星;3费@1星;3费@1星]', '开局替换'),
    }
    for env_name, segments in cases.items():
        spec = _portal_placeholder_spec(env_name)
        assert spec is not None
        assert '未入模占位' in spec.notes, f'{env_name} 占位形保留'
        for seg in segments:
            assert seg in spec.notes, \
                f'{env_name} notes 缺段 {seg!r}: {spec.notes}'
        # 裸标记回归:段列表必须随渲染字段出现(登记形状可见)
        body = spec.notes.split('GiftGrant', 1)[1]
        assert body.strip(' ;'), f'{env_name} 裸 GiftGrant 标记(段缺失)'
