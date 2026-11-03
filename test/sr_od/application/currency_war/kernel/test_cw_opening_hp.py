"""cw_opening_hp 词缀域写尾 HP 先验跟随回调测试(镜像 src =
kernel/cw_opening_hp.py 的该被测函数;按 src 镜像规范落位)。

测试面依据 = T-45 敌后破坏设计(.debug/progress/2026-09-23-invest-effects-
calc/designs/T-45-dihou-pohuai.md)§2.3 + §4 锁 5(对抗轮 2 N1/N2 修法甲
落定形态):
- **HP 跟随 = 词缀域逻辑写尾回调**:enemy_affixes 逻辑写(logic/logic_rand
  两通道同经,挂点 = cw_game_state._write_logic_frame)落帧后 diff 新旧
  名单,消失词缀命中 _AFFIX_HP_DELTA → 以删除后词缀表经 opening_hp_prior
  现算 → 经 write_prior 重算 HP 先验(写通道统一 prior 单一来源,evidence
  必带 prior: 前缀);
- **observe 覆盖不触发回调**(回归 deployed「观察写零回调」契约——
  observe 覆盖词缀后 HP 零写的形态必红 = 锁住改判);
- **种子写(old=None)不触发**(N5:种子档 diff 语义 = 全量消失候选,禁误触发);
- 非命中词缀/非实证难度档 → 零 HP 写;先验永不过可信位
  (hp_decision_trusted_of fail-closed);真值帧覆盖 prior 静默采新零告警
  (先验非 logic 来源,不进失配三分流)。

追加面 = 退化(策略卡)mid-run 跳写守卫(策略链词缀失效分支复用本
回调;生效方案 = designs/REVIEW-T291.md §3,守卫 = 节点窗在动跳写):
mid-run(node 锚定)时当期 hp 真值在场 → 回调零 HP 写(真值不踩,
开局先验通道 mid-run 停用);T-45 §4 锁 5 原「退化 mid-run logic 触发
→ 同走 prior」形态随守卫现值化(真值帧覆盖 prior 静默采新不变)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_hp_policy import (
    hp_decision_trusted_of,
)
from sr_od.application.currency_war.kernel.cw_opening_hp import (
    AFFIX_HP_RESYNC_EVIDENCE,
    OPENING_HP_BASE,
    on_enemy_affixes_logic_write,
)

_SIG_LA = ChannelSig(family='logic_action', actor='TestWriter', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='TestWriter')


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾;
    先例 = kernel/cw_gain_chain/test_on_env_gained.py 同族 fixture)。"""

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


def _make_gs(affixes: list[str] | None, *, difficulty: str = 'A8',
             enemy_difficulty: int | None = 108) -> GameState:
    """直构容器:实证难度档(可覆写供非实证档臂)+ 词缀名单 logic 直写
    (首写 old=None,回调种子档零触发——被测 diff 的「写前值」由本构造
    落定,测试体再写第二笔触发 diff)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.selected_difficulty, difficulty, sig=_SIG_OBS)
    if enemy_difficulty is not None:
        gs.observe(gs.enemy_difficulty, enemy_difficulty, sig=_SIG_OBS)
    if affixes is not None:
        gs.write_logic(gs.enemy_affixes, list(affixes), produced_by='Test',
                       evidence='t:affix', sig=_SIG_LA)
    return gs


def test_delete_hp_delta_affix_resyncs_prior() -> None:
    """删除「开局不利」→ HP 经 write_prior 重算(设计 §4 锁 5 主分支):
    prior 来源、evidence prior: 前缀、值 = 无修正基线(不含 -20;
    期望从 OPENING_HP_BASE 现算不手抄);先验永不过可信位(fail-closed)。"""
    gs = _make_gs(['开局不利', '库藏生锈'])
    on_enemy_affixes_logic_write(gs, ['开局不利', '库藏生锈'],
                                 ['库藏生锈'], source='Test')
    assert gs.hp.value == OPENING_HP_BASE, '重算值 = 无「开局不利」基线'
    assert gs.hp.source == 'prior', '写通道 = write_prior(prior 来源)'
    assert gs.hp.evidence == AFFIX_HP_RESYNC_EVIDENCE, 'evidence 前缀语义段'
    assert hp_decision_trusted_of(gs) is False, '先验不过可信位(fail-closed)'


def test_logic_rand_channel_same_tail() -> None:
    """logic_rand 通道同经(挂点在 _write_logic_frame 共用体,两逻辑通道
    同款):随机态写删除「开局不利」→ 同走 prior 重算。"""
    gs = _make_gs(['开局不利', '库藏生锈'])
    gs.write_logic_rand(gs.enemy_affixes, ['库藏生锈'], produced_by='Test',
                        evidence='t:rand', sig=_SIG_LA)
    assert gs.hp.value == OPENING_HP_BASE and gs.hp.source == 'prior', \
        '随机态写尾同样触发先验重算'


def test_delete_non_delta_affix_zero_hp_write() -> None:
    """删除非命中词缀 → 零 HP 写(设计 §4 锁 5:消失词缀不命中 HP 档,
    HP 与该词缀集零耦合)。"""
    gs = _make_gs(['库藏生锈', '灼热轰炸'])
    seq_before = gs.write_seq
    on_enemy_affixes_logic_write(gs, ['库藏生锈', '灼热轰炸'],
                                 ['库藏生锈'], source='Test')
    assert gs.hp.value is None and gs.hp.source == 'observation', '零 HP 写'
    assert gs.write_seq == seq_before, '安静不写'


def test_observe_overwrite_no_callback(rows_sink: _RowSink) -> None:
    """observe 覆盖不触发回调(设计 §4 锁 5 改判锁,必红形态):observe
    覆盖随机态词缀名单使「开局不利」消失 → HP 零写——观察写零回调契约
    (deployed 同款;被覆盖对象 = 删除分支猜测名单,差异落
    logic_rand_outcome 台账预期内,零 HP 失配类行)。"""
    gs = _make_gs(None)
    gs.write_logic_rand(gs.enemy_affixes, ['开局不利', '库藏生锈'],
                        produced_by='Test', evidence='t:rand', sig=_SIG_LA)
    gs.observe(gs.enemy_affixes, ['库藏生锈'], evidence='t:obs', sig=_SIG_OBS)
    assert gs.enemy_affixes.source == 'observation', '覆盖照常采新'
    assert gs.hp.value is None and gs.hp.source == 'observation', \
        'observe 覆盖后 HP 零写(回调不触发)'
    assert rows_sink.kinds() == ['logic_rand_outcome'], \
        f'差异台账 = 随机效果落地(预期内非失配): {rows_sink.kinds()}'


def test_seed_write_no_callback() -> None:
    """种子写(old=None)不触发重算(设计 §2.3 N5 边界):开局种子底座
    首写词缀名单 diff 语义 = 全量消失候选,回调直接跳过——hp 维持种子
    随机态(基线 82),不被翻成 prior。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        seed_opening_state,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    assert gs.enemy_affixes.value == [], '种子空名单已落'
    assert gs.hp.source == 'logic_rand' and gs.hp.value == OPENING_HP_BASE, \
        'hp 维持种子随机态(种子写零回调)'


