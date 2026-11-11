"""on_env_gained 持续伤害契约分支测试:即时分支回归 + 锚键分支(镜像 src =
kernel/cw_gain_chain.py 的该被测函数,按拆目录规范落位;同函数兄弟测试 =
kernel/test_gain_chain.py ENV_GIFTS 分道段〔超限只读复用〕)。

测试面依据 = 设计稿(原件已退役)(设计稿(原件已退役),
设计稿(原件已退役;判据 = 本文件锁面申报))§2.1/§2.4 + §4.3:
- **即时分支回归**:获得环境当刻 gain_character 发椒丘+卡芙卡(desc 无
  数量/星级词,单数缺省 1★ 先验族)——本批零改动,回归锁;
- **锚键分支**:'dot_anchor#<位面>-<轮>' 纯登记件非门控,获得刻与即时分支
  同窗相邻 write_logic 直写(同 evidence 同 sig);节点未知不写且须显式
  判 node——``_node_frame`` 未观察返回空串,照抄会产出 'dot_anchor#-'
  畸形键;开局三选一获取时 sim 节点未进窗 → 缺锚 = 预期形态。

追加面 = T-33 英雄登场设计稿(原件已退役;§ 号 = 原稿节序)§2.3 + §4 锁 2/3/4/9/11:
随机赠卡锁分支(采样发卡 + 发号 + 锁域写 + 完胜作用域键 done,四笔同窗)
/ 未锚定窗防御基准 / rng 链确定性 / 溢出解耦 / 表外环境安静。

再追加面 = T-42 特邀专家:银狼设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 5(advisor 分道条件形态支,调用点④):种子起手在场判定解锁(裁定④,
防误改回「种子不解锁」)/ 种子无目标名 → 空尾效果串维持 / bench 未观察
fail-closed 零写 + 缺陷行 / 在场判定覆盖 deployed 与溢出位。

再追加面 = T-45 敌后破坏设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 1/2/6:
词缀失效删除分支(均匀随机删 1 → 随机态写回四断言)/ 空状态容器零写 + 申报行 /
装备佩戴豁免跟随解除。锁面 5(HP 词缀回调)归 kernel/test_cw_opening_hp.py
(回调宿主镜像);锁面 7(sim 追加链)归 sim/cw_sim_backend/(流程级镜像);
锁面 3/4(写门三分支/触发链)归 operations/cw_screen/test_plane_intel_pipeline.py
与 kernel/cw_screen_report/test_plane_intel.py。

再追加面 = 概念股族模式卡(阵营随机赠卡 + 随机简易装备;权威版本 =
game_state/gain-chain.md §3 随机支/随机装备支段 + fields.md §5.2 效果缺口
与载体登记,语义 = 「概念股族模式卡登记约定」):阵营支发放(阵营池
现算比对 + 采样子链不进失配网)与绑定门非绑定态(零 done 键 +
``env_equip_random:`` 前缀);绑定态回归面 = 存量
kernel/test_gain_chain.py 随机装备通道段三锁(超限文件,禁追加,跑绿
即回归判据)。

再追加面 = 概念股族展开卡(燃血概念股 id 1002,T-49;概念股族展开卡
登记约定,权威版本 = fields.md §5.2 效果缺口与载体登记 + gain-chain.md §3
随机支/随机装备支段):族内第二实例,与追击测试同构仅值异——燃血域
随机支发放分支 + 绑定门非绑定态(seed 消耗序同构,期望名改从燃血池/
简易池现算)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_env_grants import (
    DOT_CONTRACT_ENV,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    ENV_AFFIX_DISABLE_ENV,
    ENV_AFFIX_DISABLE_RNG_TOOL,
    GAIN_CHAIN_PRODUCER,
    gain_invest_env,
    on_env_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    consume_defect_sink,
    deployed_view_sequential,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_GIFTS,
)

_ENV = DOT_CONTRACT_ENV
_SIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_EVIDENCE = f'on_env_gained:{_ENV}'


def _make_gs(*, node: bool = False) -> GameState:
    """直构状态容器(bench = 开局初始值 9 空槽);``node`` = 节点窗已开。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    if node:
        gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
                   sig=_SIG_OBS)
    return gs


