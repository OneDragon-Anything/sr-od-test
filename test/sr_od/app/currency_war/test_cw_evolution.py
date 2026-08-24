"""阵容演进引擎(契约包 C3,步 4 第一批 W33)单帧锁测试。

契约来源:`.debug/temp/currency_war/cw_dev/deep_read/契约包_C1-C7.md` C3 节
+ `转型讨论.md`(演进法则单一源:三条件/统一入口四步/两步解耦/空位规则/
中断恢复)+ `strategy_v4.md` 点6/点11。

锁验收(C3「验收测试想法」1-4):
1. DOT2→仙舟3 整档替换(引 W26 test_cw_action_v2 的构造法):旧档 0 在场/
   新档全员/无半档/发令枪序;
2. 2换1 触发与不触发(档未到 2 档 → bench 等,不出事务);
3. 空位规则:插件优先 vs 替班核心例外 vs 真核心 bench 等档 + 禁用矩阵;
4. 中断恢复:冻结打断=三条件重校验(成立执行/破坏作废);谷底回滚=回滚
   一件最弱替换位后放缓。
"""
from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_evolution import (
    EvolutionState,
    evaluate_upgrade,
    evolution_step,
    fill_gap_after,
    fill_slot_policy,
    propose_upgrades,
    rollback_weakest,
)
from sr_od.application.currency_war.cw_line_defs import _CORE_TRIO
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    CompTransaction,
    FillSpec,
    GameState,
    SellDeployed,
    SwapDeploy,
    _recount_board,
    simulate,
)


def _char(name: str, faction: str | None = None, row: str | None = None,
          star: int = 1) -> BenchChar:
    """注册表真值构造 BenchChar(faction/站位单一源;faction 可覆写流派口径)。"""
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=faction or (c.factions or ['?'])[0],
                     position_pref=row or c.position_pref(), star=star)


def _dot2_state() -> GameState:
    """DOT2 在场(持续伤害 3 人)+ 仙舟铁三角 bench 齐(验收1 构造,W26 同法)。"""
    st = GameState()
    st.gold = 20
    st.level = 8
    st.deployed = [_char(n, '持续伤害')
                   for n in ('桑博', '艾丝妲', '卡芙卡')]
    st.bench = [_char(n, '仙舟') for n in sorted(_CORE_TRIO)]
    st.board = _recount_board(st.deployed)
    return st


def _run_evolution(st: GameState) -> tuple[list, EvolutionState]:
    mem = EvolutionState()
    actions = evolution_step(st, None, mem)
    return actions, mem


# ---------- 1. DOT2 → 仙舟3 整档替换(统一入口四步闭环) ----------

def test_evolution_dot2_to_xianzhou3_full_replacement():
    st = _dot2_state()
    actions, mem = _run_evolution(st)
    assert len(actions) == 1
    tx = actions[0]
    assert isinstance(tx, CompTransaction)
    assert '仙舟3' in tx.reason and '持续伤害' in tx.reason
    out = simulate(st, tx)
    # 旧档 0 人在场:铁三角全员上阵
    names = {d.char_id for d in out.deployed}
    assert set(_CORE_TRIO) <= names
    assert '桑博' not in names and '卡芙卡' not in names
    # 无半档:board 与 deployed 聚合一致;旧档主力转 bench(回滚窗,非卖)
    assert out.board == _recount_board(out.deployed)
    assert out.board['仙舟'] >= 3
    bench_names = {b.char_id for b in out.bench}
    assert {'桑博', '卡芙卡'} <= bench_names   # 保回滚窗:退役暂缓 bench 非卖出
    assert tx.sell == []   # bench 有余量 → 零卖出
    # 账本 applied + 原状态不动(simulate 纯函数)
    assert out.action_log[-1]['result'] == 'applied'
    assert len(st.deployed) == 3 and len(st.bench) == 3
    # memory 记录回滚窗锚
    assert set(mem.last_deployed) == set(_CORE_TRIO)
    assert {'桑博', '卡芙卡', '艾丝妲'} <= set(mem.last_retained)


