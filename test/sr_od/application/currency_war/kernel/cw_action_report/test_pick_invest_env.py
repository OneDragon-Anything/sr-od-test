"""pick_invest_env 上报 rng 条件解析测试(迭代 2026-09-23-invest-effects-calc
T-10 人才引进;镜像 src = kernel/cw_action_report/pick_invest_env.py)。

测试面依据 = 该迭代 designs/T-10-rencai-yinjin.md §2.4/§4 测试 5:
上报函数仅当**选中环境登记了随机支**(ENV_GIFTS[名].chars_random_immediate
非空)才经 ``action_sampling_rng('pick_invest_env', rng)`` 解析采样 rng
(显式传入 > 注入槽 > 自掷);无随机支环境透传 None 零解析。理由:注入槽
(install_backend)每次调用即推序号——无条件解析会使任何环境选卡都推号,
后继动作采样流键整体位移 = 跨版本 sim A/B 无关变量噪声;条件解析使
「默认环境局(无随机支)rng 消耗序列逐位不变」严格成立。

计数 provider 双态断言:无随机支环境(火药味)→ provider 零调用;
人才引进 → 恰一次;显式传入优先于注入槽(显式 rng 在场则 provider
不触,落席名 = 显式 rng 的掷骰结果)。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    RandomCharSpec,
    random_char_pool,
)
from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool

_SIG = ChannelSig(family='logic_action', actor='PickInvestEnvTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='PickInvestEnvTest')


def _make_gs(opts: list[str]) -> GameState:
    """直构容器:bench/equips 观察(空席空栏,发放两条分支可落)+ 选卡槽逻辑写。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    # equips 一并观察(装备入账分支发放落栏前置;既有测试零断言 equips,无波及)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    gs.write_logic(gs.invest_env_opts, opts, produced_by='T',
                   evidence='t:opts', sig=_SIG)
    return gs


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


@pytest.fixture
def provider_calls() -> list[str]:
    """计数 provider(返回固定种子 rng;调用即记录 tool 键),必达复位。"""
    calls: list[str] = []

    def _fn(tool: str) -> random.Random:
        calls.append(tool)
        return random.Random(0)

    set_action_rng_provider(_fn)
    try:
        yield calls
    finally:
        set_action_rng_provider(None)