def test_unsampled_difficulty_skips_resync() -> None:
    """非实证难度档 → 零 HP 写(先验表只填实证档禁外推,查表口径:
    opening_hp_prior 返 None 直接跳写)。"""
    gs = _make_gs(['开局不利', '库藏生锈'], difficulty='B8')
    seq_before = gs.write_seq
    on_enemy_affixes_logic_write(gs, ['开局不利', '库藏生锈'],
                                 ['库藏生锈'], source='Test')
    assert gs.hp.value is None and gs.write_seq == seq_before, \
        '非实证档跳写(诚实未知)'


def test_true_read_overrides_prior_without_alarm(rows_sink: _RowSink) -> None:
    """真值帧覆盖先验静默采新零告警(设计 §4 锁 5:先验非 logic 来源,
    不进失配三分流;姊妹卡退化 mid-run 形态已由 mid-run 跳写守卫承接
    ——见本文件守卫锁,真值帧覆盖 prior 静默采新零告警不变)。"""
    gs = _make_gs(['开局不利', '库藏生锈'])
    on_enemy_affixes_logic_write(gs, ['开局不利', '库藏生锈'],
                                 ['库藏生锈'], source='Test')
    assert gs.hp.source == 'prior'
    gs.observe(gs.hp, 100, evidence='t:real', sig=_SIG_OBS)
    assert gs.hp.value == 100 and gs.hp.source == 'observation', '真值采新'
    assert hp_decision_trusted_of(gs) is True, '真读恢复可信位'
    assert rows_sink.kinds() == [], f'覆盖零台账行: {rows_sink.kinds()}'


def test_mid_run_node_window_skips_resync() -> None:
    """mid-run 节点窗在动 → 跳写(退化批守卫):策略卡退化可中途获得,
    其词缀删除写触发本回调时,当期 hp 已有战斗真值——开局先验重算只有
    「静默踩踏」一个效果,守卫跳写(真值不踩)。开局窗形态(node 未锚)
    照旧重算 = 既有各锁辖域。"""
    gs = _make_gs(['开局不利', '库藏生锈'])
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='prep'),
               sig=_SIG_OBS)
    gs.observe(gs.hp, 57, evidence='t:battle_truth', sig=_SIG_OBS)
    seq_before = gs.write_seq
    on_enemy_affixes_logic_write(gs, ['开局不利', '库藏生锈'],
                                 ['库藏生锈'], source='Test')
    assert gs.hp.value == 57 and gs.hp.source == 'observation', \
        'mid-run 真值不踩(守卫跳写)'
    assert gs.write_seq == seq_before, '零 HP 写'