def _bench_units(gs: GameState) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _record_writes(gs: GameState,
                   monkeypatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道,
    sig, produced_by) 写行(先例 = kernel/test_gain_chain.py 同族 helper)。"""
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


def test_immediate_leg_and_anchor_same_window(
        monkeypatch) -> None:
    """即时分支 + 锚键分支同窗(设计稿 §2.4/§2.1):节点窗已开时获得环境 →
    bench 增椒丘+卡芙卡(1★ 确定发放,即时分支零改动回归)+ done 追加锚键
    'dot_anchor#1-3'(纯登记非门控,与即时分支同 evidence 同 sig 相邻,
    write_logic 直写登记事实)。"""
    gs = _make_gs(node=True)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG)
    assert effects == ('env_gift:椒丘', 'env_gift:卡芙卡'), '即时分支效果串'
    assert _bench_units(gs) == [('椒丘', 1), ('卡芙卡', 1)], '两名 1★ 入席'
    assert gs.env_grants_done.value == ((_ENV, 'dot_anchor#1-3'),), \
        '锚键纯登记(帧 = 位面-轮)'
    done_rows = [(c[0], c[1], c[2], c[4]) for c in calls
                 if c[0] == 'env_grants_done']
    assert done_rows == [('env_grants_done', _EVIDENCE, 'logic',
                          GAIN_CHAIN_PRODUCER)], f'锚键单笔直写: {done_rows}'
    assert calls[-1][3] == _SIG, '锚键与即时分支同 sig(同窗相邻)'


def test_anchor_skipped_when_node_not_in_window(monkeypatch) -> None:
    """节点未知不写(设计稿 §2.1 显式判 node + §4.1⑥ 缺锚形态):开局
    三选一获取时 sim 节点尚未进窗(node None)→ 即时分支照常、零锚键零
    畸形键(缺锚不影响猜测写/计数/证实,check_env_dot_grants 门控 =
    active_env)。"""
    gs = _make_gs(node=False)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _ENV, rand=False, sig=_SIG)
    assert effects == ('env_gift:椒丘', 'env_gift:卡芙卡'), '即时分支照常'
    assert not gs.env_grants_done.value, '零锚键(开局形态预期)'
    assert all('dot_anchor' not in (c[1] or '') for c in calls), \
        '无畸形键痕迹(禁 dot_anchor#- 形态)'


def test_skill_point_contract_immediate_leg_regression(monkeypatch) -> None:
    """战技点契约即时分支回归(T-29 设计 §1/§4 锁 8):获得环境当刻
    chars_immediate 逐名确定发放(1★,desc 无数量/星级词单数缺省)→
    bench 增丹恒·饮月+花火各 1——现役通道逐位不变,锁不被晶矿开启
    条件分支批次扰动;获得刻零晶矿触发 done(条件分支归
    check_env_ore_open_grants,打开晶矿计数达标才发,获得刻零预登记)。"""
    gs = _make_gs()
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, '战技点契约', rand=False, sig=_SIG)
    assert effects == ('env_gift:丹恒·饮月', 'env_gift:花火'), '即时分支效果串'
    assert _bench_units(gs) == [('丹恒·饮月', 1), ('花火', 1)], \
        '两名 1★ 入席(确定发放)'
    assert gs.env_grants_done.value is None, '获得刻零晶矿触发 done'
    assert all('ore_open' not in (c[1] or '') for c in calls), \
        '零 ore_open 写行痕迹(条件分支不随获得刻触发)'


def test_stellar_hunter_contract_immediate_leg_regression() -> None:
    """星核猎手契约即时分支回归(T-30 设计 §4 锁 8):获得环境当刻
    chars_immediate 确定发放(卡芙卡 1★,desc 无数量/星级词单数缺省)
    → bench 增卡芙卡 1——现役通道逐位不变;其 **uid 恒 None**(即时分支
    不传 uid 形参,实例号仅条件分支发放刻赋号)。"""
    gs = _make_gs()
    effects = on_env_gained(gs, None, '星核猎手契约', rand=False, sig=_SIG)
    assert effects == ('env_gift:卡芙卡',), '即时分支效果串'
    placed = [s.unit for s in gs.bench.value.slots
              if s is not None and s.kind == 'unit' and s.unit is not None]
    assert [(u.char_id, u.star, u.uid) for u in placed] == \
        [('卡芙卡', 1, None)], '1★ 入席且无实例号(锁域零记录)'
    assert not gs.env_grant_deploy_locks.value, '即时分支零锁记录'
    assert not gs.env_grant_uid_seq.value, '即时分支零发号'


# ============================================================ 随机赠卡锁分支
# (环境「随机赠卡+上场锁」登记表发放分支;设计稿(原件已退役)
# 序位 (1,1) 沿默认表步进 19 步 = (3,4)(序 20)。)

_DEPLOY_ENV = '英雄登场'


def _make_gs_node_pos(node_pos: tuple[int, int] | None) -> GameState:
    """直构状态容器(bench 9 空槽);``node_pos`` 非 None = 观察锚定生效序位
    (check_env_battle_grants 测试同款直测注入)。"""
    gs = _make_gs()
    if node_pos is not None:
        gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    return gs


def test_deploy_lock_grant_leg_seeded_roll_full_writes(
        monkeypatch) -> None:
    """赠卡锁分支四笔同窗写(T-33 设计 §4 锁 2):固定种子 → bench 追加
    1 张 2★ 且名 ∈ 5 费规格池、uid 非空(发号 0→1);锁记录 =
    ((名, uid, (3,4)),)(默认表,(1,1) 步进 19);done 含
    deploy_lock_uid#<uid>;效果串两行(env_gift_random:/env_deploy_lock:
    前缀);期望名从同 seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_DEPLOY_LOCK_GRANTS,
        random_char_pool,
    )
    spec = ENV_DEPLOY_LOCK_GRANTS[_DEPLOY_ENV].spec
    pool = random_char_pool(spec)
    expected = random.Random(20261018).choice(pool)
    gs = _make_gs_node_pos((1, 1))
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False, sig=_SIG,
                            rng=random.Random(20261018))
    assert effects == (f'env_gift_random:{expected}@2star',
                       f'env_deploy_lock:{expected}#uid1@3-4'), '效果串两行'
    placed = [(s.unit.char_id, s.unit.star, s.unit.uid)
              for s in gs.bench.value.slots
              if s is not None and s.kind == 'unit' and s.unit is not None]
    assert placed == [(expected, 2, 1)], '2★ 入席且实例号随行(发号 0→1)'
    assert gs.env_grant_uid_seq.value == 1, '发号计数器落账'
    assert gs.env_grant_deploy_locks.value == \
        ((expected, 1, (3, 4)),), '锁记录 = (名, uid, (1,1)+19 步)'
    assert gs.env_grants_done.value == \
        ((_DEPLOY_ENV, 'deploy_lock_uid#1'),), '完胜作用域键落 done'
    # 四笔相邻写序:发号 → bench 链 → 锁域 → done(同 sig 同 producer)
    assert [c[0] for c in calls] == [
        'env_grant_uid_seq', 'bench', 'env_grant_deploy_locks',
        'env_grants_done'], f'四笔相邻写: {calls}'
    assert calls[0][1] == f'on_env_gained:{_DEPLOY_ENV}#uid', '发号笔 evidence'
    assert calls[2][1] == f'env_deploy_lock:{_DEPLOY_ENV}', '锁域 evidence'
    assert calls[3][1] == (f'env_deploy_lock:{_DEPLOY_ENV}'
                           f'#accel_scope'), '作用域键 evidence'
    assert all(c[3] == _SIG for c in calls), '同 sig(同窗相邻)'
    assert all(c[4] == GAIN_CHAIN_PRODUCER for c in calls), '同 produced_by'


