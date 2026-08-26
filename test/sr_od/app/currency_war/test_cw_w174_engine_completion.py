"""W174/ADR-0371 引擎补完守卫单帧锁(own-gap 修法)。

锁验收(「拥有≥门槛 ∧ 上场<门槛时的上场选择行为」;锁契约不锁分布):
1. 缺口帧发补完事务:pair 体系 owned≥tier ∧ on-board<tier → bench 体系件
   上场(cap 满时换下最弱非保护件);
2. 保护序:pair/引擎件不被换下(undeploy 只吃非保护散件);
3. 无缺口帧(owned≥tier∧on-board≥tier / owned<tier)不发射;
4. flag off(engine_completion=False)逐位回 W170 后行为(无补完事务);
5. 末窗豁免:r8 补完事务照发(净效果复核过);boss 冻结轮不启动;
6. 希儿系单卡判据(希儿在手未上场 → 上);
7. bench 容量不足卖最弱非保护 bench 件腾位。
"""
from __future__ import annotations

import re

import pytest

from sr_od.application.currency_war import cw_evolution as cw_evolution_mod
from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_evolution import (
    EvolutionState,
    evolution_step,
)
from sr_od.application.currency_war.cw_intention import IntentionState
from sr_od.application.currency_war.cw_sim import _board_factions_of
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    CompTransaction,
    GameState,
    _recount_board,
    simulate,
)
from sr_od.application.currency_war.cw_strategy import StrategySession


def _char(name: str, star: int = 1, row: str = 'back') -> BenchChar:
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, star=star)


def _sess(pair: tuple[str, ...]) -> StrategySession:
    """p1_pair 配方锁定帧的 session(v3_intention 挂体系对)。"""
    sess = StrategySession()
    sess.v3_intention = IntentionState(p1_pair=pair)
    return sess


# run42 型(run42 复盘:手握 4 种列车件只上 1):deployed 7 件全为
# 非引擎散件(无 仙舟/持续伤害/列车同行 羁绊),cap 满;bench 4 件列车。
_B_FILLER = ('银枝', '刃', '镜流', '布洛妮娅', '阮·梅', '娜塔莎', '翡翠')
_B_TRAIN = ('丹恒·饮月', '姬子·启行', '姬子', '星期日')


def _state(bench=(), deployed=(), level: int = 7,
           round_num: int = 4) -> GameState:
    st = GameState()
    st.plane = 1
    st.round_num = round_num
    st.level = level
    st.gold = 30
    st.bench = list(bench)
    # 排位平衡:前 3 后 4(front_max=4/back_max=6,守终态排不变量)
    st.deployed = [(_char(n, row='front') if i < 3 else _char(n))
                   for i, n in enumerate(deployed)]
    st.board = _recount_board(st.deployed)
    return st


def _t42_frame() -> GameState:
    """列车 owned 4 ≥2 ∧ 上场 0;deployed 7 件非引擎散件占满 cap。"""
    return _state(bench=[_char(n) for n in _B_TRAIN],
                  deployed=_B_FILLER)


def _completion_txs(actions: list) -> list[CompTransaction]:
    return [a for a in actions if isinstance(a, CompTransaction)
            and 'engine_complete' in (a.reason or '')]


def test_completion_tx_deploys_owned_engine_members():
    """①缺口帧:cap 满局手握≥门槛体系件 → 补完事务换上场(run42 型)。"""
    st = _t42_frame()
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert len(txs) == 1
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 列车同行 on-board 达门槛(≥2):拥有已够 → 上场补完
    assert _board_factions_of(out.deployed).get('列车同行', 0) >= 2


def test_completion_protects_engine_and_pair_pieces():
    """②保护序:undeploy 只吃非保护散件——pair/引擎贡献件不下场
   (deployed 掺一件仙舟引擎件符玄,保护集辖,不被换下)。"""
    st = _state(bench=[_char(n) for n in _B_TRAIN],
                deployed=(*_B_FILLER[:6], '符玄'))
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, '缺口仍在(列车 owned≥2 上场 0)应发补完事务'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied'
    # 仙舟引擎件(符玄)不被换下;下的全是非保护散件
    assert '符玄' in {d.char_id for d in out.deployed if d is not None}   # ADR-0392
    downed = {st.deployed[i].char_id for i in (txs[0].undeploy or [])}
    assert downed <= set(_B_FILLER)


def test_completion_no_gap_no_tx():
    """③无缺口不发射:owned≥tier∧已上场够 / owned<tier → 无补完事务
   (获取问题不辖——本批边界,归 W175 早期买入门)。"""
    # 已成帧:仙舟 3 上场 + 列车 2 上场 → 无缺口
    st = _state(
        deployed=('丹恒·饮月', '符玄', '藿藿', '姬子·启行', '姬子'),
        bench=(_char('桑博'), _char('卡芙卡')), level=5)
    sess = _sess(('仙舟', '列车同行'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))
    # owned<tier:仙舟仅 1 件在手
    st2 = _state(deployed=('姬子·启行', '姬子'), bench=(_char('藿藿'),),
                 level=5)
    sess2 = _sess(('仙舟', '列车同行'))
    assert not _completion_txs(evolution_step(st2, sess2, EvolutionState()))