def test_propose_and_evaluate_best_is_xianzhou_card():
    st = _dot2_state()
    opts = propose_upgrades(st)
    # 仙舟3 体系卡机会在列:核心在场 + 引擎完备评分最高
    xz = [o for o in opts if o.comp_name == 'xianzhou3']
    assert len(xz) == 1 and xz[0].core_present is True
    verdict = evaluate_upgrade(xz[0], st)
    assert verdict.execute and verdict.effect_ok and verdict.core_ok
    # 发令枪序锁:核心先到档未齐 → bench 等(构造:核心在 bench、档不足 2)
    st2 = GameState()
    st2.gold = 20
    st2.level = 6
    st2.deployed = [_char('桑博', '持续伤害')]   # 仙舟 0 件
    st2.bench = [_char('藿藿', '仙舟')]           # 仅 1 件:档未到 2
    st2.board = _recount_board(st2.deployed)
    v2 = evaluate_upgrade(evaluate_upgrade(xz[0], st).option, st2)
    assert not v2.execute and 'bench 等' in v2.detail


def test_gun_order_faction_ready_core_missing_no_dismantle():
    """档齐核心未到 → 不拆过渡档(发令枪 = 最后到齐的那个)。"""
    st = _dot2_state()
    # 拿走全部铁三角(核心不在手),仙舟档位用 3 个非核心仙舟件顶上
    st.bench = [_char(n, '仙舟') for n in ('青雀', '符玄', '彦卿')]
    actions, _ = _run_evolution(st)
    # 仙舟3 卡:档在手 3 ≥2 但核心(铁三角)0 在手 → 不出事务
    assert all(not isinstance(a, CompTransaction) for a in actions) \
        or actions == []
    xz = [o for o in propose_upgrades(st) if o.comp_name == 'xianzhou3']
    v = evaluate_upgrade(xz[0], st)
    assert not v.execute and '不拆过渡档' in v.detail


# ---------- 2. 2换1 触发与不触发 ----------

def test_two_swap_one_gate():
    """目标羁绊在手 ≥2(2 档成型)才替换;1 件 → 不触发。"""
    st = _dot2_state()
    st.bench = [_char('藿藿', '仙舟')]   # 仙舟仅 1 件:2换1 不触发
    actions, _ = _run_evolution(st)
    assert actions == []
    xz = [o for o in propose_upgrades(st) if o.comp_name == 'xianzhou3']
    assert xz and not evaluate_upgrade(xz[0], st).execute


def test_two_swap_one_gap_window_proxy():
    """缺口 1 张 + 店里可见(再遇窗口代理)→ 触发;店里没有 → 不触发。"""
    st = _dot2_state()
    st.bench = [_char(n, '仙舟') for n in ('藿藿', '爻光')]   # 在手 2,目标 3
    from sr_od.application.currency_war.cw_state import ShopCard
    st.shop = [ShopCard(x=0, faction='仙舟', name='丹恒·饮月', cost=2)]
    actions, _ = _run_evolution(st)
    assert len(actions) == 1 and isinstance(actions[0], CompTransaction)
    # 窗口关闭(店空):缺口 1 张无再遇窗口 → 不触发
    st2 = _dot2_state()
    st2.bench = [_char(n, '仙舟') for n in ('藿藿', '爻光')]
    st2.shop = []
    actions2, _ = _run_evolution(st2)
    assert not any(isinstance(a, CompTransaction) for a in actions2)


# ---------- 3. 空位规则:插件优先 / 替班例外 / 真核心等档 / 禁用矩阵 ----------