def test_deploy_lock_grant_leg_unanchored_window_default_base() -> None:
    """未锚定窗防御(T-33 设计 §4 锁 3):生效序位 None(开局段结构性,
    环境选择先于节点锚定)→ 解锁序位仍 (3,4)(防御基准 (1,1) 步进
    19);赠卡与发号照常。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_DEPLOY_LOCK_GRANTS,
        random_char_pool,
    )
    pool = random_char_pool(ENV_DEPLOY_LOCK_GRANTS[_DEPLOY_ENV].spec)
    expected = random.Random(3).choice(pool)
    gs = _make_gs_node_pos(None)
    effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False, sig=_SIG,
                            rng=random.Random(3))
    assert effects == (f'env_gift_random:{expected}@2star',
                       f'env_deploy_lock:{expected}#uid1@3-4'), \
        '未锚定窗解锁位 = (1,1) 基准 + 19 步'
    assert gs.env_grant_deploy_locks.value == ((expected, 1, (3, 4)),)


def test_deploy_lock_grant_leg_rng_explicit_and_replay() -> None:
    """rng 链(T-33 设计 §4 锁 4,继承 T-10 支语义):同 seed 重放同名
    确定(全链掷骰单一来源);显式传入优先(两次不同显式 rng = 各自
    现算期望名,互不一致即证非共享全局源)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_DEPLOY_LOCK_GRANTS,
        random_char_pool,
    )
    pool = random_char_pool(
        ENV_DEPLOY_LOCK_GRANTS[_DEPLOY_ENV].spec)

    def _pick(seed: int) -> tuple[str, tuple]:
        gs = _make_gs_node_pos((1, 1))
        effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False,
                                sig=_SIG, rng=random.Random(seed))
        return effects[0].split(':')[1].split('@')[0], \
            gs.env_grant_deploy_locks.value

    n1, locks1 = _pick(11)
    n2, locks2 = _pick(11)
    assert n1 == n2 and locks1 == locks2, '同 seed 重放确定'
    assert n1 in pool, '掷骰名 ∈ 规格池'
    n3, _ = _pick(12)
    expected12 = random.Random(12).choice(pool)
    assert n3 == expected12, '显式 rng 优先(期望名从同 seed 现算)'


def test_deploy_lock_grant_leg_overflow_decoupled(monkeypatch) -> None:
    """溢出解耦(T-33 设计 §4 锁 9):bench 满 + 溢出位被占 →
    gain_character 零写留证(bench/overflow 零新写),锁记录 + done 照写
    (发放事实成立、placed=False 留证,check_env_battle_grants 同口径)。"""
    gs = _make_gs_node_pos((1, 1))
    units = [f'剧本单位{i}' for i in range(9)]
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=Unit(char_id=n, star=1))
               for n in units], capacity=9), sig=_SIG_OBS)
    gs.write_logic(gs.overflow_warning, True, produced_by='seed',
                   evidence='t:ovf', sig=_SIG)
    gs.write_logic(gs.overflow_card, '占位道具', produced_by='seed',
                   evidence='t:ovf', sig=_SIG)
    calls = _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _DEPLOY_ENV, rand=False, sig=_SIG,
                            rng=random.Random(5))
    assert len(effects) == 2, '效果串照常两行(发放事实登记)'
    assert effects[0].startswith('env_gift_random:')
    assert [c[0] for c in calls] == [
        'env_grant_uid_seq', 'env_grant_deploy_locks', 'env_grants_done'], \
        f'bench 拒落下零 bench 写,发号/锁域/done 照写: {calls}'
    assert gs.env_grant_deploy_locks.value[0][2] == (3, 4), '锁记录照写'
    assert gs.env_grants_done.value == ((_DEPLOY_ENV,
                                         'deploy_lock_uid#1'),), 'done 照写'
    kept = [s.unit.char_id for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]
    assert kept == units, 'bench 零写(溢出位被占拒落)'