def test_no_random_leg_env_skips_rng_resolution(provider_calls: list[str]) -> None:
    """条件解析负态:选无随机支环境(火药味 = 道具支 only)→ provider
    零调用(序号不推,默认环境局 rng 消耗序列逐位不变)。"""
    gs = _make_gs(['火药味', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == [], '无随机支环境零解析'


def test_delayed_item_env_skips_rng_resolution(
        provider_calls: list[str]) -> None:
    """条件解析负态·倒计时件(T-34 命运礼物设计 §4 锁 10 采样半边,
    迭代 2026-09-23-invest-effects-calc):命运礼物 = 全链零采样(到手
    确定件名、解锁位确定推算、开盒确定事件,不在 ENV_GIFTS 也不在
    ENV_DEPLOY_LOCK_GRANTS)→ provider 零调用(注入槽序号不推,后继
    动作采样流键零位移)。"""
    gs = _make_gs(['命运礼物', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == [], '零采样环境零解析'
    assert gs.pending_item_opens.value == (('惊喜盒', (2, 4)),), \
        '队列登记照常(零解析不影响发放分支)'


def test_random_leg_env_resolves_rng_exactly_once(
        provider_calls: list[str]) -> None:
    """条件解析正态:选人才引进 → 恰一次解析(tool 键 = pick_invest_env),
    注入槽 rng 采样即落席(bench 追加 1 张 1★,名 ∈ 4 费规格池)。"""
    gs = _make_gs(['人才引进', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == ['pick_invest_env'], '恰一次解析'
    units = _bench_units(gs)
    assert len(units) == 1 and units[0][1] == 1, '采样落席 1 张 1★'
    assert units[0][0] in random_char_pool(RandomCharSpec(cost=4, star=1))


def test_explicit_rng_beats_provider(provider_calls: list[str]) -> None:
    """显式传入优先于注入槽(action_sampling_rng 解析序):装 provider 下
    显式传 rng → provider 零调用,落席名 = 显式 rng 的掷骰结果(同 seed
    现算期望,不手抄;期望源 = 生产同源牌库时点池 grant_char_pool)。"""
    gs = _make_gs(['人才引进', '轮岗', '头彩'])
    pool = grant_char_pool(gs, RandomCharSpec(cost=4, star=1))
    expected = random.Random(20261014).choice(pool)
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG, rng=random.Random(20261014))
    assert out.applied
    assert provider_calls == [], '显式 rng 在场,注入槽不触'
    assert _bench_units(gs) == [(expected, 1)], '落席 = 显式 rng 掷骰'


# ==================== 随机装备支解析(劳务派遣合同)====================
# (设计 = 该迭代 designs/T-19-laowu-paiqian-hetong.md §3 pick_invest_env
# 条件行改写 + §4.7 前置;条件 = chars_random_immediate 或
# equips_random_immediate 任一非空)


def test_equip_random_leg_env_resolves_rng(provider_calls: list[str]) -> None:
    """随机装备支正态:选劳务派遣合同(equips_random_immediate only)→
    恰一次解析(tool 键 = pick_invest_env),星徽采样经注入槽 rng 落 equips
    + done 绑定键落地(不扩条件行则本卡走回退自掷,sim 分支1 非确定)。"""
    gs = _make_gs(['劳务派遣合同', '轮岗', '头彩'])
    gs.write_logic(gs.equips, [], produced_by='T', evidence='t:eq', sig=_SIG)
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == ['pick_invest_env'], '随机装备支恰一次解析'
    assert len(gs.equips.value) == 1, '分支1 发放 1 件星徽'
    binding = [k for e, k in (gs.env_grants_done.value or ())
               if e == '劳务派遣合同' and k.startswith('star_grant#')]
    assert binding, '绑定键落地'


def test_non_gift_env_pick_no_attrerror_zero_resolution(
        provider_calls: list[str]) -> None:
    """非 ENV_GIFTS 环境选卡回归(条件行括号锁):_grant 为 None(经济
    环境选卡必经)→ 条件短路零解析不炸链——按「追加 or 子句」逐字落实
    会成 (A and B) or C,对 None 取属性 AttributeError 炸选卡链。"""
    gs = _make_gs(['火药味', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=1), _SIG)   # 轮岗 = 经济环境,不在 ENV_GIFTS
    assert out.applied
    assert provider_calls == [], '非随机支环境零解析'
    assert (gs.active_env.value or '') == '轮岗'


def test_deterministic_equip_env_grants_without_rng(
        provider_calls: list[str]) -> None:
    """确定性装备环境(T-31 设计 §4 锁 5):红钻贵族零随机支 → rng 谓词
    零解析(provider 不触,确定性装备入账分支不入谓词);选卡后 equips 尾追
    '红钻'、bench +1 箱(supply_box)——上报 → gain_invest_env →
    on_env_gained 双端同链,live/sim 共用语义一条测试覆盖。"""
    gs = _make_gs(['红钻贵族', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == [], '零随机支环境零解析'
    assert list(gs.equips.value) == ['红钻'], '装备入账分支入栏'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert len(boxes) == 1, '开箱分支落席 1 个 supply_box 槽件'


def test_deterministic_equip_env_grants_without_rng_blue(
        provider_calls: list[str]) -> None:
    """确定性装备环境(T-32 设计 §4 锁 5):蓝钻贵族零随机支 → rng 谓词
    零解析(provider 不触);选卡后 equips 尾追 '蓝钻'、bench +1 箱
    (supply_box)——上报 → gain_invest_env → on_env_gained 双端同链,
    live/sim 共用语义一条测试覆盖。"""
    gs = _make_gs(['蓝钻贵族', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == [], '零随机支环境零解析'
    assert list(gs.equips.value) == ['蓝钻'], '装备入账分支入栏'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert len(boxes) == 1, '开箱分支落席 1 个 supply_box 槽件'


# ==================== 环境道具双件(专家研讨会)====================
# (设计 = 迭代 2026-09-23-invest-effects-calc T-39 专家研讨会设计 §4 锁 7)


def test_expert_seminar_pick_grants_two_item_slots_no_rng(
        provider_calls: list[str]) -> None:
    """双端同链(T-39 设计 §4 锁 7):report_action_pick_invest_env_param
    ('专家研讨会') → gain_invest_env → on_env_gained 道具通道 → bench 落
    两槽,kind 序 = ['bookcard', 'supply_box'] 且 item 逐槽 = 卡文名
    (live/sim 共用语义一条覆盖);零随机支 → rng 谓词零解析(条件行锁,
    默认环境局 rng 消耗序列逐位不变)。"""
    gs = _make_gs(['专家研讨会', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == [], '零随机支环境零解析'
    assert (gs.active_env.value or '') == '专家研讨会', '选择事实写值'
    slots = [(s.kind, s.item) for s in gs.bench.value.slots
             if s is not None and s.kind != 'empty']
    assert slots == [('bookcard', '专家邀请函'),
                     ('supply_box', '简易武装箱')], f'两槽卡文序: {slots}'


# ==================== 开局替换型赠卡(人才储备)====================
# (设计 = 迭代 2026-09-23-invest-effects-calc T-43 设计 §4 锁 5)


def test_opening_replace_env_pick_bench_three_not_seven(
        provider_calls: list[str]) -> None:
    """双端同链替换语义分界锁(T-43 设计 §4 锁 5):上报选人才储备 →
    bench 恰 3 只 3 费 1★(替换语义分界:发放结果即终态,非 4+3=7 叠加
    ——T-10/T-36 追加语义与本卡替换语义的分界);恰一次 rng 解析(随机支
    在册,pick_invest_env 条件行命中)。"""
    gs = _make_gs(['人才储备', '轮岗', '头彩'])
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert provider_calls == ['pick_invest_env'], '随机支恰一次解析'
    units = _bench_units(gs)
    pool = random_char_pool(RandomCharSpec(cost=3, star=1))
    assert len(units) == 3, '替换后恰 3 只(非叠加 7 只)'
    assert all(n in pool and st == 1 for n, st in units), '全 3 费 1★'
