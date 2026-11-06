"""轮回不止(id 332201)行为锁(镜像 src = cw_gain_effects.py 的
``_STRATEGY_CHAR_GRANTS`` + ``_make_char_grant_effect`` PICK 推导 +
cw_investments.py 的 ``StrategyPlaneStartCharGrant``/``STRATEGY_PLANE_
START_CHAR_GRANTS`` 位面开始角色子形专表 + cw_gain_chain.py 的
``check_strategy_plane_start_grants`` 角色分支;先例 = 同目录
test_strategy_char_grant.py 具名角色发放族 + test_strategy_zhongshen_
xuexi.py 位面开始通道 item 形姊妹)。

测试面依据 = 卡面官方原文(cw_invest_data.PLAZA_AUGMENTS id 332201:
「获得【白厄】和一件【轮回者】装备。进入第二/三位面时，再获得一次。
本局游戏结束时，【白厄】携带着装备成为新的【轮回者】。若游戏结束时
【白厄】不在队伍中，【轮回者】的装备变为初始状态。」)与在码登记裁定:

- 效果条目1a:「获得【白厄】」具名直读行骑厂(表 +1 行,PICK 行由生成式注册
  段自动派生),确定发放 rand=False,星级 1 = roster 单位先验;
  效果串 ``char_grant:白厄(placed=…,merge=…,uid=…)`` = 工厂现值形;
- 效果条目2:「进入第二/三位面时，再获得一次」= 位面 2/3 的位面开始窗
  (2-1/3-1)各发放一次(用户裁定读法);中途拿卡不补发 = 用户裁定
  (取卡窗恒 r∈{2,3},与 r==1 位面开始窗零交叠,零补发腿);零 done 一次性标志位
  零 GameState 新域(静态谓词天然单调,窗幂等守卫承担单次);效果串
  ``plane_start_grant:白厄(1★)``(与 item 形同前缀同括注形),evidence
  前缀 ``plane_start_char_grant:p<位面>`` 分域;角色分支零发号(uid
  消费域 = 上场锁/离场队列,白厄两缺,同函数姊妹分支同窗无号);
- 「一件【轮回者】装备」零建模 = cw_investments.STRATEGY_REINCARNATOR_
  UNMODELED 披露键申报(四面零数据);效果条目3/效果条目4 局终域零建模同键覆盖;
- 构建校验 = 漂移哨三哨(孤儿键/id 双匹配/char 词表),治理口径:
  笔误类哨不落 import,两表一致性对账归表域测试(镜像一致性锁)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_plane_start_grants,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
    STRATEGY_PLANE_START_CHAR_GRANTS,
    StrategyPlaneStartCharGrant,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


def _make_gs(*, bench: list[tuple[str, int]] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;bench 直构槽位 (角色名, 星)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    return gs


def test_pick_leg_grants_baie() -> None:
    """效果条目1a 主锁:on_strategy_gained 直构(rand=False)→ 备战追加恰 1 只
    1★ 白厄、效果串 = 工厂现值形 ``char_grant:白厄(placed=True,merge=0,
    uid=1)``(单发零升星;uid = PICK 具名角色发放族发号纪律,名单全部键
    非本卡特例);落位写 evidence = pick_invest_char_grant#place。"""
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, '轮回不止', rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:白厄(placed=True,merge=0,uid=1)',), \
        f'单发步串: {effects!r}'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [('白厄', 1)], \
        '备战追加恰 1 只 1★ 白厄(星级 1 = roster 单位先验)'
    assert all(u.uid is not None for u in units), \
        '发放刻赋实例号(具名角色发放族名单全部键发号纪律)'


def test_pick_leg_grants_baie_on_occupied_bench() -> None:
    """效果条目1a 非空备战席回归:白厄 ≠ 既有单位同名同星,落位零合成级联
    (互异填席隔离升星判断面,链现役语义本表不特判)。"""
    gs = _make_gs(bench=[('希儿', 1)])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, '轮回不止', rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:白厄(placed=True,merge=0,uid=1)',), \
        f'单发步串: {effects!r}'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [
        ('希儿', 1), ('白厄', 1)], '追加落位零合成'


def test_zero_effect_registration() -> None:
    """零效果锁:STRATEGY_EFFECTS 恒空(卡面经济/战力条目零登记,防未来
    误登记)+ 商店停机钩子名单不含本卡(本卡零商店改写/计数采集面;
    名单访问形 = 类限定 ClassVar)。"""
    assert '轮回不止' not in STRATEGY_EFFECTS, 'STRATEGY_EFFECTS 零登记'
    assert '轮回不止' not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '停机钩子名单零成员'


