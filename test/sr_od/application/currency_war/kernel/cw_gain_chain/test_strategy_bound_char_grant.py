"""价值投资·金(id 200401)绑定型随机角色授予腿锁(镜像 src =
kernel/cw_gain_effects.py 的 ``_STRATEGY_CHAR_GRANT_BINDINGS`` +
``_make_bound_char_grant_effect`` + ``PICK_INVEST_EFFECTS`` 生成式注册 +
家族披露键常量;按被测方法拆目录规范落位——test_gain_chain.py 超线冻结
禁追加,新增测试落拆目录新文件,先例 = 同目录姊妹镜像文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-165-jiazhi-touzi-jin.md(定稿)§4 锁 1/2/3 + REVIEW-T165 §2/④(七裁决
点全部默认案):

- 锁 1 注册腿:表值 = (1, 1, 2)(费用档, 名数, 到手星级);效果体条目
  由工厂从表生成进注册表(表驱动生成式,禁两处字面量);披露键 = 家族
  常量收编在册两键(uniform/with_replacement),零新增键内容(单一源:
  与援军族三键常量的交集 = 全集,键不得双源另立);
- 锁 2 腿 1 sim 世界(sim 装配):固定 rng → 备战 +1 名 2★、名 ∈ 1 费
  载体派生池(禁手抄清单);效果串 ``strategy_gift_random:<名>@2star``
  前缀 + @ 后缀一体断言;采样后绑定域写入(evidence
  ``value_invest_bind:*``,绑定即世界真值);门控测试形态:直构 gs 无
  sim 装配 → 门控恒 False,绑定断言须装配占位后端后行使;
- 锁 3 腿 1 live 形态:同 path 非装配 → 备战随机态写(logic_rand 通道)
  、绑定域零写(live 掷骰是猜测,假绑定禁入容器——复制发放腿唯一判据)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_CHAR_GRANT_BINDINGS,
    PICK_INVEST_EFFECTS,
    REINFORCEMENT_ASSUMPTION_KEYS,
    STRATEGY_RANDOM_CHAR_GRANT_ASSUMPTION_KEYS,
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
    RandomCharSpec,
    random_char_pool,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_CARD = '价值投资·金'

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


class _SimPresenceStub:
    """装配占位后端(仅令 ``sim_backend_installed()`` 为真;本腿不触后端
    任何口,触即 AssertionError 响亮——被测门控只读装配槽非 None;
    test_check_strategy_star_merge_gold 同名先例)。"""

    def screen_identity(self) -> str:
        raise AssertionError('绑定腿不触后端读口')

    def observe(self, screen_name: str) -> object:
        raise AssertionError('绑定腿不触后端观察')

    def visible(self, screen_name: str, area_name: str) -> bool:
        raise AssertionError('绑定腿不触后端门问询')

    def click_answer(self, op: object, screen_name: str, area_name: str,
                     until_find_all: object, until_not_find_all: object):
        raise AssertionError('绑定腿不触后端点击')

    def advance(self, decl: object) -> None:
        raise AssertionError('绑定腿不触后端推进')


@pytest.fixture
def sim_installed():
    """sim 形态:装配占位后端;teardown 必卸(模块槽进程全局)。"""
    cw_sim_ports.install_sim_backend(_SimPresenceStub())
    yield
    cw_sim_ports.uninstall_sim_backend()


def _make_gs(*, bench: list[tuple[str, int]] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;bench 直构槽位 (角色名, 星)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(镜像 test_gain_chain 同名 fixture,装配 + 必达收尾)。"""

    def __init__(self) -> None:
        from sr_od.application.currency_war.kernel.cw_game_state import (
            consume_defect_sink,
            set_defect_sink,
        )
        self.rows: list[dict] = []
        self._consume = consume_defect_sink
        self._set = set_defect_sink
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        self._set(None)
        self._consume()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


def test_bound_char_grant_table_and_registration() -> None:
    """锁 1 注册腿:表值三元(费用档, 名数, 到手星级)= 卡面结构值
    (2星1费 ×1 名);效果体条目由工厂从表生成进注册表(表驱动生成式,
    禁两处字面量);家族披露键 = 在册两键收编(与援军族三键常量取交集
    = 全集——零新增键内容,键禁双源另立)。"""
    assert _STRATEGY_CHAR_GRANT_BINDINGS == {_CARD: (1, 1, 2)}, \
        '表值 = 卡面「2星1费」结构值(费用档 1, 名数 1, 到手星级 2)'
    entry = PICK_INVEST_EFFECTS.get(_CARD)
    assert entry is not None, '注册面在册(生成式)'
    assert callable(entry), '值 = 工厂生成效果体'
    assert set(STRATEGY_RANDOM_CHAR_GRANT_ASSUMPTION_KEYS) == {
        'strategy_gift_random_char_uniform',
        'strategy_gift_random_char_with_replacement'}, \
        '家族披露键 = 在册两键(抽样先验 uniform + 放回申报)'
    assert set(STRATEGY_RANDOM_CHAR_GRANT_ASSUMPTION_KEYS) <= set(
        REINFORCEMENT_ASSUMPTION_KEYS), \
        '披露键与援军族在册键集同源(零新增键内容,禁双源)'