def test_fill_gap_plugin_priority_over_filler():
    """插件(单卡 T1)优先于散件;真核心 bench 等档不填散位。"""
    st = GameState()
    st.gold = 10
    st.level = 8
    st.deployed = [_char(n, '仙舟') for n in sorted(_CORE_TRIO)]
    st.board = _recount_board(st.deployed)
    st.bench = [_char('知更鸟'),   # 插件单卡 T1(盛会之星,非骨架线)
                _char('娜塔莎')]   # 散件(非插件;贝洛伯格治疗)
    fills = fill_slot_policy(st)
    assert fills and fills[0].source == 'bench'
    first = st.bench[fills[0].idx]
    assert first.char_id == '知更鸟'   # 插件优先于散件
    tx = CompTransaction([], [], [], reason='t')
    out = simulate(st, tx)
    post_fills = fill_gap_after(tx, out)
    assert [f.idx for f in post_fills] == [f.idx for f in fills]


def test_fill_gap_substitute_exception_beats_plugin():
    """替班核心例外:DOT 线在场时,黑天鹅(替班者)优先于插件。"""
    st = GameState()
    st.gold = 10
    st.level = 7
    st.deployed = [_char('桑博', '持续伤害'), _char('艾丝妲', '持续伤害'),
                   _char('卡芙卡', '持续伤害'), _char('椒丘', '持续伤害')]
    st.board = _recount_board(st.deployed)
    st.bench = [_char('知更鸟'),    # 插件单卡 T1
                _char('黑天鹅', '持续伤害')]   # DOT队 替班者(顶卡芙卡主C)
    fills = fill_slot_policy(st)
    assert fills
    first = st.bench[fills[0].idx]
    assert first.char_id == '黑天鹅'   # 替班核心例外 > 插件优先


def test_fill_gap_disable_matrix_skips_shield_in_wenemy_family():
    """禁用矩阵:万敌燃血家族下盾系插件(砂金)不填位(官方:燃血无法获盾)。"""
    from sr_od.application.currency_war.cw_comps import get_comp
    st = GameState()
    st.gold = 10
    st.level = 7
    st.deployed = [_char('万敌', '夜之半神'), _char('赛飞儿', '夜之半神'),
                   _char('长夜月', '夜之半神')]
    st.board = _recount_board(st.deployed)
    st.bench = [_char('砂金'),      # 盾系单卡 × 万敌燃血 = 硬禁用
                _char('罗刹')]      # 盾外 T2 插件可用
    target = get_comp('万敌单C')   # family='万敌燃血'
    fills = fill_gap_after(CompTransaction([], [], [], reason='t'),
                           st, target)
    assert fills
    picked = [st.bench[f.idx].char_id for f in fills if f.source == 'bench']
    assert '砂金' not in picked
    assert picked[0] == '罗刹'


def test_fill_gap_true_core_waits_on_bench():
    """真核心 bench 等档:未成型线的 carry 不填散位(上场时机=新档成型时机)。"""
    st = GameState()
    st.gold = 10
    st.level = 6
    st.deployed = [_char('桑博', '持续伤害'), _char('艾丝妲', '持续伤害')]
    st.board = _recount_board(st.deployed)
    st.bench = [_char('飞霄'),      # 追击飞霄 carry;追击未成型 → 等档
                _char('灵砂')]      # T3 插件单卡
    fills = fill_slot_policy(st)
    assert fills
    picked = [st.bench[f.idx].char_id for f in fills if f.source == 'bench']
    assert '飞霄' not in picked and picked[0] == '灵砂'


# ---------- 4. 中断恢复 / 谷底回滚 ----------

