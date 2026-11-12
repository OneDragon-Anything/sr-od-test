"""on_env_gained 概念股族(狼狩概念股/昼之半神概念股)发放分支测试(镜像 src =
kernel/cw_gain_chain.py 的被测函数 on_env_gained;概念股族段测试原落位
父目录 test_on_env_gained.py 已超 800 行追加冻结线禁追加,新锁按被测
方法拆目录规范落位本目录,同函数兄弟测试 = 父目录 test_on_env_gained.py
〔超限文件禁追加,函数 helper import 复用不改〕;helper 复用先例 =
sim/cw_sim_backend/test_env_pick_grant_sim_chain.py 自超限
test_sim_backend.py import 形态;fixture 不可跨文件 import,rows_sink
自带同名同语义副本,先例 = 同先例文件的 _isolate_defect_buffer)。

测试面依据 = gain-chain.md §3 随机支/随机装备支段 + fields.md §5.2
效果缺口与载体登记,语义 = 「概念股族展开卡登记约定」(狼狩概念股
id 1009 族内第九实例/昼之半神概念股 id 1010 第十实例/夜之半神概念股
id 1011 第十一实例/击破概念股 id 1012 第十二实例/群攻概念股 id 1013
第十三实例/减益概念股 id 1014 第十四实例/战技点概念股 id 1016 第十五
实例〔族收官〕,与父目录追击/燃血分支锁同构仅值异):
- **阵营支发放分支**:固定 seed 直构 → bench 追加 1 张 1★ 且名 ∈
  grant_char_pool 现算集(牌库时点池 = 规格域 ∩ 当时牌库,未解锁专家
  貊泽剔除,6 名)且 ∉ EXPERT_CHARS;效果串 ``env_gift_random:<名>@1star``
  (星级 = spec.star 先验);
- **随机装备入账分支非绑定态**:概念股非 ENV_BOSS_GRANTS 成员 → 效果串
  ``env_equip_random:<名>`` 前缀、env_grants_done 零 star_grant# 绑定键。
"""
from __future__ import annotations

import random

import pytest
from test.sr_od.application.currency_war.kernel.cw_gain_chain.test_on_env_gained import (
    _SIG,
    _bench_units,
    _make_gs_with_equips,
)

from sr_od.application.currency_war.kernel.cw_gain_chain import on_env_gained
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_GIFTS,
)


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾;
    fixture 不可跨文件 import,自带同名同语义副本,先例 = 父目录
    test_on_env_gained.py 同族 fixture)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


_ENV = '狼狩概念股'
_ENV_10 = '昼之半神概念股'
_ENV_11 = '夜之半神概念股'
_ENV_12 = '击破概念股'
_ENV_13 = '群攻概念股'
_ENV_14 = '减益概念股'
_ENV_15 = '战技点概念股'


