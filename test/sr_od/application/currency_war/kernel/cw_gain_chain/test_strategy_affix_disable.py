"""退化(id 260601)策略链词缀失效分支锁(镜像 src = kernel/
cw_gain_chain.py on_strategy_gained 硬编码分支;按拆目录规范落位,
同构先例 = 同目录 test_on_env_gained.py 敌后破坏删除分支段)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/REVIEW-T291.md
§3(生效方案 = 复用敌后破坏已落三条效果条目机制建模,选择规则均匀随机换为取尾;
机制单一源 = designs/T-45-dihou-pohuai.md §2.5 族面条款;卡面官方原文:
「使最右侧的敌人词缀失效，并使敌人难度-5。获得8金币。」——失效腿 =
本文件锁面;难度腿/金腿 = STRATEGY_ECONOMY 注册行静态承载〔机制锁由
test_sim_rules 难度族与 economy 估值锁现役辖域,零新增〕):

- 锁 1 删除腿:选退化(rng 注入定值 + 词缀种子右端定向)→
  enemy_affixes 长度 -1、来源 logic_rand(rand=True 双保险,mid-run
  锚定窗也落随机态)、logic_rand_fields() 含 enemy_affixes(补观察谓词
  消费口)、效果串策略变体 strategy_affix_disable:<名> 在账;
- 锁 2 空状态容器边界:零写 + 申报行(strategy_affix_disable_empty_container,
  实机已失效而模型未删);
- 锁 3 取尾选择基准:排序后取右端(状态容器尾元素),非首元素;rng 注入
  不改变选择(确定性取尾,零流键消费——不与敌后破坏采样流共槽);
- 锁 4 mid-run 守卫:节点窗在动 + 当期 hp 真值在场 → 词缀照删、hp
  零写(真值不踩;HP 回调级守卫锁归 kernel/test_cw_opening_hp.py);
- 锁 5 闭集负锁:退化不入 PICK_INVEST_EFFECTS(失效腿走硬编码分支,
  误登记吃红)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    GAIN_CHAIN_PRODUCER,
    STRATEGY_AFFIX_DISABLE_EMPTY_DECL,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    consume_defect_sink,
    set_defect_sink,
)

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_CARD = '退化'


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾;
    先例 = 同目录 test_on_env_gained.py 同族 fixture)。"""

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