def test_freeze_on_encounter_recovery_revalidates():
    """遭遇/boss 前冻结不启动新替换;恢复 = 三条件重校验,成立则当轮执行。"""
    st = _dot2_state()
    st.node_type = '遭遇'
    mem = EvolutionState()
    actions = evolution_step(st, None, mem)
    assert actions == []   # 冻结扩到遭遇前
    assert mem.pending is not None and mem.pending.comp_name == 'xianzhou3'
    # 恢复(非遭遇轮):三条件仍成立 → 当轮执行
    st.node_type = '战斗'
    actions2 = evolution_step(st, None, mem)
    assert len(actions2) == 1 and isinstance(actions2[0], CompTransaction)
    assert simulate(st, actions2[0]).action_log[-1]['result'] == 'applied'
    # 恢复但条件破坏(核心被卖)→ 重校验失败,作废不重演
    mem2 = EvolutionState()
    st2 = _dot2_state()
    st2.node_type = '遭遇'
    assert evolution_step(st2, None, mem2) == []
    st2.node_type = '战斗'
    st2.bench = [_char('青雀', '仙舟'), _char('符玄', '仙舟'),
                 _char('彦卿', '仙舟')]   # 铁三角被卖:核心不在手
    actions3 = evolution_step(st2, None, mem2)
    assert not any(isinstance(a, CompTransaction) for a in actions3)
    assert mem2.pending is None   # 那次替换作废


def test_valley_rollback_weakest_then_pause():
    """谷底回滚:回滚一件最弱替换位(SwapDeploy 换回保留件)后放缓。"""
    st = _dot2_state()
    _, mem = _run_evolution(st)
    out = simulate(st, _rebuilt_tx(st, mem))
    # 掉血>15 触发(调用方观测)→ 回滚最弱新档位
    action = rollback_weakest(out, mem)
    assert action is not None and isinstance(action, SwapDeploy)
    assert action.reason == 'valley_rollback'
    assert mem.paused is True
    rolled = simulate(out, action)
    assert rolled.board == _recount_board(rolled.deployed)
    # 回滚后再遇上遭遇轮:暂停生效,不续演进
    rolled.node_type = '遭遇'
    assert evolution_step(rolled, None, mem) == []


def _rebuilt_tx(st: GameState, mem: EvolutionState) -> CompTransaction:
    """从 memory 重建上次替换事务(rollback 测试的消费锚)。"""
    actions, _ = _run_evolution(st)
    assert actions and isinstance(actions[0], CompTransaction)
    return actions[0]


def test_valley_rollback_no_retained_sells_weakest():
    """无 bench 保留件(回滚窗已耗尽)→ 退役最弱新档位(SellDeployed)。"""
    st = _dot2_state()
    _, mem = _run_evolution(st)
    tx = _rebuilt_tx(st, mem)
    out = simulate(st, tx)
    out.bench = []   # 回滚窗耗尽(旧档保留件已清)
    mem.last_retained = []
    action = rollback_weakest(out, mem)
    assert isinstance(action, SellDeployed)
    assert mem.paused is True


# ---------- 边界:DOT 同体线退化为加深 ----------

def test_dot_same_line_degenerates_to_deepen():
    """DOT 同体线:目标羁绊=当前主档 → 无替换(纯加深/无动作),不出整档事务。"""
    st = _dot2_state()
    st.bench = []   # 无仙舟件:唯一机会是 DOT 自身加深,但无 bench 件可上
    actions, _ = _run_evolution(st)
    assert actions == []   # 没有可上新羁绊机会 → 空动作(加深由常规买/上通道)
    # 有 DOT 件在 bench:加深 = 纯 deploy 事务(undeploy/sell 空,无替换)
    st2 = _dot2_state()
    st2.bench = [_char('椒丘', '持续伤害')]
    st2.deployed = [_char('桑博', '持续伤害'), _char('艾丝妲', '持续伤害')]
    st2.board = _recount_board(st2.deployed)
    st2.level = 5
    actions2, _ = _run_evolution(st2)
    if actions2:
        tx = actions2[0]
        assert isinstance(tx, CompTransaction)
        assert tx.undeploy == [] and tx.sell == []   # 加深无替换
        out = simulate(st2, tx)
        assert out.board == _recount_board(out.deployed)