def test_non_registered_env_stays_quiet(monkeypatch) -> None:
    """表外环境安静不写(T-33 设计 §4 锁 11;早退出口改形回归半边):
    INVESTMENT_ENVS 已登记但零登记表命中(轮岗)→ 效果串恒空逐位不变
    (() 形态)、零字段写操作——赠卡锁分支为表外环境零写径。"""
    gs = _make_gs_node_pos((1, 1))
    calls = _record_writes(gs, monkeypatch)
    seq_before = gs.write_seq
    effects = on_env_gained(gs, None, '轮岗', rand=False, sig=_SIG)
    assert effects == (), '表外环境效果串恒空(() 逐位不变)'
    assert not calls, f'零字段写操作: {calls}'
    assert gs.write_seq == seq_before, '安静不写'


# ============================================================ 延迟道具支线
# (环境「战利品区倒计时件」获得分支;设计稿(原件已退役)
# T-34 命运礼物设计 §2.3 + §4 锁 2/3/9。解锁位数学:获得刻生效序位 (1,1)
# 沿默认表步进 12 步 = (2,4)(计数起点 = 获得节点计入,设计裁决点 3)。)

_DELAYED_ENV = '命运礼物'


def test_delayed_item_grant_leg_enqueues_zero_seat_write(
        monkeypatch) -> None:
    """到手分支入队(T-34 设计 §4 锁 2):获得命运礼物 → 队列 =
    (('惊喜盒', (2, 4)),)((1,1) 步进 12)+ 效果串 item_open_scheduled:
    惊喜盒@2-4 + done 含 (命运礼物, delayed_open_accel);**零席位写**
    (占席证伪锁:bench/overflow/equips 任何字段零写,惊喜盒 = 战利品区
    浮动件非占席)——字段写操作恰两笔:队列(rand 通道,链收尾)+ done
    (logic 直写,登记事实)。"""
    gs = _make_gs_node_pos((1, 1))
    calls = _record_writes(gs, monkeypatch)
    bench_before = gs.bench.value
    effects = on_env_gained(gs, None, _DELAYED_ENV, rand=False, sig=_SIG)
    assert effects == ('item_open_scheduled:惊喜盒@2-4',), '效果串单行'
    assert gs.pending_item_opens.value == (('惊喜盒', (2, 4)),), \
        '队列登记 = (件名, (1,1)+12 步)'
    assert gs.env_grants_done.value == \
        ((_DELAYED_ENV, 'delayed_open_accel'),), '完胜加速作用域键落 done'
    assert gs.bench.value == bench_before, 'bench 逐位不变(零席位写)'
    assert gs.overflow_card.value is None, 'overflow 零写'
    assert gs.equips.value is None, 'equips 零写'
    assert [(c[0], c[1], c[2], c[4]) for c in calls] == [
        ('pending_item_opens', f'on_env_gained:{_DELAYED_ENV}#open_queue',
         'rand', GAIN_CHAIN_PRODUCER),
        ('env_grants_done', f'on_env_gained:{_DELAYED_ENV}#accel_scope',
         'logic', GAIN_CHAIN_PRODUCER),
    ], f'字段写操作恰两笔(队列链收尾 + done 直写): {calls}'
    assert all(c[3] == _SIG for c in calls), '同 sig(同窗相邻)'


def test_delayed_item_grant_leg_modified_schedule_and_terminal_hold(
        ) -> None:
    """解锁位修饰局与局终停留(T-34 设计 §4 锁 3):人身意外险规则
    (P1=10,resolve_plane_node_seqs 注册表现算单一源)下 (1,1) 步进
    12 步 = (2,3)——序差不随位面长度预测漂移;日程过短((3,3) 后无
    后继)→ 步进遇 None 停留最后合法值 (3,3)。"""
    from sr_od.application.currency_war.kernel.cw_node_schedule import (
        resolve_plane_node_seqs,
    )
    gs = _make_gs_node_pos((1, 1))
    gs.write_logic(gs.node_seq_by_plane,
                   resolve_plane_node_seqs('人身意外险'),
                   produced_by='seed', evidence='t:seqs', sig=_SIG)
    effects = on_env_gained(gs, None, _DELAYED_ENV, rand=False, sig=_SIG)
    assert gs.pending_item_opens.value == (('惊喜盒', (2, 3)),), \
        '修饰局 (1,1)+12 步 = (2,3)'
    assert effects == ('item_open_scheduled:惊喜盒@2-3',)
    gs2 = _make_gs_node_pos((1, 1))
    gs2.write_logic(gs2.node_seq_by_plane,
                    {1: ('battle',) * 3, 2: ('battle',) * 3,
                     3: ('battle',) * 3},
                    produced_by='seed', evidence='t:seqs', sig=_SIG)
    on_env_gained(gs2, None, _DELAYED_ENV, rand=False, sig=_SIG)
    assert gs2.pending_item_opens.value == (('惊喜盒', (3, 3)),), \
        '局终方向无后继:停留最后合法值'