@pytest.mark.parametrize('leg_table', [
    pytest.param('items_immediate', id='items-leg-empty'),
    pytest.param('chars_conditional', id='conditional-leg-empty'),
])
def test_registration_legs_shape(leg_table: str) -> None:
    """登记面腿形锁:STRATEGY_GRANTS 条目 = chars_immediate ('白厄',) 一条效果条目,
    条件集/道具集恒空(重复腿不入条件集,登记裁定在码;轮回者装备腿零
    建模不入 equips——equip 字段校验闸天然拒绝非注册装备名,登记面
    自洽非遗漏)。"""
    grant = STRATEGY_GRANTS['轮回不止']
    expected = {'items_immediate': (), 'chars_conditional': ()}[leg_table]
    assert getattr(grant, leg_table) == expected, f'{leg_table} 恒空'


# ============================================================ 效果条目2 表构建锁


def test_plane_start_char_table_registration() -> None:
    """表锁(锁 1 前半):现值单条目四字段逐位(用户裁定 planes=(2, 3)
    「第二/三位面」直读 + char 白厄 + star 1★ 先验 + id 双匹配随 import
    期孤儿/双查哨承证)。"""
    assert list(STRATEGY_PLANE_START_CHAR_GRANTS) == ['轮回不止'], \
        f'现值单条目: {list(STRATEGY_PLANE_START_CHAR_GRANTS)!r}'
    grant = STRATEGY_PLANE_START_CHAR_GRANTS['轮回不止']
    assert grant.id == '332201', f'id 漂移: {grant.id!r}'
    assert grant.planes == (2, 3), f'planes 漂移: {grant.planes!r}'
    assert grant.char == '白厄', f'char 漂移: {grant.char!r}'
    assert grant.star == 1, f'star 漂移: {grant.star!r}'