def test_langshou_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """狼狩域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库时点
    池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子 rng
    直构 → bench 追加 1 张 1★ 且名 ∈ grant_char_pool 现算集(grant_char_
    pool 阵营 spec = 规格域 ∩ 当时牌库,未解锁专家貊泽剔除——注册表派生
    不手抄)且 ∉ EXPERT_CHARS(种子落点选点 = 牌库时点过滤后池现算,专家
    不入池,过滤语义钉死);效果串 ``env_gift_random:<名>@1star``(星级 =
    spec.star 先验);锚定状态容器 + 采样子链 rand=True → 写照常生效且不进
    失配网(随机态语义,首观察静默覆盖)。期望名从同 seed 现算(单一来源,
    不手抄)。"""
    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_ENV].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert expected in pool and expected not in EXPERT_CHARS, \
        '发放名 ∈ 牌库时点池且非专家(未解锁专家剔除生效)'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_langshou_concept_stock_random_equip_leg_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定;概念股族展开卡登记约定):狼狩概念股(非成员)随机装备入账分支
    → 效果串 ``env_equip_random:<名>`` 前缀(与绑定态 ``env_star_grant:``
    分域)、env_grants_done 零 star_grant# 绑定键(非成员零绑定写,治
    「无条件绑定等第二个消费者」缺陷);装备照常入栏且名 ∈ 类别池现算集
    (equips_by_category('简易') 注册表派生,不手抄)。两条分支期望值从同
    seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与生产消费序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_ENV].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_zhouzhibanshen_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """昼之半神域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库
    时点池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子
    rng 直构 → bench 追加 1 张 1★ 且名 ∈ grant_char_pool 现算集(本域
    6 名 is_expert 全空 = 全员非专家,牌库时点过滤恒等零收窄——注册表
    派生不手抄,无 T-56 型种子避让约束);效果串 ``env_gift_random:<名>
    @1star``(星级 = spec.star 先验);锚定状态容器 + 采样子链 rand=True →
    写照常生效且不进失配网(随机态语义,首观察静默覆盖)。期望名从同
    seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_ENV_10].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _ENV_10, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert expected in pool, \
        '发放名 ∈ 牌库时点池(本域无专家,过滤恒等)'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_zhouzhibanshen_concept_stock_random_equip_leg_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定;概念股族展开卡登记约定):昼之半神概念股(非成员)随机
    装备入账分支 → 效果串 ``env_equip_random:<名>`` 前缀(与绑定态
    ``env_star_grant:`` 分域)、env_grants_done 零 star_grant# 绑定键
    (非成员零绑定写,治「无条件绑定等第二个消费者」缺陷);装备照常入栏
    且名 ∈ 类别池现算集(equips_by_category('简易') 注册表派生,不手抄;
    装备先验「昼神送轮滑鞋」随 fixed_hypothesis 家族键已登记,零卡级申报)。
    两条分支期望值从同 seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与生产消费
    序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_ENV_10].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _ENV_10, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_yezhibanshen_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """夜之半神域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库
    时点池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子
    rng 直构 → bench 追加 1 张 1★ 且名 ∈ grant_char_pool 现算集(本域
    7 名 is_expert 全空 = 全员非专家,牌库时点过滤恒等零收窄——注册表
    派生不手抄,无 T-56 型种子避让约束);效果串 ``env_gift_random:<名>
    @1star``(星级 = spec.star 先验);锚定状态容器 + 采样子链 rand=True →
    写照常生效且不进失配网(随机态语义,首观察静默覆盖)。期望名从同
    seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_ENV_11].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _ENV_11, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert expected in pool, \
        '发放名 ∈ 牌库时点池(本域无专家,过滤恒等)'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_yezhibanshen_concept_stock_random_equip_leg_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定;概念股族展开卡登记约定):夜之半神概念股(非成员)随机
    装备入账分支 → 效果串 ``env_equip_random:<名>`` 前缀(与绑定态
    ``env_star_grant:`` 分域)、env_grants_done 零 star_grant# 绑定键
    (非成员零绑定写,治「无条件绑定等第二个消费者」缺陷);装备照常入栏
    且名 ∈ 类别池现算集(equips_by_category('简易') 注册表派生,不手抄;
    economy.md 四卡线索名单不含夜之半神 = 装备身份零先验,均匀 v0 + 按
    卡固定假说待校准随 fixed_hypothesis 家族键已登记,零卡级申报)。两条分支
    期望值从同 seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与生产消费
    序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_ENV_11].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _ENV_11, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_jipo_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """击破域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库时点
    池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子 rng
    直构 → bench 追加 1 张 1★ 且名 ∈ grant_char_pool 现算集(grant_char_
    pool 阵营 spec = 规格域 ∩ 当时牌库,未解锁专家加拉赫/姬子剔除——本域
    = 专家域 2 名,域 9 名过滤后 7 名,注册表派生不手抄)且 ∉ EXPERT_
    CHARS(种子落点选点 = 牌库时点过滤后池现算,专家不入池,过滤语义
    钉死;族惯例 seed 20261027 落点已实现批现算验证落非专家成员);
    效果串 ``env_gift_random:<名>@1star``(星级 = spec.star 先验);锚定
    状态容器 + 采样子链 rand=True → 写照常生效且不进失配网(随机态语义,
    首观察静默覆盖)。期望名从同 seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_ENV_12].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _ENV_12, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert expected in pool and expected not in EXPERT_CHARS, \
        '发放名 ∈ 牌库时点池且非专家(未解锁专家剔除生效)'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_jipo_concept_stock_random_equip_leg_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定;概念股族展开卡登记约定):击破概念股(非成员)随机装备
    入账分支 → 效果串 ``env_equip_random:<名>`` 前缀(与绑定态
    ``env_star_grant:`` 分域)、env_grants_done 零 star_grant# 绑定键
    (非成员零绑定写,治「无条件绑定等第二个消费者」缺陷);装备照常
    入栏且名 ∈ 类别池现算集(equips_by_category('简易') 注册表派生,
    不手抄;economy.md 四卡线索名单不含击破 = 装备身份零先验,均匀 v0 +
    按卡固定假说待校准随 fixed_hypothesis 家族键已登记,零卡级申报)。两条
    分支期望值从同 seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与
    生产消费序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_ENV_12].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _ENV_12, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_qungong_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """群攻域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库
    时点池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子
    rng 直构 → bench 追加 1 张 1★ 且名 ∈ grant_char_pool 现算集(本域
    7 名 is_expert 全空 = 全员非专家,牌库时点过滤恒等零收窄——注册表
    派生不手抄,无 T-56 型种子避让约束;族惯例 seed 20261027 落点已实现
    批现算验证 ∈ 域,落点翡翠 = 域独占成员);效果串 ``env_gift_random:
    <名>@1star``(星级 = spec.star 先验);锚定状态容器 + 采样子链 rand=True →
    写照常生效且不进失配网(随机态语义,首观察静默覆盖)。期望名从同
    seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_ENV_13].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _ENV_13, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert expected in pool, \
        '发放名 ∈ 牌库时点池(本域无专家,过滤恒等)'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_qungong_concept_stock_random_equip_branch_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定;概念股族展开卡登记约定):群攻概念股(非成员)随机装备
    入账分支 → 效果串 ``env_equip_random:<名>`` 前缀(与绑定态
    ``env_star_grant:`` 分域)、env_grants_done 零 star_grant# 绑定键
    (非成员零绑定写,治「无条件绑定等第二个消费者」缺陷);装备照常
    入栏且名 ∈ 类别池现算集(equips_by_category('简易') 注册表派生,
    不手抄;economy.md 四卡线索名单不含群攻 = 装备身份零先验,均匀 v0 +
    按卡固定假说待校准随 fixed_hypothesis 家族键已登记,零卡级申报)。两条
    分支期望值从同 seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与
    生产消费序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_ENV_13].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _ENV_13, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_jianyi_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """减益域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库时点
    池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子 rng
    直构 → bench 追加 1 张 1★ 且名 ∈ grant_char_pool 现算集(grant_char_
    pool 阵营 spec = 规格域 ∩ 当时牌库,未解锁专家佩拉剔除——本域
    = 专家域 1 名,域 7 名过滤后 6 名,注册表派生不手抄)且 ∉ EXPERT_
    CHARS(种子落点选点 = 牌库时点过滤后池现算,专家不入池,过滤语义
    钉死;族惯例 seed 20261027 落点已实现批现算验证落非专家成员);
    效果串 ``env_gift_random:<名>@1star``(星级 = spec.star 先验);锚定
    状态容器 + 采样子链 rand=True → 写照常生效且不进失配网(随机态语义,
    首观察静默覆盖)。期望名从同 seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_ENV_14].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _ENV_14, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert expected in pool and expected not in EXPERT_CHARS, \
        '发放名 ∈ 牌库时点池且非专家(未解锁专家剔除生效)'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_jianyi_concept_stock_random_equip_branch_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定;概念股族展开卡登记约定):减益概念股(非成员)随机装备
    入账分支 → 效果串 ``env_equip_random:<名>`` 前缀(与绑定态
    ``env_star_grant:`` 分域)、env_grants_done 零 star_grant# 绑定键
    (非成员零绑定写,治「无条件绑定等第二个消费者」缺陷);装备照常
    入栏且名 ∈ 类别池现算集(equips_by_category('简易') 注册表派生,
    不手抄;economy.md 四卡线索名单不含减益 = 装备身份零先验,均匀 v0 +
    按卡固定假说待校准随 fixed_hypothesis 家族键已登记,零卡级申报)。两条
    分支期望值从同 seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与
    生产消费序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_ENV_14].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _ENV_14, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_zhanjidian_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """战技点域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库时点
    池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子 rng
    直构 → bench 追加 1 张 1★ 且名 ∈ grant_char_pool 现算集(grant_char_
    pool 阵营 spec = 规格域 ∩ 当时牌库,未解锁专家青雀剔除——本域
    = 专家域 1 名,域 7 名过滤后 6 名,注册表派生不手抄)且 ∉ EXPERT_
    CHARS(种子落点选点 = 牌库时点过滤后池现算,专家不入池,过滤语义
    钉死;族惯例 seed 20261027 落点已实现批现算验证落非专家成员);
    独立单位成员 Archer 照发在候选池内〔economy.md:94 族级定论点名
    战技点(Archer)〕;效果串 ``env_gift_random:<名>@1star``(星级 =
    spec.star 先验);锚定状态容器 + 采样子链 rand=True → 写照常生效且不进
    失配网(随机态语义,首观察静默覆盖)。期望名从同 seed 现算(单一来源,
    不手抄)。"""
    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_ENV_15].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _ENV_15, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert expected in pool and expected not in EXPERT_CHARS, \
        '发放名 ∈ 牌库时点池且非专家(未解锁专家剔除生效)'
    assert 'Archer' in pool, \
        '独立单位成员照发在候选池(economy.md:94 族级定论)'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_zhanjidian_concept_stock_random_equip_branch_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定;概念股族展开卡登记约定):战技点概念股(非成员)随机装备
    入账分支 → 效果串 ``env_equip_random:<名>`` 前缀(与绑定态
    ``env_star_grant:`` 分域)、env_grants_done 零 star_grant# 绑定键
    (非成员零绑定写,治「无条件绑定等第二个消费者」缺陷);装备照常
    入栏且名 ∈ 类别池现算集(equips_by_category('简易') 注册表派生,
    不手抄;economy.md 四卡线索名单不含战技点 = 装备身份零先验,均匀 v0 +
    按卡固定假说待校准随 fixed_hypothesis 家族键已登记,零卡级申报)。两条
    分支期望值从同 seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与
    生产消费序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_ENV_15].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _ENV_15, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'