def test_delayed_item_grant_leg_repeat_gain_two_entries_scope_once(
        ) -> None:
    """重复获得(T-34 设计 §4 锁 9 入队半边):结构性可达的重复获得 →
    队列两条独立条目(弹除/回退各自独立),done 加速键幂等只写一次。"""
    gs = _make_gs_node_pos((1, 1))
    on_env_gained(gs, None, _DELAYED_ENV, rand=False, sig=_SIG)
    on_env_gained(gs, None, _DELAYED_ENV, rand=False, sig=_SIG)
    assert gs.pending_item_opens.value == \
        (('惊喜盒', (2, 4)), ('惊喜盒', (2, 4))), '队列两条独立条目'
    assert gs.env_grants_done.value == \
        ((_DELAYED_ENV, 'delayed_open_accel'),), 'done 幂等不重写'


# ============================================================ 专家研讨会
# (环境道具双件发放 = bookcard 槽件发放首例;设计稿(原件已退役))

_EXPERT_ENV = '专家研讨会'


def _make_gs_seeded() -> GameState:
    """直构 + 开局初始值(设计锁 2 前置:直构不种初始值 = bench 未观察
    拒落零写;种子初始值单一源 = seed_opening_state)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        seed_opening_state,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    return gs


def test_expert_seminar_dual_item_grants_card_text_order(
        monkeypatch) -> None:
    """发放分支(T-39 设计 §2.1/§2.4 + §4 锁 2):种子初始值直构 → 选专家
    研讨会 → bench 落两槽,kind 序 = ['bookcard', 'supply_box'] 且 item 名
    逐槽 = ['专家邀请函', '简易武装箱'](卡文序);效果串两行
    ``item_gift:<名>`` 顺序同卡文(发放事实恒登记)。"""
    gs = _make_gs_seeded()
    _record_writes(gs, monkeypatch)
    effects = on_env_gained(gs, None, _EXPERT_ENV, rand=False, sig=_SIG)
    assert effects == ('item_gift:专家邀请函', 'item_gift:简易武装箱'), \
        '效果串两行顺序同卡文'
    placed = [(s.kind, s.item) for s in gs.bench.value.slots
              if s is not None and s.kind != 'empty']
    assert placed == [('bookcard', '专家邀请函'),
                      ('supply_box', '简易武装箱')], \
        f'两槽卡文序落席(kind+item 逐槽): {placed}'


# ============================================================ 条件形态调用点④
# (advisor 分道条件形态支,首例 = 特邀专家:银狼;T-42 设计 §2.4 + §4 锁 5。
# 环境获得时刻在场判定 = 备战 ∪ 上阵 ∪ 溢出位;开局获得形态 deployed 恒空,
# 中途获得形态 deployed 现读是判定域组成部分——两臂都锁。)

_ENV_EXPERT_WOLF = '特邀专家:银狼'


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾;
    先例 = kernel/test_gain_chain.py 同族 fixture)。"""

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