def _make_gs(affixes: list[str] | None, *,
             mid_run: bool = False) -> GameState:
    """直构状态容器:词缀名单 logic 直写(首写 old=None,HP 回调种子档零触发
    ——被测删除写的「写前值」由本构造落定);``mid_run`` = 节点窗已开
    (mid-run 守卫锁用)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if affixes is not None:
        gs.write_logic(gs.enemy_affixes, list(affixes), produced_by='Test',
                       evidence='t:affix', sig=_LSIG)
    if mid_run:
        gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='prep'),
                   sig=_SIG_OBS)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = 同目录 test_on_env_gained.py 同族
    helper)。"""
    calls: list[tuple[str, str | None, str, ChannelSig, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel, sig,
                          produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def test_affix_disable_tail_leg_random_state_write(monkeypatch) -> None:
    """删除腿四断言(锁 1):选退化(rng 注入定值)→ ①enemy_affixes
    长度 -1(尾元素整条移除,剩余整条替换);②来源 logic_rand(rand=True
    声明采样链);③logic_rand_fields() 含 enemy_affixes;④效果串策略
    变体 strategy_affix_disable:<名> 在账。词缀种子 = 位置域序(读链
    center.x 升序排序基准),右端 = 尾元素。"""
    affixes = ['库藏生锈', '灼热轰炸', '第二位面强化']
    gs = _make_gs(affixes)
    calls = _record_writes(gs, monkeypatch)
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(7))
    assert effects == ('strategy_affix_disable:第二位面强化',), \
        f'④效果串策略变体(取尾 = 右端): {effects}'
    assert gs.enemy_affixes.value == ['库藏生锈', '灼热轰炸'], \
        '①长度 -1 且整条替换(尾元素移除)'
    assert gs.enemy_affixes.source == 'logic_rand', \
        '②来源 logic_rand(rand=True 双保险)'
    assert 'enemy_affixes' in gs.logic_rand_fields(), \
        '③随机态字段已登记(补观察谓词消费口)'
    rows = [(c[0], c[1], c[2], c[4]) for c in calls
            if c[0] == 'enemy_affixes']
    assert rows == [('enemy_affixes',
                     'on_strategy_gained:退化#affix_disable',
                     'rand', GAIN_CHAIN_PRODUCER)], f'写行形态: {rows}'


def test_affix_disable_empty_container_zero_write_with_decl(
        monkeypatch, rows_sink: _RowSink) -> None:
    """空状态容器边界(锁 2):状态容器空(直构未写)时选退化 → 零容器写 +
    申报行已登记(kind = strategy_affix_disable_empty_container,实机已
    失效而模型未删的偏差申报),零效果串。"""
    gs = _make_gs(None)
    calls = _record_writes(gs, monkeypatch)
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (), '零效果串(未发生删除)'
    assert not calls, f'零容器写: {calls}'
    assert gs.write_seq == seq_before, '安静不写'
    assert rows_sink.kinds() == [STRATEGY_AFFIX_DISABLE_EMPTY_DECL], \
        f'申报行分键: {rows_sink.kinds()}'


def test_affix_disable_tail_anchor_right_end_deterministic() -> None:
    """取尾选择基准(锁 3):排序后取右端(状态容器尾元素),非首元素;
    不同注入 rng 同一选择且 rng 状态零消耗(确定性取尾,零流键消费
    ——均匀随机旧制不回归)。"""
    affixes = ['库藏生锈', '灼热轰炸', '第二位面强化']
    seen: list[tuple[str, ...]] = []
    for seed in (7, 20261213):
        gs = _make_gs(affixes)
        rng0 = random.Random(seed)
        state0 = rng0.getstate()
        effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                     rng=rng0)
        assert effects == ('strategy_affix_disable:第二位面强化',), \
            f'取尾 = 状态容器尾元素(seed={seed}): {effects}'
        assert gs.enemy_affixes.value == ['库藏生锈', '灼热轰炸'], \
            f'尾元素整条移除(seed={seed})'
        assert rng0.getstate() == state0, \
            f'rng 零消费(确定性取尾,seed={seed})'
        seen.append(effects)
    assert len(set(seen)) == 1, '不同注入 rng 同一选择(取尾非采样)'
    assert not seen[0][0].endswith(affixes[0]), \
        '非首元素(均匀随机旧制不回归)'


def test_affix_disable_mid_run_guard_preserves_hp_truth() -> None:
    """mid-run 守卫(锁 4,端到端):节点窗在动 + 当期 hp 真值在场 →
    词缀照删(取尾命中 HP 档词缀)、hp 零写(开局先验禁覆写当期真值
    ——静默踩踏面封死;开局窗形态由 kernel/test_cw_opening_hp.py
    既有各锁辖域)。实证难度档必须种齐(A8/108):否则先验查表返 None
    跳写,守卫红验不红(锁空转)。"""
    gs = _make_gs(['库藏生锈', '灼热轰炸', '开局不利'], mid_run=True)
    gs.observe(gs.selected_difficulty, 'A8', sig=_SIG_OBS)
    gs.observe(gs.enemy_difficulty, 108, sig=_SIG_OBS)
    gs.observe(gs.hp, 57, evidence='t:battle_truth', sig=_SIG_OBS)
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == ('strategy_affix_disable:开局不利',), \
        f'词缀照删(取尾 = 开局不利): {effects}'
    assert gs.enemy_affixes.value == ['库藏生锈', '灼热轰炸'], '删除已落'
    assert gs.hp.value == 57 and gs.hp.source == 'observation', \
        'mid-run 真值不踩(守卫跳写,hp 保持战斗真值)'


def test_tuihua_not_in_pick_closed_set() -> None:
    """闭集负锁(锁 5):退化不入 PICK_INVEST_EFFECTS——失效腿走
    on_strategy_gained 硬编码分支,误登记四名闭集吃红。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS, \
        '闭集负锁:词缀失效腿走硬编码分支,误登记吃红'