def test_bound_char_grant_sampler_pool_and_domain_guard(
        rows_sink) -> None:
    """锁 2 采样面(池值域断言禁手抄清单;正常路径零申报行)。"""
    pool = set(random_char_pool(RandomCharSpec(cost=1, star=2)))
    assert pool, '前置:1 费池非空(注册表漂移哨)'
    rng = random.Random(200401)
    expected = rng.choice(random_char_pool(RandomCharSpec(cost=1, star=2)))
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(200401))
    assert effects == (f'strategy_gift_random:{expected}@2star',), \
        '效果串 = 前缀 + 采样名 + @ 后缀一体(@ 后缀 = 校准归组键)'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [(expected, 2)], \
        '备战恰 +1 名 2★(到手星级 = desc 明写结构值)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_bound_char_grant_bad_star_raises() -> None:
    """值域哨负锁(工厂直呼行使,表封闭期注册面不可达越界行):表行
    star 越界 → ValueError 响亮——star 值域 = Unit.star 合法域,登记
    笔误禁静默降档;cost=0 系统单位不入随机发放池(援军族同款哨)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _make_bound_char_grant_effect,
    )
    gs = _make_gs(bench=[])
    for cost, star in ((1, 4), (0, 2), (6, 1)):
        effect = _make_bound_char_grant_effect('探针卡', cost, 1, star)
        with pytest.raises(ValueError):
            effect(gs, sig=_LSIG, rng=random.Random(0))


def test_bound_char_grant_sim_world_writes_binding(
        sim_installed, rows_sink) -> None:
    """锁 2 sim 世界主锁(装配后端行使门控):获得时点 → 备战 +1 名 2★
    ∈ 1 费池 + 绑定域写入(值 = {卡名: 采样名},evidence
    ``value_invest_bind:<卡名>:<名>``——绑定即世界真值,复制发放腿唯一
    判据落账)。"""
    rng = random.Random(200401)
    expected = rng.choice(random_char_pool(RandomCharSpec(cost=1, star=2)))
    gs = _make_gs(bench=[])
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(200401))
    assert effects == (f'strategy_gift_random:{expected}@2star',)
    assert gs.strategy_char_grant_bindings.value == {_CARD: expected}, \
        '绑定域 = {卡名: 采样名}(合并写,双持姊妹卡各键并存)'
    fld = gs.strategy_char_grant_bindings
    assert fld.source == 'logic', '绑定 = 世界真值 → 确定面直写'
    assert (fld.evidence or '').startswith(
        f'value_invest_bind:{_CARD}:'), '绑定写 evidence 前缀'
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [(expected, 2)], \
        '备战 +1 名 2★ ∈ 1 费池'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_bound_char_grant_live_form_zero_binding_write(
        rows_sink) -> None:
    """锁 3 live 形态负锁(核心):未装配 sim(纯实机态)→ 备战照常
    随机态直写(T-89 族形猜测写:live 掷骰 = 未验证推算,下一备战帧
    bench 整表观察纠偏)、绑定域零写——假绑定即使无消费面也禁入容器
    (复制发放腿唯一判据,静默存续不可接受)。"""
    cw_sim_ports.uninstall_sim_backend()
    rng = random.Random(200401)
    expected = rng.choice(random_char_pool(RandomCharSpec(cost=1, star=2)))
    gs = _make_gs(bench=[])
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(200401))
    assert effects == (f'strategy_gift_random:{expected}@2star',)
    units = bench_units_of(gs)
    assert [(u.char_id, u.star) for u in units] == [(expected, 2)], \
        'live 备战照常随机态直写(族形猜测保真度)'
    assert gs.bench.source == 'logic_rand', '随机态通道(logic_rand)'
    assert gs.strategy_char_grant_bindings.value in (None, {}), \
        '绑定域零写(直构未种容器 None 形态同零写)'
    assert rows_sink.kinds() == [], '零申报行(零写 = 无缺口)'