def _make_conditional_gs(*, bench: list[tuple[str, int]] | None = (),
                         front: list[Unit] | None = None,
                         overflow_card: str | None = None) -> GameState:
    """条件形态局状态容器(bench None = 保持未观察,供 fail-closed 臂)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if front is not None:
        gs.observe(gs.deployed, deployed_view_sequential(front, [],
                                                        back_capacity=6),
                   sig=_SIG_OBS)
    if overflow_card is not None:
        gs.observe(gs.overflow_card, overflow_card, sig=_SIG_OBS)
        gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    return gs


def test_seed_start_lv999_unlocks_on_env_gain(rows_sink: _RowSink) -> None:
    """种子起手解锁(设计 §4 锁 5 主分支,锁裁定④防误改回「种子不解锁」):
    开局 bench 已含银狼LV.999,获得环境特邀专家:银狼 → 调用点④在场判定
    解锁,效果串 advisor_unlock:特邀专家:银狼:银狼(与即时形态同形);
    解锁 evidence = 环境获得族后缀(provenance 由环境名可辨)。"""
    gs = _make_conditional_gs(bench=[('银狼LV.999', 1)])
    out = gain_invest_env(gs, None, _ENV_EXPERT_WOLF, rand=False, sig=_SIG)
    assert out.effects == (f'advisor_unlock:{_ENV_EXPERT_WOLF}:银狼',), \
        f'命中效果串: {out.effects}'
    assert gs.unlocked_experts.value == ('银狼',), '解锁写入'
    assert gs.unlocked_experts.evidence == \
        f'on_env_gained:{_ENV_EXPERT_WOLF}#expert_unlock', 'evidence 族后缀'
    assert rows_sink.kinds() == [], '命中路径零缺陷行'


def test_seed_without_lv999_keeps_empty_tail(rows_sink: _RowSink) -> None:
    """种子无目标名不解锁(设计 §4 锁 5 条 2):在场判定未命中 → 零写,
    效果串维持现值空尾(事实申报,空尾即「条件形态未触发」的自然读法);
    环境获得后的首次获得走三渠道(两调用点无缝衔接,此处只锁未命中形态)。"""
    gs = _make_conditional_gs(bench=[('火花', 1)])
    out = gain_invest_env(gs, None, _ENV_EXPERT_WOLF, rand=False, sig=_SIG)
    assert out.effects == (f'advisor_unlock:{_ENV_EXPERT_WOLF}:',), \
        '空尾效果串维持'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写'
    assert rows_sink.kinds() == [], '未命中非缺陷,零台账行'


def test_bench_unobserved_fails_closed_with_defect(
        rows_sink: _RowSink) -> None:
    """bench 未观察 fail-closed(设计 §4 锁 5 条 3):不判零写 + 缺陷
    保留证据行(新 kind gain_chain_cond_bench_unobserved);种子初始值下
    生产实机(live)和模拟器(sim)两边不可达(开局种子恒种 bench),直构/测试形态防御。"""
    gs = _make_conditional_gs(bench=None)
    out = gain_invest_env(gs, None, _ENV_EXPERT_WOLF, rand=False, sig=_SIG)
    assert out.effects == (f'advisor_unlock:{_ENV_EXPERT_WOLF}:',), \
        'fail-closed 维持空尾效果串'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写'
    assert rows_sink.kinds() == ['gain_chain_cond_bench_unobserved'], \
        f'缺陷行分键: {rows_sink.kinds()}'


def test_presence_covers_deployed_and_overflow(rows_sink: _RowSink) -> None:
    """在场判定三域(设计 §4 锁 5 条 4):deployed 持有(中途获得形态)
    与溢出位持有(席满溢出)均计入判定域 → 环境获得即解锁。"""
    gs_dep = _make_conditional_gs(bench=[], front=[Unit(char_id='银狼LV.999',
                                                        star=1)])
    out_dep = gain_invest_env(gs_dep, None, _ENV_EXPERT_WOLF, rand=False,
                              sig=_SIG)
    assert out_dep.effects == (f'advisor_unlock:{_ENV_EXPERT_WOLF}:银狼',)
    assert gs_dep.unlocked_experts.value == ('银狼',), 'deployed 在场命中'
    gs_ovf = _make_conditional_gs(bench=[], overflow_card='银狼LV.999')
    out_ovf = gain_invest_env(gs_ovf, None, _ENV_EXPERT_WOLF, rand=False,
                              sig=_SIG)
    assert out_ovf.effects == (f'advisor_unlock:{_ENV_EXPERT_WOLF}:银狼',)
    assert gs_ovf.unlocked_experts.value == ('银狼',), '溢出位在场命中'
    assert rows_sink.kinds() == [], '命中路径零缺陷行'


# ============================================================ 词缀失效删除分支
# (敌后破坏 id 146;设计稿(原件已退役)(已退役账本
# calc/设计稿(原件已退役;判据 = 本文件锁面申报))§2.1 + §4 锁 1/2/6:删除式建模——
# 词缀名单非空时均匀随机删 1、剩余列表整条替换写回(经 _select_write
# 择道,rand=True 双保险声明采样链);空状态容器零写 + 申报行;装备佩戴豁免
# 跟随删除后值。HP 先验跟随锁面归 kernel/test_cw_opening_hp.py(回调
# 宿主镜像),sim 追加链锁面归 sim/cw_sim_backend/(流程级镜像)。)

_AFFIX_ENV = ENV_AFFIX_DISABLE_ENV


def _make_affix_gs(affixes: list[str] | None) -> GameState:
    """词缀名单直写状态容器(logic 直写;old=None 首写,HP 回调种子档零触发)。"""
    gs = _make_gs()
    if affixes is not None:
        gs.write_logic(gs.enemy_affixes, list(affixes), produced_by='seed',
                       evidence='t:affix', sig=_SIG)
    return gs


def _with_slot_rng(seed: int):
    """动作分支采样注入槽临时装配(上下文管理器,退出即关;
    删除分支经 action_sampling_rng('env_affix_disable', None) 取槽)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        set_action_rng_provider,
    )

    class _Slot:
        def __enter__(self) -> None:
            set_action_rng_provider(lambda tool: random.Random(seed))

        def __exit__(self, *exc) -> None:
            set_action_rng_provider(None)

    return _Slot()


