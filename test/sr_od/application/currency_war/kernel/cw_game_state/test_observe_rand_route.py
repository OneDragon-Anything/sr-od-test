"""观察失配分类·随机态污染继承测试(Bug A 死因链复现锁)。

锁的设计约定(kernel/cw_game_state.py「污染继承」节):
- 确定面写(write_logic)落到现值来源为 logic_rand 的字段 → 升格随机态
  落帧(采样链下游推导值同为可能局面,随机态保持到观察收尾);
- 死因链完整复现:晶矿奖励角色采样落位(rand)→ 买牌投影在污染基线上
  确定性重写席位 → 观察修正采样差异 → 必须落 ``logic_rand_outcome``
  (预期内随机落地),不得判 ``observe_vs_logic_mismatch`` 真失配停机
  (run_20261121_152706 实证死因:污染洗白后 9 槽席位对 8 槽实读判真
  失配,停机钩子 hook:reconcile_mismatch 触发);
- 确定性链检出力不受损:干净观察基座上的确定性写失配照走真失配分流
  (豁免不得变成掩盖真失配的口子);
- 观察收尾即闭合:观察覆盖后字段翻 observation,后续确定性写恢复
  source=logic,失配检出窗重新打开。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from sr_od.application.currency_war.kernel.cw_action_report.buy_card import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    set_reconcile_andon_hook,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    ShopCard,
)

_SIG_LOGIC = ChannelSig(family='logic_action', actor='test')
_SIG_OBS = ChannelSig(family='obs', actor='test', screen='货币战争-备战',
                      mode='read')

#: 开局四单元基准(与死因链同一开局形态:slots 1-4 有单位,5-9 空)。
_BOARD4 = ('那刻夏', '火花', '绯英', '知更鸟·晴歌')


def _bench_view(char_ids: list[str]) -> BenchView:
    """名字列表 → 定长 9 槽席位视图(前 len 个 unit 槽,其余空)。"""
    units = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=1))
             for c in char_ids]
    return BenchView(slots=units + [BenchSlot(kind='empty')]
                     * (9 - len(char_ids)), capacity=9)


def _seed_rand_board(gs: GameState) -> None:
    """复现晶矿奖励角色采样落位:观察开局四单元 → rand 写加采样角色
    灵砂到首空槽 slot5(采样是猜测,值 = 可能局面快照)。"""
    gs.observe(gs.bench, _bench_view(list(_BOARD4)), sig=_SIG_OBS)
    gs.write_logic_rand(gs.bench, _bench_view(list(_BOARD4) + ['灵砂']),
                        produced_by='CwActionCollectOreParam',
                        evidence='proj_ore_reward_char#ore1', sig=_SIG_LOGIC)


@pytest.fixture(autouse=True)
def _clean_defect_board() -> None:
    """缺陷行缓冲进程级共享:用前取走残留、用后清空,防跨测试串染。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


def test_rand_base_buy_projection_then_correction_is_rand_outcome() -> None:
    """死因链完整复现:rand 基座买牌投影 → 观察修正 = logic_rand_outcome,
    不停机。链步 = run_20261121_152706 15:27:53-15:28:14 四帧语义:
    ① rand 采样灵砂落 slot5;② 买牌投影(确定性重写席位,真实买牌上报
    函数走通污染链);③ 观察读回 8 单元真值(灵砂不存在,买入单元前移
    一槽);④ 分类必须 = 随机效果落地。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _seed_rand_board(gs)
    assert gs.bench.source == 'logic_rand'

    # ② 买牌投影:真实买牌上报函数在污染基线上确定性落位(桂乃芬 → slot6)
    outcome = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=ShopCard(
            x=0, faction='仙舟舰队', name='桂乃芬', cost=1, star=1)),
        _SIG_LOGIC)
    assert outcome.applied is True
    # 污染继承生效:确定性写落到 rand 基座 → 字段保持随机态(不洗白)
    assert gs.bench.source == 'logic_rand', \
        '确定性写落到随机态基座必须升格随机态(provenance 禁洗白)'

    # ③ 观察修正:实读 8 单元(灵砂不存在,买入单元整体前移一槽——
    # 污染基座的落位级联差)——死因链停机帧的同一差异形状
    andon_rows: list[dict] = []
    set_reconcile_andon_hook(andon_rows.append)
    try:
        gs.observe(gs.bench, _bench_view(
            ['那刻夏', '火花', '绯英', '知更鸟·晴歌',
             '桂乃芬', '瓦尔特', '桂乃芬', '火花']),
            sig=_SIG_OBS)
    finally:
        set_reconcile_andon_hook(None)

    # ④ 预期内随机落地:只落 logic_rand_outcome,无真失配行无停机
    rows = consume_defect_sink()
    kinds = [r['kind'] for r in rows]
    assert 'logic_rand_outcome' in kinds, f'随机落地应留台账行: {kinds}'
    assert 'observe_vs_logic_mismatch' not in kinds, \
        f'采样差异不得判真失配(死因链复发): {kinds}'
    assert andon_rows == [], '预期内随机落地不得触发停机钩子'
    assert gs.bench.source == 'observation', '观察覆盖后字段应翻观察态'
    assert [s.unit.char_id for s in gs.bench.value.slots
            if s.kind == 'unit'][-4:] == ['桂乃芬', '瓦尔特', '桂乃芬', '火花']


def test_clean_base_deterministic_mismatch_still_stops() -> None:
    """确定性链检出力不受损:干净观察基座上的确定性写失配照走真失配
    分流(污染继承只扩随机窗,不给确定性推算 bug 开豁免口子)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, _bench_view(list(_BOARD4)), sig=_SIG_OBS)
    # 确定性写(观察态基座 → 不触发污染继承,落 source=logic)
    gs.write_logic(gs.bench, _bench_view(list(_BOARD4) + ['长夜月']),
                   produced_by='test', evidence='proj_test', sig=_SIG_LOGIC)
    assert gs.bench.source == 'logic'

    andon_rows: list[dict] = []
    set_reconcile_andon_hook(andon_rows.append)
    try:
        # 实读与推算意外分歧(多出的单元不存在)
        gs.observe(gs.bench, _bench_view(list(_BOARD4) + ['忘归人']),
                   sig=_SIG_OBS)
    finally:
        set_reconcile_andon_hook(None)

    kinds = [r['kind'] for r in consume_defect_sink()]
    assert 'observe_vs_logic_mismatch' in kinds, \
        f'干净基座确定性失配必须照真失配停: {kinds}'
    assert len(andon_rows) == 1, '真失配必须触发停机钩子'


def test_rand_window_closes_after_observation() -> None:
    """观察收尾即闭合:观察覆盖后字段翻 observation,后续确定性写恢复
    source=logic,失配检出窗重新打开(继承面只在未验证窗口生效)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _seed_rand_board(gs)
    # 同值确定写仍升格(基座未验证)
    gs.write_logic(gs.bench, gs.bench.value,
                   produced_by='test', evidence='proj_test', sig=_SIG_LOGIC)
    assert gs.bench.source == 'logic_rand'

    # 观察覆盖(采新真值)
    truth = _bench_view(list(_BOARD4) + ['桂乃芬'])
    gs.observe(gs.bench, truth, sig=_SIG_OBS)
    assert gs.bench.source == 'observation'

    # 后续确定性写恢复 logic(基座已验证)
    gs.write_logic(gs.bench, replace(truth, slots=list(truth.slots)),
                   produced_by='test', evidence='proj_test2', sig=_SIG_LOGIC)
    assert gs.bench.source == 'logic', \
        '观察收尾后确定性写不得再升格(检出窗重开)'