def test_plane_start_char_table_mirror_consistency() -> None:
    """镜像一致性锁(锁 6,治理口径:char 与同卡 STRATEGY_GRANTS 角色集
    一致性不做 import 哨,降测试层,箱条目一致性测试同形):注册全集
    逐条 char ∈ 同卡 chars_immediate ∪ chars_conditional——「再获得一次」
    = 对效果条目1 整组的重复,发放对象漂移(改角色/漏登记即时腿)在窗口行为
    断言不可见,唯此锁暴露。"""
    for name, grant in STRATEGY_PLANE_START_CHAR_GRANTS.items():
        registered = (set(STRATEGY_GRANTS[name].chars_immediate)
                      | set(STRATEGY_GRANTS[name].chars_conditional))
        assert grant.char in registered, \
            f'{name} 角色子形与登记表角色集漂移: {grant.char!r}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨,负验注入):键不在策略注册表 → ValueError
    (import 即炸语义,直调校验函数锁同款行为)。"""
    from sr_od.application.currency_war.kernel import cw_investments
    monkeypatch.setitem(
        cw_investments.STRATEGY_PLANE_START_CHAR_GRANTS, '不存在的卡',
        StrategyPlaneStartCharGrant(id='999999', planes=(2, 3),
                                    char='白厄', star=1))
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_strategy_plane_start_char_grants()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """构建校验②(id 双匹配哨,负验注入):登记 id ≠ base 溯源 id →
    ValueError(版本改名且 id 仍在的漂移也炸)。"""
    from sr_od.application.currency_war.kernel import cw_investments
    monkeypatch.setitem(
        cw_investments.STRATEGY_PLANE_START_CHAR_GRANTS, '轮回不止',
        StrategyPlaneStartCharGrant(id='332999', planes=(2, 3),
                                    char='白厄', star=1))
    with pytest.raises(ValueError, match='id 漂移'):
        cw_investments._validate_strategy_plane_start_char_grants()


def test_validator_char_unknown_raises(monkeypatch) -> None:
    """构建校验③(角色词表漂移哨,负验注入):char ∉ CHARACTER_ROSTER
    → ValueError(游戏角色词表改名/移除可独立触发)。"""
    from sr_od.application.currency_war.kernel import cw_investments
    monkeypatch.setitem(
        cw_investments.STRATEGY_PLANE_START_CHAR_GRANTS, '轮回不止',
        StrategyPlaneStartCharGrant(id='332201', planes=(2, 3),
                                    char='不存在的角色', star=1))
    with pytest.raises(ValueError, match='发放角色漂移'):
        cw_investments._validate_strategy_plane_start_char_grants()


# ============================================================ 效果条目2 行为锁


def test_plane_p2_p3_windows_grant() -> None:
    """行为锁(锁 2 前半):持卡局 P1→P2 位面开始窗(2,1)发放 1 只 1★
    白厄,效果串恰 1 条定谳形;P2→P3 窗(3,1)第二次同验,终 2 只零合并
    (同名同星凑三触发链现役合成,2 只不触发)。"""
    gs = _make_gs(bench=[])
    gs.observe(gs.active_strategies, ['轮回不止'], sig=_SIG_OBS)
    seq = check_strategy_plane_start_grants(gs, node_pos=(2, 1), sig=_LSIG)
    assert seq == ['plane_start_grant:白厄(1★)'], f'效果串: {seq!r}'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [('白厄', 1)], \
        'P2 开始入席 1★ 白厄'
    assert gs.bench.evidence == 'plane_start_char_grant:p2#place', \
        '写入端 evidence 分域(plane_start_char_grant:p<位面>)'
    seq3 = check_strategy_plane_start_grants(gs, node_pos=(3, 1), sig=_LSIG)
    assert seq3 == ['plane_start_grant:白厄(1★)'], f'P3 效果串: {seq3!r}'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [
        ('白厄', 1), ('白厄', 1)], 'P3 开始第二次发放,2 只零合并'


def test_plane_1_window_zero_grant() -> None:
    """行为锁(锁 2 负验一):P1 内位面首窗(1,1)零发放——位面 1 不在
    planes 选择性子集(卡面「第二/三位面」词面),零写。"""
    gs = _make_gs(bench=[])
    gs.observe(gs.active_strategies, ['轮回不止'], sig=_SIG_OBS)
    seq_before = gs.write_seq
    seq = check_strategy_plane_start_grants(gs, node_pos=(1, 1), sig=_LSIG)
    assert seq == [], f'P1 首窗应零条目: {seq!r}'
    assert gs.write_seq == seq_before, 'P1 首窗零写'


def test_not_held_zero_grant() -> None:
    """行为锁(锁 2 负验二):未持卡零发放(持卡谓词单边,零写)。"""
    gs = _make_gs(bench=[])
    seq_before = gs.write_seq
    seq = check_strategy_plane_start_grants(gs, node_pos=(2, 1), sig=_LSIG)
    assert seq == [], f'未持卡应零条目: {seq!r}'
    assert gs.write_seq == seq_before, '未持卡零写'


def test_mid_run_pick_no_refire() -> None:
    """行为锁(锁 2 后半,(2,2) 拿卡局,中途拿卡不补发 = 用户裁定):
    拿卡发生在 P2r2 → P2 位面开始窗已过(持卡谓词在 (2,1) 为假 = 零
    发放,结构性无补发腿);拿卡后 P2r2 窗(r==2)零发放;P3 开始窗
    (3,1)发 1 只。本锁只验效果条目2 切片(即时腿不经 on_strategy_gained,
    不在本锁执行);「终局共 2 只零合并」全貌由双窗行为锁(恰 2×1★
    共存零合并)与效果条目1a 单发锁分证。"""
    gs = _make_gs(bench=[])
    # P2 位面开始窗:卡未持(取卡在 P2r2)→ 零发放
    seq = check_strategy_plane_start_grants(gs, node_pos=(2, 1), sig=_LSIG)
    assert seq == [], f'拿卡前 P2 开始应零条目: {seq!r}'
    # P2r2 拿卡(即时腿走 on_strategy_gained,与本锁无涉;此处只登记持卡)
    gs.observe(gs.active_strategies, ['轮回不止'], sig=_SIG_OBS)
    seq_r2 = check_strategy_plane_start_grants(gs, node_pos=(2, 2),
                                               sig=_LSIG)
    assert seq_r2 == [], f'P2r2 窗应零条目(不补发): {seq_r2!r}'
    # P3 位面开始窗:选择性子集内首次到窗 → 发 1 只
    seq_p3 = check_strategy_plane_start_grants(gs, node_pos=(3, 1),
                                               sig=_LSIG)
    assert seq_p3 == ['plane_start_grant:白厄(1★)'], f'P3 效果串: {seq_p3!r}'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [('白厄', 1)]


def test_merge_cascade_third_copy_star_up() -> None:
    """级联记账锁(锁 3):预置 2×1★ 白厄(均置备战栏,落点走「全备战栏
    → 最左」支)→ 效果条目2 位面开始窗发放第 3 只 → 到席瞬间 3 合 1 合成
    2★(获得链现役级联,事实面 = 容器终态断言);落点 = 全备战栏最左
    (载体槽位 = 0)。"""
    gs = _make_gs(bench=[('白厄', 1), ('白厄', 1)])
    gs.observe(gs.active_strategies, ['轮回不止'], sig=_SIG_OBS)
    seq = check_strategy_plane_start_grants(gs, node_pos=(2, 1), sig=_LSIG)
    assert seq == ['plane_start_grant:白厄(1★)'], \
        f'效果串恒 1 条(发放事实与合成级联解耦): {seq!r}'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [('白厄', 2)], \
        '三只并成 1×2★(到席瞬间合成)'
    slots = gs.bench.value.slots
    carrier = slots[0]
    assert (carrier is not None and carrier.kind == 'unit'
            and carrier.unit is not None
            and carrier.unit.char_id == '白厄'
            and carrier.unit.star == 2), '落点 = 全备战栏最左(槽位 0)'
