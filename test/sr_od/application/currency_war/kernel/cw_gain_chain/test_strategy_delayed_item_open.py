"""偶像经济策略链延迟道具支线测试(镜像 src = kernel/cw_gain_chain.py
on_strategy_gained 延迟道具支线;按拆目录规范落位,环境道同构先例 =
同目录 test_on_env_gained.py 延迟段,完胜回退半边 =
kernel/cw_env_grants/test_check_env_item_open_perfect.py 策略道段)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/REVIEW-T329.md
§五④ 锁 2/6/7/8(写状态副本发放域键域扩展首例 = 策略道;卡面原文:
「获得【火花】和一个【火花礼盒】，倒计时10个节点后礼盒打开,……战斗
完胜时,额外减少1点倒计时。」):

- 锁 2 入队:选偶像经济 → 队列 = (('火花礼盒', (2,4)),)((1,3) 选卡位
  沿默认表步进 10 步)+ 效果串 item_open_scheduled:火花礼盒@2-4 +
  done 含 (偶像经济, delayed_open_accel);**bench/overflow 全程零写**
  (非占席锁:战利品区浮动件禁惯性走 GiftGrant 占席通道);
- 锁 2 修饰局/局终:人身意外险(P1=10)下 (1,3)+10 = (2,3);日程过短
  步进遇 None 停留最后合法值;
- 锁 6 重复获得:队列两条独立条目,done 加速键幂等只写一次;
- 锁 7 腿① 缺口维持:选卡前后 bench/overflow/deployed 逐位不变
  (火花不入席 = sim 状态副本写端缺口申报的行为面锁定,防实现批顺手接送卡);
- 锁 8 快照存续:含策略道条目的队列快照 restore 往返逐位相等。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    GAIN_CHAIN_PRODUCER,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    resolve_plane_node_seqs,
)

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_CARD = '偶像经济'


def _make_gs_node_pos(node_pos: tuple[int, int] | None) -> GameState:
    """直构状态容器(bench 9 空槽);``node_pos`` 非 None = 观察锚定生效序位
    (环境道延迟段同款直测注入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    if node_pos is not None:
        gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(环境道 test_on_env_gained.py 同族 helper)。"""
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


def test_strategy_delayed_leg_enqueues_zero_seat_write(monkeypatch) -> None:
    """到手分支入队(REVIEW-T329 §五④ 锁 2):选偶像经济 → 队列 =
    (('火花礼盒', (2,4)),)((1,3) 步进 10)+ 效果串 item_open_scheduled:
    火花礼盒@2-4 + done 含 (偶像经济, delayed_open_accel);**零席位写**
    ——容器写恰两笔:队列(rand 通道,链收尾)+ done(logic 直写,登记
    事实)。"""
    gs = _make_gs_node_pos((1, 3))
    calls = _record_writes(gs, monkeypatch)
    bench_before = gs.bench.value
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == ('item_open_scheduled:火花礼盒@2-4',), '效果串单行'
    assert gs.pending_item_opens.value == (('火花礼盒', (2, 4)),), \
        '队列登记 = (件名, (1,3)+10 步)'
    assert gs.env_grants_done.value == \
        ((_CARD, 'delayed_open_accel'),), '完胜加速作用域键落 done'
    assert gs.bench.value == bench_before, 'bench 逐位不变(零席位写)'
    assert gs.overflow_card.value is None, 'overflow 零写'
    assert [(c[0], c[1], c[2], c[4]) for c in calls] == [
        ('pending_item_opens',
         f'on_strategy_gained:{_CARD}#open_queue', 'rand',
         GAIN_CHAIN_PRODUCER),
        ('env_grants_done',
         f'on_strategy_gained:{_CARD}#accel_scope', 'logic',
         GAIN_CHAIN_PRODUCER),
    ], f'容器写恰两笔(队列链收尾 + done 直写): {calls}'
    assert all(c[3] == _LSIG for c in calls), '同 sig(同窗相邻)'


def test_strategy_delayed_leg_modified_schedule_and_terminal_hold() -> None:
    """解锁位修饰局与局终停留(环境道锁 3 同式):人身意外险规则
    (P1=10,resolve_plane_node_seqs 注册表现算单一源)下 (1,3) 步进
    10 步 = (2,3)——序差不随位面长度预测漂移;日程过短((1,3) 后无
    后继)→ 步进遇 None 停留最后合法值 (1,3)。"""
    gs = _make_gs_node_pos((1, 3))
    gs.write_logic(gs.node_seq_by_plane,
                   resolve_plane_node_seqs('人身意外险'),
                   produced_by='seed', evidence='t:seqs', sig=_LSIG)
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert gs.pending_item_opens.value == (('火花礼盒', (2, 3)),), \
        '修饰局 (1,3)+10 步 = (2,3)'
    assert effects == ('item_open_scheduled:火花礼盒@2-3',)
    gs2 = _make_gs_node_pos((1, 3))
    gs2.write_logic(gs2.node_seq_by_plane,
                    {1: ('battle',) * 3},
                    produced_by='seed', evidence='t:seqs', sig=_LSIG)
    on_strategy_gained(gs2, _CARD, rand=False, sig=_LSIG)
    assert gs2.pending_item_opens.value == (('火花礼盒', (1, 3)),), \
        '局终方向无后继:停留最后合法值'


def test_strategy_delayed_leg_repeat_gain_two_entries_scope_once() -> None:
    """重复获得(REVIEW-T329 §五④ 锁 6):结构性可达的重复获得 → 队列
    两条独立条目(弹除/回退各自独立),done 加速键幂等只写一次。"""
    gs = _make_gs_node_pos((1, 3))
    on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert gs.pending_item_opens.value == \
        (('火花礼盒', (2, 4)), ('火花礼盒', (2, 4))), '队列两条独立条目'
    assert gs.env_grants_done.value == \
        ((_CARD, 'delayed_open_accel'),), 'done 幂等不重写'


def test_char_grant_leg_stays_family_level_gap(monkeypatch) -> None:
    """腿① 送卡缺口维持锁(REVIEW-T329 §五④ 锁 7,族级定论 = T-267
    §1.7-4/T-272):选偶像经济前后 bench/overflow 逐位不变——火花
    不入席 = sim 状态副本写端缺口申报的行为面锁定,防实现批顺手建送卡效果体
    (本文件锁 2 的独立面:锁 2 锁「礼盒腿零席位写」,本锁锁「角色腿
    不因本批获得通道入席」)。"""
    gs = _make_gs_node_pos((1, 3))
    bench_before = gs.bench.value
    overflow_before = gs.overflow_card.value
    deployed_before = gs.deployed.value
    on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert gs.bench.value == bench_before, \
        'bench 逐位不变(火花不入席,送卡缺口维持族级待办)'
    assert gs.overflow_card.value == overflow_before, 'overflow 零写'
    assert gs.deployed.value == deployed_before, 'deployed 零写'
    placed = [s for s in gs.bench.value.slots
              if s is not None and s.kind == 'unit' and s.unit is not None]
    assert not placed, '备战席零单位(无任何角色入席)'


def test_unregistered_strategy_quiet(monkeypatch) -> None:
    """表外策略安静不写(延迟支线视角:表外卡零写径——on_strategy_
    gained 未收录卡安静不写存量锁的支线半边回归)。"""
    gs = _make_gs_node_pos((1, 3))
    calls = _record_writes(gs, monkeypatch)
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '随便一张未收录卡', rand=False,
                                 sig=_LSIG)
    assert effects == (), '表外策略效果串恒空'
    assert not calls, f'零容器写: {calls}'
    assert gs.write_seq == seq_before, '安静不写'


def test_snapshot_round_trip_with_strategy_entry() -> None:
    """快照存续(REVIEW-T329 §五④ 锁 8 策略道半边):含策略道条目的
    队列快照 restore 往返逐位相等(条目形状 (件名, NodePos) 件名无域限,
    两族条目同构同往返)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    gs = _make_gs_node_pos(None)
    queue = (('惊喜盒', (2, 4)), ('火花礼盒', (2, 4)))
    gs.write_logic(gs.pending_item_opens, queue, produced_by='test-seed',
                   evidence='t:queue', sig=_LSIG)
    snap = gs.full_state_snapshot()
    assert 'pending_item_opens' in snap['values'], '队列进快照'
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.pending_item_opens.value == queue, '往返逐位相等(含策略道)'
