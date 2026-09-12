"""R5 W1 常开化+观察接线收尾·W1 专项锁面。

范围锚 = docs/develop/sr_od/application/currency_war/game_state/r5-migration-plan.md §2 W1 行;
裁定正本 = ADR-0634(影子双写推翻:journal 无条件常开/写入口签名必填)。
常开与签名必填的通用锁面在 test_cw_state_journal.py(锁语义重推申报在案),
本文件收 W1 独有的四族:

- **kind_inherited 分支保留锁**(W1 ④;ADR-0630 D3 勘误注的「随 M2 补锁」
  义务落账):sim 合成口 node_type=None ∧ 有前值 → kind 沿前值回写
  evidence='kind_inherited';node_type=None ∧ 无前值 → node 不写(诚实缺位)。
  该分支 = 保留决策(R1 落地审 D3 处置),锁钉其存在与语义,防静默摘除;
- **battle_done 新行锁**(W1 ⑤):结算覆盖 settlement 行注记携带
  ``battle_done:<节点类型>`` ——旧 exogenous 'node_enter' 外生行
  (cw_screen_battle_wait 旧写,删除波 1 退役)的「出节点」判读语义由
  settlement 行承接,同时点同载荷;行行自足快照语义强于旧行;
- **legacy 行 = 0 锁**(W1 验证差异项):模拟流(观察/沿用/中继/逻辑写入/
  派生/观察事件/结算覆盖)产出的全部行 sig.actor 在册非空;
- **结构删净锁**:kernel 源无 legacy 合成路径;写入口 sig 参数必填
  (inspect 签名面,防「删了路径留缺省」的半删回归)。
"""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_state_journal as journal_mod
from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    REGISTERED_ACTORS,
    BoardState,
    ChannelSig,
    NodeKey,
    apply_settlement_cover,
    board_state_of,
    register_sig_actors,
    synthesize_from_game_state,
)
from sr_od.application.currency_war.kernel.cw_state import GameState

# ---- 测试签名(actor 已登记;语义同 test_cw_state_journal 的 W1 helper)----
register_sig_actors('TestSigWriter')


def _sig() -> ChannelSig:
    """渠道①签名(obs 族)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


_KERNEL_PATH: Path = (Path(inspect.getfile(BoardState)))


@pytest.fixture()
def journal(tmp_path):
    """装一份指到 tmp 的状态流水(teardown 复位模块全局)。"""
    j = journal_mod.install_state_telemetry(
        tmp_path / 'state' / 'journal.jsonl',
        run_id_provider=lambda: 'run_w1')
    yield j
    journal_mod.reset_state_telemetry()


@pytest.fixture(autouse=True)
def _reset_journal_default():
    """每条用例前复位流水实例(模块级全局隔离纪律)。"""
    journal_mod.reset_state_telemetry()
    yield
    journal_mod.reset_state_telemetry()


# ============================================================ kind_inherited 保留锁(W1 ④)


def _sim_state(node_type, plane: int = 1, round_num: int = 5) -> GameState:
    """裸 sim GameState 桩(node_type 显式可控;gold/level 等按需置缺省)。"""
    st = GameState(plane=plane, round_num=round_num)
    st.node_type = node_type
    st.gold = 30
    st.gold_readable = True
    st.level = 4
    st.level_readable = True
    return st


def test_kind_inherited_branch_retained() -> None:
    """W1 ④(保留锁,非删除对象):node_type 未建模帧 kind 沿前值回写,
    evidence='kind_inherited'(ADR-0630 D3 勘误注:生产 sim 路径不可达、
    潜伏面无害,语义保留并补锁)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    _sig_synth = ChannelSig(family='obs', actor='synthesize_from_game_state',
                            mode='synthesized')
    bs.observe(bs.node, NodeKey(plane=1, round_num=4, kind='battle'),
               evidence='sim:synthesized', sig=_sig_synth)
    # 前帧:node_type=None(裸 GameState 未建模该帧)
    synthesize_from_game_state(bs, _sim_state(None))
    assert bs.node.value is not None, '有前值 = 节点照写'
    assert bs.node.value.kind == 'battle', 'kind_inherited:类型沿前值回写'
    assert bs.node.value.round_num == 5, 'plane/round 真读更新'
    assert bs.node.evidence == 'kind_inherited', 'evidence 标继承语义'