def test_affix_disable_deletion_leg_random_state_write(monkeypatch) -> None:
    """删除采样分支四断言(T-45 设计 §4 锁 1):rng 注入定值下选敌后破坏 →
    ①enemy_affixes 长度 -1(采样命中名整条移除,剩余整条替换);②来源
    logic_rand(rand=True 声明采样链);③logic_rand_fields() 含
    enemy_affixes(补观察谓词消费口);④效果串 env_affix_disable:<名>
    在账。期望名从同 seed 现算(单一来源,不手抄)。"""
    affixes = ['开局不利', '库藏生锈', '灼热轰炸']
    expected_removed = random.Random(7).choice(affixes)
    gs = _make_affix_gs(affixes)
    calls = _record_writes(gs, monkeypatch)
    with _with_slot_rng(7):
        effects = on_env_gained(gs, None, _AFFIX_ENV, rand=False, sig=_SIG)
    assert effects == (f'env_affix_disable:{expected_removed}',), '④效果串'
    kept = list(affixes)
    kept.remove(expected_removed)
    assert gs.enemy_affixes.value == kept, '①长度 -1 且整条替换'
    assert gs.enemy_affixes.source == 'logic_rand', '②来源 logic_rand'
    assert 'enemy_affixes' in gs.logic_rand_fields(), '③随机态字段已登记'
    rows = [(c[0], c[1], c[2], c[4]) for c in calls
            if c[0] == 'enemy_affixes']
    assert rows == [('enemy_affixes',
                     f'on_env_gained:{_AFFIX_ENV}#affix_disable',
                     'rand', GAIN_CHAIN_PRODUCER)], f'写行形态: {rows}'