def test_completion_flag_off_restores_baseline():
    """④A/B 通道:engine_completion=False 回 W170 后行为(同帧无补完
   事务);对照组(开)同帧有——差异即本批行为面。"""
    st = _t42_frame()
    sess = _sess(('列车同行', '仙舟'))
    actions_off = evolution_step(st, sess, EvolutionState(),
                                 engine_completion=False)
    assert not _completion_txs(actions_off)
    assert _completion_txs(evolution_step(st, sess, EvolutionState()))


def test_completion_final_window_exemption():
    """⑤末窗豁免:r8(cap 满,undeploy 非空)补完事务照发——净效果
   pair on-board 不减∧引擎数不减;ADR-0363 件2「防丢」语义不辖补上。"""
    st = _t42_frame()
    st.round_num = 8   # P1 位面末窗(nodes_of_plane=9 → 剩 ≤1 轮)
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, '末窗补完(换下散件换上体系件)应豁免冻结'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied'


def test_completion_frozen_on_encounter_node():
    """⑤b 遭遇/boss 冻结轮不启动补完(与既有演进纪律一致)。"""
    st = _t42_frame()
    st.node_type = 'boss'
    sess = _sess(('列车同行', '仙舟'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))


def test_completion_seeie_system_single_card():
    """⑥希儿系单卡判据:希儿在手未上场 → 补完事务上希儿(档=1)。"""
    st = _state(bench=(_char('希儿'), _char('姬子·启行')),
                deployed=_B_FILLER)
    sess = _sess(('希儿系', '列车同行'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs and '希儿系' in txs[0].reason
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied'
    assert '希儿' in {d.char_id for d in out.deployed if d is not None}   # ADR-0392


def test_completion_bench_overflow_sells_unprotected():
    """⑦bench 容量不足:undeploy 落位溢出 → 卖最弱非保护 bench 件腾位
   (保护件不受卖;卖的全是散件)。"""
    st = _t42_frame()
    # bench 塞满 9 槽:4 列车件 + 5 散件(非保护)
    filler = ('银枝', '刃', '镜流', '布洛妮娅', '娜塔莎')
    st.bench = [_char(n) for n in _B_TRAIN + filler]
    sess = _sess(('列车同行', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert txs, 'bench 满仍应有腾位补完(卖散件腾 bench)'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 卖的全是非保护散件;列车件(保护)绝不被卖
    sold = {st.bench[i].char_id for i, src in (txs[0].sell or [])
            if src == 'bench'}
    assert sold <= set(filler)
    assert _board_factions_of(out.deployed).get('列车同行', 0) >= 2


class _LogRecorder:
    """记录 log.info 调用(观测行格式锁用;不触发真实日志链路)。"""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, msg: str, *args: object) -> None:
        self.lines.append(msg % args if args else msg)


def test_engine_complete_log_undeploy_roster(monkeypatch: pytest.MonkeyPatch):
    """⑧W228 观测行格式锁:engine-complete 行 undeploy 追加下场名单
    (角色名 list;空则 [])——W220 判读问题⑥,补完保护锚点(W192-3)
    需名单级可核。零行为改动:仅锁日志行格式。"""
    rec = _LogRecorder()
    monkeypatch.setattr(cw_evolution_mod, 'log', rec)
    # 有下场件帧(cap 满):undeployed=[角色名,...],名单与 tx 索引一致
    st = _t42_frame()
    txs = _completion_txs(evolution_step(st, _sess(('列车同行', '仙舟')),
                                         EvolutionState()))
    assert txs
    line = next(x for x in rec.lines if 'engine-complete' in x)
    expect_names = [st.deployed[i].char_id
                    for i in (txs[0].undeploy or [])]
    assert f'undeployed={expect_names}' in line, line
    assert re.search(r'undeploy=\d+', line), line  # 计数仍在
    # 无下场件帧(cap 未满,纯 deploy 补完):名单为空 → undeployed=[]
    # (列车 owned 4 ≥ tier ∧ 上场 0 缺口;deployed 仅 2 散件有 room,
    # 补完不需换下任何人)
    st2 = _state(bench=[_char(n) for n in _B_TRAIN],
                 deployed=_B_FILLER[:2])
    txs2 = _completion_txs(evolution_step(st2, _sess(('列车同行', '仙舟')),
                                          EvolutionState()))
    assert txs2 and not (txs2[0].undeploy or []), txs2
    line2 = [x for x in rec.lines if 'engine-complete' in x][-1]
    assert 'undeployed=[]' in line2, line2