def test_kind_inherited_no_prior_value_keeps_none() -> None:
    """W1 ④ 边界:node_type=None ∧ 无前值 → node 不写保持 None(禁 'prep'
    占位假值,P1-1 同型;诚实缺位)。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    synthesize_from_game_state(bs, _sim_state(None))
    assert bs.node.value is None, '无现值且未读:不写,禁合成假值'


# ============================================================ battle_done 新行锁(W1 ⑤)


def test_settlement_row_carries_battle_done_note(journal) -> None:
    """W1 ⑤:结算覆盖的 settlement 行注记 = battle_done:<节点类型>
    (旧 exogenous 'node_enter' 行「接」半的收编归宿);逐字段行不带注记。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    apply_settlement_cover(
        bs, hp_after=76, streak_after=2, killed=True,
        gold=120, note='battle_done:battle')
    rows = journal.rows
    settle_rows = [r for r in rows if r['field'] == 'settlement']
    assert len(settle_rows) == 1, 'settlement 域恰一行'
    assert settle_rows[0]['note'] == 'battle_done:battle', \
        '出节点语义随 settlement 行在账(判读按注记检索战斗完成)'
    assert settle_rows[0]['sig']['actor'] == 'CwScreenBattleWait', \
        '结算覆盖写端 actor 在册(§3.2.1 ①类属 = 画面 op 类名)'
    other = [r for r in rows if r['field'] in ('hp', 'streak', 'gold')]
    assert all(r['note'] == '' for r in other), '逐字段行不带 battle_done 注记'


# ============================================================ legacy 行 = 0 锁(W1 验证差异项)


def test_journal_rows_all_registered_actor(journal) -> None:
    """legacy 行 = 0:模拟流全行型(write/obs_event)actor 在册非空——
    影子期「空 actor 合成行」在常开账本中结构性消失(ADR-0634)。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        note_action_receipt,
    )
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.gold, 20, sig=_sig())
    bs.carry(bs.gold, frame='p1-r2', sig=_sig())
    bs.write_logic(bs.strategy_refresh_used, {'白银投资': 1},
                   produced_by='CwScreenInvestStrategy',
                   sig=ChannelSig(family='logic_action',
                                  actor='CwScreenInvestStrategy',
                                  mode='compute'))
    bs.relay(bs.active_strategies, ['白银投资'],
             sig=ChannelSig(family='logic_hook', actor='cw_observation',
                            mode='compute'))
    bs.note_obs_event('arbitrate', 'gold', {'old': 20, 'new': 21},
                      verdict='v', sig=_sig())
    note_action_receipt(bs, op='SellBench', applied=True,
                        actor='PrepActionExecutor')
    apply_settlement_cover(bs, hp_after=80, streak_after=1,
                           note='battle_done:battle')
    rows = journal.rows
    assert rows, '模拟流有行(锁前提)'
    empty = [r for r in rows if not r['sig'].get('actor')]
    assert empty == [], '无空 actor 行(legacy 合成已退役)'
    unregistered = [r for r in rows
                    if r['sig'].get('actor') not in REGISTERED_ACTORS]
    assert unregistered == [], '全行 actor 在册(登记面封闭集)'


# ============================================================ 结构删净锁(防半删回归)


def test_no_legacy_synthesis_path_in_kernel_source() -> None:
    """kernel 源无 legacy 合成路径(删代码非停写;防「删了路径留缺省」
    半删回归——R5 W1 删除面「legacy 合成签名路径」的机器面)。判据 =
    legacy 传参形态(``legacy=`` 调用/``legacy:`` 形参注解)零命中;
    注释中的「legacy 已退役」陈述不触红。"""
    src = _KERNEL_PATH.read_text(encoding='utf-8')
    assert 'legacy=' not in src, \
        'kernel 不得残留 legacy 合成传参(R5 W1/ADR-0634)'
    assert 'legacy:' not in src, \
        'kernel 不得残留 legacy 形参(合成签名路径已删净)'


@pytest.mark.parametrize('api', [
    'observe', 'carry', 'write_prior', 'leave_screen',
    'write_logic', 'relay', 'note_obs_event',
])
def test_write_apis_require_sig(api: str) -> None:
    """写入口 sig 必填(inspect 签名面):7 个写 API 的 sig 参数无缺省值
    (显式签名铺满的结构保证;缺位 = 调用期 TypeError,非静默合成;
    confirm 已随 ADR-0651 两步机制废除出列)。"""
    sig = inspect.signature(getattr(BoardState, api))
    assert 'sig' in sig.parameters, f'{api} 缺 sig 参数'
    assert sig.parameters['sig'].default is inspect.Parameter.empty, \
        f'{api}.sig 应为必填(无缺省;影子期缺位合成已退役)'


def test_board_singleton_provider_unchanged() -> None:
    """session 旁表供给口在位(铺满面消费不搬家;防误伤)。"""
    session = SimpleNamespace()
    assert isinstance(board_state_of(session), BoardState)