def test_affix_disable_slot_scoped_to_hit(monkeypatch) -> None:
    """采样分支具名流键命中前置(T-45 设计 §2.1 仿 env_merge_grant 形态):
    注入槽只在敌后破坏命中时取一次且键名精确;他环境(表外轮岗)零取槽
    ——不扰他局流键序。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        set_action_rng_provider,
    )
    taken: list[str] = []

    def _spy(tool: str):
        taken.append(tool)
        return random.Random(0)

    set_action_rng_provider(_spy)
    try:
        on_env_gained(_make_affix_gs(['开局不利']), None, '轮岗',
                      rand=False, sig=_SIG)
        assert taken == [], '表外环境零取槽'
        on_env_gained(_make_affix_gs(['开局不利']), None, _AFFIX_ENV,
                      rand=False, sig=_SIG)
        assert taken == [ENV_AFFIX_DISABLE_RNG_TOOL], \
            f'命中恰取一次且键精确: {taken}'
    finally:
        set_action_rng_provider(None)


def test_affix_disable_empty_container_zero_write_with_decl(
        monkeypatch, rows_sink: _RowSink) -> None:
    """空状态容器边界(T-45 设计 §4 锁 2):状态容器空(直构未写)时选敌后破坏 →
    零字段写操作 + 申报行已登记(kind = env_affix_disable_empty_container,
    实机已失效而模型未删的偏差申报),零效果串。"""
    gs = _make_affix_gs(None)
    calls = _record_writes(gs, monkeypatch)
    seq_before = gs.write_seq
    effects = on_env_gained(gs, None, _AFFIX_ENV, rand=False, sig=_SIG)
    assert effects == (), '零效果串(未发生删除)'
    assert not calls, f'零字段写操作: {calls}'
    assert gs.write_seq == seq_before, '安静不写'
    assert rows_sink.kinds() == ['env_affix_disable_empty_container'], \
        f'申报行分键: {rows_sink.kinds()}'


def test_affix_disable_rust_release_unfollows() -> None:
    """豁免跟随(T-45 设计 §4 锁 6):删除「库藏生锈」→ 装备佩戴豁免
    解除——消费面 = build_equip_env_signals 全量读状态容器自动跟随,rust
    豁免判据(row4)删除前在场/删除后解除。seed 经现算取命中名(探针:
    s ∈ [0,100) 内存在 choice(['库藏生锈','灼热轰炸'])=='库藏生锈' 的
    seed,循环现算不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_equip_env import (
        build_equip_env_signals,
        rust_release_active,
    )
    affixes = ['库藏生锈', '灼热轰炸']
    seed = next(s for s in range(100)
                if random.Random(s).choice(affixes) == '库藏生锈')
    gs = _make_affix_gs(affixes)
    before = rust_release_active(
        sorted(build_equip_env_signals(gs).enemy_affixes), True)
    assert before is True, '删除前:生锈在场 → hold 豁免生效'
    with _with_slot_rng(seed):
        effects = on_env_gained(gs, None, _AFFIX_ENV, rand=False, sig=_SIG)
    assert effects == ('env_affix_disable:库藏生锈',), '删除命中生锈'
    after = rust_release_active(
        sorted(build_equip_env_signals(gs).enemy_affixes), True)
    assert after is False, '删除后:豁免解除(名单自动跟随)'


# ============================================================ 概念股族
# (阵营随机赠卡 + 随机简易装备;权威版本 = game_state/gain-chain.md §3 随机支
# /随机装备支段 + fields.md §5.2 效果缺口与载体登记,语义 = 「概念股族
# 模式卡登记约定」。绑定门:ENV_BOSS_GRANTS 成员(劳务派遣合同)绑定态
# 行为逐位不变 = 存量 kernel/test_gain_chain.py 随机装备通道段三锁辖域,
# 此处只锁非绑定态(追击概念股)。)

_CONCEPT_ENV = '追击概念股'


def _make_gs_with_equips() -> GameState:
    """直构状态容器(bench 9 空槽 + equips 空库):装备入账分支接收面。"""
    gs = _make_gs()
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return gs


def test_concept_stock_faxis_char_grant_branch(rows_sink: _RowSink) -> None:
    """阵营支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库时点池掷骰,
    两族同一循环同一前缀):固定种子 rng 直构 → bench 追加 1 张 1★ 且名
    ∈ 阵营池现算集(grant_char_pool 阵营 spec = 规格域 ∩ 当时牌库,未解锁
    专家剔除,注册表派生不手抄);效果串 ``env_gift_random:<名>@1star``
    (星级 = spec.star 先验);锚定状态容器 + 采样子链 rand=True → 写照常生效
    且不进失配网(随机态语义,首观察静默覆盖)。期望名从同 seed 现算
    (单一来源,不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(gs, ENV_GIFTS[_CONCEPT_ENV].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _CONCEPT_ENV, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_concept_stock_random_equip_leg_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态(gain-chain.md §3 随机装备支段:非 ENV_BOSS_GRANTS
    成员零绑定):追击概念股(非成员)随机装备入账分支 → 效果串
    ``env_equip_random:<名>`` 前缀(与绑定态 ``env_star_grant:`` 分域)、
    env_grants_done 无 star_grant# 键(非成员零绑定写,治「无条件绑定
    等第二个消费者」缺陷);装备照常入栏且名 ∈ 类别池现算集
    (equips_by_category('简易') 注册表派生,不手抄)。两条分支期望值从同
    seed 现算(字符分支先掷、装备入账分支同 rng 续掷,与生产消费序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_CONCEPT_ENV].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _CONCEPT_ENV, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


# 族展开第二实例(燃血概念股 id 1002;概念股族展开卡登记约定,权威版本 =
# fields.md §5.2 效果缺口与载体登记 + gain-chain.md §3 随机支/随机装备支
# 段,与追击同构仅值异。)

_RANXUE_ENV = '燃血概念股'


def test_ranxue_concept_stock_faction_char_grant_branch(
        rows_sink: _RowSink) -> None:
    """燃血域随机支发放分支(gain-chain.md §3 随机支段:阵营轴 = 牌库时点
    池掷骰,两族同一循环同一前缀;概念股族展开卡登记约定):固定种子 rng
    直构 → bench 追加 1 张 1★ 且名 ∈ 阵营池现算集(grant_char_pool 阵营
    spec = 规格域 ∩ 当时牌库,未解锁专家剔除,注册表派生不手抄);效果串
    ``env_gift_random:<名>@1star``(星级 = spec.star 先验);锚定状态容器 +
    采样子链 rand=True → 写照常生效且不进失配网(随机态语义,首观察
    静默覆盖)。期望名从同 seed 现算(单一来源,不手抄)。"""
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    gs.prep_anchored = True
    pool = grant_char_pool(
        gs, ENV_GIFTS[_RANXUE_ENV].chars_random_immediate[0])
    expected = random.Random(20261027).choice(pool)
    out = on_env_gained(gs, None, _RANXUE_ENV, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out[0] == f'env_gift_random:{expected}@1star', '效果串前缀+星级'
    assert _bench_units(gs) == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


def test_ranxue_concept_stock_random_equip_leg_unbound_no_done(
        rows_sink: _RowSink) -> None:
    """绑定门非绑定态第二实例(gain-chain.md §3 随机装备支段:非
    ENV_BOSS_GRANTS 成员零绑定;概念股族展开卡登记约定):燃血概念股
    (非成员)随机装备入账分支 → 效果串 ``env_equip_random:<名>`` 前缀(与
    绑定态 ``env_star_grant:`` 分域)、env_grants_done 无 star_grant#
    键(非成员零绑定写,治「无条件绑定等第二个消费者」缺陷);装备
    照常入栏且名 ∈ 类别池现算集(equips_by_category('简易') 注册表派生,
    不手抄)。两条分支期望值从同 seed 现算(字符分支先掷、装备入账分支同 rng 续掷,
    与生产消费序一致)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
    gs = _make_gs_with_equips()
    r = random.Random(20261027)
    expected_char = r.choice(grant_char_pool(
        gs, ENV_GIFTS[_RANXUE_ENV].chars_random_immediate[0]))
    expected_eq = r.choice(equips_by_category('简易'))
    out = on_env_gained(gs, None, _RANXUE_ENV, rand=False, sig=_SIG,
                        rng=random.Random(20261027))
    assert out == (f'env_gift_random:{expected_char}@1star',
                   f'env_equip_random:{expected_eq}'), \
        '两条分支效果串:非绑定前缀 env_equip_random:'
    assert gs.equips.value == [expected_eq], '装备入栏(类别池现算)'
    assert gs.env_grants_done.value is None, \
        '非绑定态零 done 键(无 star_grant# 绑定)'
    assert rows_sink.kinds() == [], '正常路径零申报行'
