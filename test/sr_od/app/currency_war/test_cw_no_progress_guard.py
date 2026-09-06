"""环级无进展守卫锁(第 5 局放行硬门)。

设计出处 = .debug/temp/currency_war/redesign/ARCH_REFLECTION_3STALLS.md
问三缺口 G3(prep 环无通用无进展守卫)/ 问四防线①(同签名动作批 +
状态零推进连续 N 环 → 存证 + stop_running)/ 问五放行裁决(守卫是
放行硬门)。触发语义:签名 = 动作类型序列(session.last_prep_action_sig,
CwScreenPrep 决策出口写)+ 状态指纹(prep_no_progress_state_fingerprint,
只读 observe 现成字段);连续 PREP_NO_PROGRESS_ROUNDS=3 环同签名 ∧
零推进 → 截图 + flag + stop_running。取代旧 PREP_STALL_EVIDENCE_ROUNDS
只留证不停机线(单一计数,勿留两套)。

不误伤三判据(与守卫实现注释同源):
①战斗等待期不进备战分支,回备战 round 必变 → 归零;
②正常多帧部署:每次成功动作改变身份/金 → 指纹变 → 归零;
③闩跳过帧:动作批不同 → 签名变 → 归零。
"""

from types import SimpleNamespace

from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

# ==================== 纯函数:计数与指纹 ====================


def _fingerprint_module():
    from sr_od.application.currency_war.operations import cw_loop
    return cw_loop


def _session(plane=1, round_num=5, gold=30, node='battle',
             bench=('a', 'b'), deployed=('c',)):
    """伪 session(守卫只读这些字段;镜像 prep_no_progress_state_fingerprint 契约)。"""
    return SimpleNamespace(
        last_state=SimpleNamespace(plane=plane, round_num=round_num, gold=gold),
        last_node_type=node,
        prep_obs_frame=SimpleNamespace(
            bench_chars=[SimpleNamespace(char_id=c) for c in bench],
            deployed_chars=[SimpleNamespace(char_id=c) for c in deployed],
        ),
    )


def _simulate(rings: list[tuple[tuple[str, ...], object]]) -> tuple[int, bool]:
    """重放备战环序列:(动作批, session 或指纹差异),返回 (末次计数, 是否触发)。

    每环 = cw_loop 备战分支一次守卫判定(动作批 None 模拟 overlay 交回环)。
    """
    m = _fingerprint_module()
    sig_state = None
    count = 0
    triggered = False
    for actions, sess in rings:
        if actions is None:
            sig_state = None
            count = 0
            continue
        fp = sess if isinstance(sess, tuple) else \
            m.prep_no_progress_state_fingerprint(sess)
        sig_state, count = m.prep_no_progress_tick(sig_state, count,
                                                   (actions, fp))
        if count >= m.CwLoop.PREP_NO_PROGRESS_ROUNDS:
            triggered = True
    return count, triggered


def test_tick_accumulates_same_sig_and_resets_on_change() -> None:
    """同签名累加 / 异签名归零(计数器核心语义)。"""
    m = _fingerprint_module()
    s, c = m.prep_no_progress_tick(None, 0, (('A',), (1,)))
    assert (s, c) == ((('A',), (1,)), 0), '首见签名计数从 0 起'
    _, c = m.prep_no_progress_tick(s, c, (('A',), (1,)))
    _, c = m.prep_no_progress_tick(s, c, (('A',), (1,)))
    assert c == 2, '同签名两次重复后计数=2'
    _, c = m.prep_no_progress_tick(s, c, (('A',), (2,)))
    assert c == 0, '指纹变化(状态推进)必须归零'
    _, c = m.prep_no_progress_tick((('A',), (2,)), c, (('B',), (2,)))
    assert c == 0, '动作批变化必须归零'


def test_state_fingerprint_covers_all_progress_fields() -> None:
    """指纹覆盖轮次/节点序/金/deploy 身份任一变化(任务规格:任一变化=推进)。"""
    m = _fingerprint_module()
    base = m.prep_no_progress_state_fingerprint(_session())
    variants = [
        _session(round_num=6),          # 轮次推进
        _session(plane=2),              # 位面推进
        _session(node='supply'),        # 节点序推进
        _session(gold=44),              # 金变化
        _session(bench=('a', 'x')),     # 备战席身份变(同数换人不漏检)
        _session(deployed=('c', 'd')),  # 部署数/身份变
    ]
    for v in variants:
        assert m.prep_no_progress_state_fingerprint(v) != base, (
            f'指纹须随字段变化而变:{v}')


# ==================== 三历史卡死签名重放(守卫必须触发) ====================


def test_replay_m2_open_shop_reignition_loop_triggers() -> None:
    """历史① M2 开店环:OpenShop 批重燃重发、帧状态不变 → 3 环触发。"""
    frozen = _session()
    rings = [(('OpenShop',), frozen)] * 5
    count, triggered = _simulate(rings)
    assert triggered, 'M2 重燃形态必须触发守卫'
    assert count >= 3


def test_replay_m7_equip_loop_triggers() -> None:
    """历史② M7 装备环:RunEquip 批跨帧重发、零变换 → 3 环触发。"""
    frozen = _session()
    rings = [(('OpenShop', 'RunEquip'), frozen)] * 5
    count, triggered = _simulate(rings)
    assert triggered, 'M7 装备环形态必须触发守卫'


def test_replay_partner_overlay_rundeploy_loop_triggers() -> None:
    """历史③ 选择伙伴遮罩 RunDeploy 环:遮罩挡拖拽、op 正常返回、板面不动 → 触发。"""
    frozen = _session()
    rings = [(('RunDeploy',), frozen)] * 5
    count, triggered = _simulate(rings)
    assert triggered, '遮罩 RunDeploy 环形态必须触发守卫'


# ==================== 不误伤:健康序列/战斗等待/闩跳过 ====================


def test_healthy_rotation_never_triggers() -> None:
    """健康轮转:每环 round 或部署/金在变 → 永不触发。"""
    rings = []
    for r in range(10):
        sess = _session(round_num=5 + r // 3, gold=30 + r,
                        deployed=('c',) if r % 2 == 0 else ('c', 'd'))
        rings.append((('OpenShop',), sess))
    _, triggered = _simulate(rings)
    assert not triggered, '状态推进中的同批动作不得触发'


def test_action_variance_with_frozen_state_never_triggers() -> None:
    """状态冻结但动作批在变(闩跳过帧/异构重试)→ 签名变 → 归零,不触发。"""
    frozen = _session()
    rings = [
        (('OpenShop',), frozen),
        (('OpenShop',), frozen),
        (('StartBattle',), frozen),   # 闩抑制后改发出战
        (('OpenShop',), frozen),
        (('OpenShop',), frozen),
        (('OpenShop', 'RunEquip'), frozen),
    ]
    _, triggered = _simulate(rings)
    assert not triggered, '动作批变化 = 签名变化,不得累计触发'


def test_overlay_interlude_and_battle_wait_reset_and_silence() -> None:
    """战斗等待期/overlay 交回环(动作批 None)不累计且中断已累计连击:
    ①纯 None 环长序列不触发;②卡死中插入 None(战斗)后计数清零。"""
    rings = [(None, None)] * 20
    _, triggered = _simulate(rings)
    assert not triggered, '战斗等待/overlay 环必须静默'

    frozen = _session()
    rings = [
        (('RunDeploy',), frozen),
        (('RunDeploy',), frozen),
        (None, None),                 # 中途一场战斗/overlay 交回
        (('RunDeploy',), frozen),
        (('RunDeploy',), frozen),
    ]
    count, triggered = _simulate(rings)
    assert not triggered, 'None 环必须清零计数(战斗静默期不误伤)'


def test_threshold_is_three() -> None:
    """N=3(与旧 PREP_STALL_EVIDENCE_ROUNDS 取值对齐;任务书裁决)。"""
    m = _fingerprint_module()
    assert m.CwLoop.PREP_NO_PROGRESS_ROUNDS == 3


# ==================== 存证 flag(测试零真实副作用:tmp_path) ====================


def test_write_no_progress_flag_content(tmp_path) -> None:
    """flag 三要素:计数 + 签名 + 截图路径,处理流程可执行。"""
    m = _fingerprint_module()
    p = tmp_path / 'prep_no_progress.flag'
    out = m.write_no_progress_flag(3, (('RunDeploy',), (1, 5, 'battle', 30, ('a',), ('c',))),
                                   '<shot>', path=p)
    assert out == str(p)
    text = p.read_text(encoding='utf-8')
    assert '3' in text and 'RunDeploy' in text and '<shot>' in text
    assert '[HOOK-STOP]' in text and '处理流程' in text


# ==================== 接线:备战单轮 op 写签名 / loop 消费 ====================


def _make_round_director(test_context, monkeypatch, scripted_actions,
                         overlay=None):
    """备战单轮单测装配(镜像 test_cw_w971_p3b_seg2 同名 helper 的最小集)。"""
    from types import SimpleNamespace as _SN

    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )

    class _StubStrategy:
        def decide_prep_screen(self, session, config):
            return list(scripted_actions)

        def update_target(self, state, session, config):
            pass

    d = pd_mod.CwScreenPrep(test_context)
    session = StrategySession()
    match = _SN(strategy=_StubStrategy(), session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    monkeypatch.setattr(d, '_clear_entry_overlays', lambda: None)
    monkeypatch.setattr(d, '_try_collapse_open_shop', lambda: False)
    monkeypatch.setattr(d, '_takeover_collect_if_needed', lambda m, s: None)
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)

    class _Obs:
        event_overlay = overlay
        state = None
        bench_chars: list = []
        deployed_chars: list = []
        spheres: list = []
        boxes: list = []
        deploy_vacancy = 0

    monkeypatch.setattr(d, '_observe', lambda heavy=True, screen=None: _Obs())
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_observation.read_bench_full',
        lambda ctx, screen: False)
    monkeypatch.setattr(d, '_open_shop_phase',
                        lambda a, obs: (True, 'read_only 读牌完成'))
    return d, match, session


def test_prep_op_records_action_signature(test_context, monkeypatch) -> None:
    """备战单轮决策出口把动作类型序列写 session.last_prep_action_sig
    (守卫动作腿的唯一写点)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        OpenShop,
    )

    d, _match, session = _make_round_director(
        test_context, monkeypatch, [OpenShop(read_only=True)])
    with fast_sleep():
        enter_running_state(test_context)
        try:
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert session.last_prep_action_sig == ('OpenShop',), (
        f'决策出口须写动作批签名:{session.last_prep_action_sig!r}')


def test_prep_op_overlay_handback_keeps_signature_none(
        test_context, monkeypatch) -> None:
    """overlay 交回环(决策未发生)签名保持 None → cw_loop 不累计
    (防跨环误延;战斗等待静默期不误伤的接线面)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        OpenShop,
    )

    d, _match, session = _make_round_director(
        test_context, monkeypatch, [OpenShop(read_only=True)], overlay='遭遇')
    with fast_sleep():
        enter_running_state(test_context)
        try:
            d.run()
        finally:
            reset_running_state(test_context, d)
    assert session.last_prep_action_sig is None, (
        'overlay 交回不得写签名(None 才能让外环清计数)')


def _make_loop_op(test_context, monkeypatch, session, stops, flags,
                  sig=('OpenShop',)):
    """真 loop 路径单测装配:真 CwLoop 实例 + 画面分发桩(只认备战双锚)。

    桩面 = loop() 顶层分发的「画面判定与外部出口」:round_by_* 桩让全部分支
    不命中、唯备战双锚命中;观察/识别族(find_trial_reveal_cards/find_bookcards
    /read_node_sequence)与备战单轮(CwScreenPrep)桩为空——本锁辖「守卫消费
    签名 → 停机」接线,不辖备战环内部(备战桩不重写签名 → 跨环冻结)。
    遥测全局(state.start_run/get_recorder/分配器)桩化,满足「模块级全局
    一并桩化」纪律;flag 写入重定向收集器(测试零真实 .debug/ 副作用)。
    handle_init 不跑(重装配结算链/配置),loop() 消费但守卫路径不消费的
    run 级属性按 False/0 显式布线。
    """
    session.last_prep_action_sig = sig
    from sr_od.application.currency_war.operations import cw_loop as loop_mod

    class _StubPrep:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return SimpleNamespace(success=True, status='stub')

    match = SimpleNamespace(strategy=None, session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    monkeypatch.setattr(test_context, 'cw_selected_difficulty', '',
                        raising=False)
    monkeypatch.setattr(test_context.run_context, 'stop_running',
                        lambda reason='': stops.append(reason))
    monkeypatch.setattr(loop_mod, 'write_no_progress_flag',
                        lambda count, sig, shot: flags.append((count, sig)))
    # 遥测/分配器模块级全局:构造与守卫路径会触碰,一并桩化(测试隔离整条副作用链)
    monkeypatch.setattr(loop_mod.state, 'start_run',
                        lambda difficulty='': None)
    monkeypatch.setattr(loop_mod.state, 'get_recorder',
                        lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(loop_mod, '_get_or_init_allocator', lambda ctx: None)
    monkeypatch.setattr(loop_mod, 'read_node_sequence', lambda ctx, screen: [])
    monkeypatch.setattr(loop_mod, 'CwScreenPrep', _StubPrep)
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_identity_obs.'
        'find_trial_reveal_cards', lambda screen, slots: [])
    monkeypatch.setattr(
        'sr_od.application.currency_war.obs.cw_identity_obs.find_bookcards',
        lambda screen, slots: [])
    # 0p 分支 area 锚未命中也会跑 OCR 排他判别 → OCR 读帧桩化(零真识别)
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_screen.'
        'cw_screen_boss_briefing.read_ocr_texts', lambda ctx, screen: [])

    _fail = SimpleNamespace(is_success=False)
    op = loop_mod.CwLoop(test_context)

    def _find_area(screen, screen_name, area_name, **kwargs):
        hit = (screen_name == '货币战争-备战'
               and area_name in ('备战标识-购买经验', '按钮-出战'))
        return SimpleNamespace(is_success=hit)

    monkeypatch.setattr(op, 'round_by_find_area', _find_area)
    monkeypatch.setattr(op, 'round_by_ocr', lambda screen, text, **k: _fail)
    monkeypatch.setattr(op, 'round_by_ocr_and_click',
                        lambda screen, text, **k: _fail)
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda screen, s, a, **k: _fail)
    monkeypatch.setattr(op, 'save_screenshot', lambda prefix='': 'stub-shot')
    monkeypatch.setattr(op, '_stall_watch_tick', lambda screen: None)
    op.last_screenshot = object()   # 仅作桩入参透传,识别族全桩
    # handle_init 布线:loop() 守卫路径不消费的 run 级属性显式置安全值
    op._is_new_match = False
    op._cw_resume_candidate = False
    op._cw_locked_resume = False
    op._cw_back_btn_count = 0
    op._cw_strategy_dead_streak = 0
    op._cw_dead_prev_key = None
    return op


def test_loop_prep_guard_stops_after_frozen_signature_rounds(
        test_context, monkeypatch) -> None:
    """行为锁(替代旧 cw_loop.loop 源码字面锁「last_prep_action_sig 等 5 条
    在场断言」):3 轮「同签名动作批 ∧ 状态零推进」经真 loop 备战分支消费
    session.last_prep_action_sig → 截图存证 + write_no_progress_flag +
    stop_running(reason='hook:prep_no_progress')。失守场景 = 消费端脱落
    (签名写点还在但外环不再计数/停机降级为只留证)时本锁红;纯重构
    (改名/换行/抽取函数)不再假红。计数语义:首见签名计 0,同签名每环 +1,
    第 4 个冻结环计数达 PREP_NO_PROGRESS_ROUNDS=3 触发。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags)
    with fast_sleep():
        for _ in range(4):
            op.loop()
    assert stops == ['hook:prep_no_progress'], (
        f'守卫须停机一次,实得 {stops!r}')
    assert flags and flags[0][0] == 3, (
        f'停机前须写存证 flag(计数=3),实得 {flags!r}')


def test_loop_prep_guard_healthy_progress_never_stops(
        test_context, monkeypatch) -> None:
    """真 loop 路径不误伤面:同签名动作批但状态每环推进(gold 变)→
    指纹变 → 计数归零,不触发停机(健康多帧部署走真分发路径验证)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags)
    with fast_sleep():
        for i in range(6):
            session.last_state = SimpleNamespace(plane=1, round_num=5, gold=30 + i)
            op.loop()
    assert stops == [], f'状态推进中的同批动作不得停机:{stops!r}'
    assert flags == [], '健康序列不得写存证 flag'


# ==================== 备战收益耗尽 → 出战臂(ADR-0554) ====================
# 机制依据(docs/game/currency_war/data/gameplay.md):备战等待零边际收益
# (商店每节点自动刷新 1 次,金息/基础金/连胜奖励均在战斗结算发放)→
# RunDeploy 稳态 no-op 形态判「收益耗尽」改判出战;其余形态维持停机。
# 判据单一源 = cw_loop.prep_exhaustion_launch_eligible。


def test_exhaustion_eligible_truth_table() -> None:
    """判据真值表:RunDeploy 稳态(success)唯一 eligible;失败环/混合批/
    None 批一律不 eligible(执行面失败形态保持守卫停机语义)。"""
    from sr_od.application.currency_war.operations import cw_loop as m
    e = m.prep_exhaustion_launch_eligible
    assert e(('RunDeploy',), True), 'RunDeploy 稳态 no-op + 上环 success = 收益耗尽'
    assert e(('RunDeploy', 'RunDeploy'), True), '同批多次 RunDeploy 同型'
    assert not e(('RunDeploy',), False), '上环 fail = 执行面失败,须停机留证'
    assert not e(('RunDeploy',), None), '无上环记录(首轮)不 eligible'
    assert not e(None, True), 'None 批(overlay 交回)不累计不 eligible'
    assert not e(('OpenShop',), True), 'OpenShop 批 = 重燃重发形态,须停机'
    assert not e(('OpenShop', 'RunEquip'), True), '装备环形态,须停机'
    assert not e(('RunDeploy', 'OpenShop'), True), '混合批不 eligible'


def test_loop_exhaustion_launches_battle_instead_of_stop(
        test_context, monkeypatch) -> None:
    """行为锁(ADR-0554):3 冻结环 RunDeploy 稳态 no-op(上环 success)→
    守卫触发位改判出战(launch 核被调、不 stop_running、不写停机 flag)。
    失守场景 = 出战臂脱落回落停机(恢复烧对局预算的旧病)时本锁红。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    launches: list = []

    def _fake_launch(op_, ctx_):
        launches.append(1)
        return True, 'stub-launch'

    monkeypatch.setattr(loop_mod, 'readiness_battle_launch', _fake_launch)
    with fast_sleep():
        for _ in range(4):
            op.loop()
    assert launches, '收益耗尽帧必须经发射核出战'
    assert stops == [], f'RunDeploy 稳态 no-op 不得停机:{stops!r}'
    assert flags == [], '出战臂路径不得写停机 flag'
    assert op._cw_exhaust_fail_n == 0, '发射成功须复位失败连击'


def test_loop_exhaustion_launch_fail_gives_up_to_guard_stop(
        test_context, monkeypatch) -> None:
    """防线(与达标臂 C1 同构):发射核连续 3 次失败 → 放弃短路,回落守卫
    停机留证(不无限自旋;停机时 flag 照写)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    launches: list = []
    monkeypatch.setattr(loop_mod, 'readiness_battle_launch',
                        lambda op_, ctx_: (launches.append(1), (False, 'stub-fail'))[1])
    with fast_sleep():
        for _ in range(6):
            op.loop()
    assert len(launches) == 3, f'失败连击达 3 即放弃,实得 {len(launches)} 次'
    assert stops == ['hook:prep_no_progress'], (
        f'放弃短路后须回落守卫停机:{stops!r}')
    assert flags, '回落停机须写存证 flag'
    assert op._cw_exhaust_fail_n == 0, '放弃时失败计数复位'


def test_loop_exhaustion_not_eligible_when_prep_fails(
        test_context, monkeypatch) -> None:
    """不误伤面(执行面失败形态保持停机):同 RunDeploy 冻结签名但备战环
    round_fail(计划非空落地 0 = 拖拽落空类)→ 不出战,守卫照常停机。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    launches: list = []

    class _FailPrep:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            return SimpleNamespace(success=False, status='部署未落地')

    monkeypatch.setattr(loop_mod, 'CwScreenPrep', _FailPrep)
    monkeypatch.setattr(loop_mod, 'readiness_battle_launch',
                        lambda op_, ctx_: (launches.append(1), (True, 'x'))[1])
    with fast_sleep():
        for _ in range(4):
            op.loop()
    assert launches == [], '执行面失败形态不得改判出战'
    assert stops == ['hook:prep_no_progress'], (
        f'失败环形态须维持守卫停机:{stops!r}')


def test_loop_exhaustion_stale_gives_up_to_guard_stop(
        test_context, monkeypatch) -> None:
    """ADR-0554 双限锁①(stale 同型连击):发射核连续 3 次 stale_screen →
    放弃重试,回落守卫停机(单帧 stale 不停机交回下轮;持续 stale 受上限
    辖,禁无界自旋)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    attempts: list = []

    def _stale_launch(op_, ctx_):
        attempts.append(1)
        return False, 'readiness_stale_screen'

    monkeypatch.setattr(loop_mod, 'readiness_battle_launch', _stale_launch)
    with fast_sleep():
        for _ in range(6):
            op.loop()
    assert len(attempts) == 3, f'stale 连击达 3 即放弃,实得 {len(attempts)} 次'
    assert stops == ['hook:prep_no_progress'], (
        f'持续 stale 须回落守卫停机(禁无界自旋):{stops!r}')
    assert flags, '回落停机须写存证 flag'
    assert op._cw_exhaust_stale_n == 0, '放弃时 stale 计数复位'


def test_loop_exhaustion_success_resets_stale_counter(
        test_context, monkeypatch) -> None:
    """stale 连击复位面(ADR-0554 锁重构:先造非零再断言复位,防恒真锁):
    注入首发 stale(计数置 1)→ 次发射 success → 断言复位真发生
    (生产复位语句被移除时本锁红:stale_n 残留 1)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    calls: list = []

    def _stale_then_ok(op_, ctx_):
        calls.append(1)
        if len(calls) == 1:
            return False, 'readiness_stale_screen'
        return True, 'stub-launch'

    monkeypatch.setattr(loop_mod, 'readiness_battle_launch', _stale_then_ok)
    with fast_sleep():
        for _ in range(6):
            op.loop()
    assert len(calls) >= 2, f'须先 stale 后 success,实调 {len(calls)} 次'
    assert stops == [], f'发射成功路径不得停机:{stops!r}'
    assert op._cw_exhaust_stale_n == 0, (
        '发射成功必须复位 stale 连击(锁防复位语句被删:stale 已置非零)')
    assert op._cw_exhaust_attempts == 0, '发射成功必须复位总尝试计数'


def test_loop_exhaustion_interleaved_capped_by_total_limit(
        test_context, monkeypatch) -> None:
    """ADR-0554 双限锁②(总尝试限):fail/stale 交错序列两同型计数器互
    复位、同型连击永不达限——总尝试上限(2×守卫阈值=6)兜底封死无界
    自旋:总限内(前 5 次尝试)不停机持续重试,第 6 环达限回落守卫停机。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    calls: list = []

    def _fail_stale_alternate(op_, ctx_):
        calls.append(1)
        if len(calls) % 2 == 1:
            return False, 'stub-fail'
        return False, 'readiness_stale_screen'

    monkeypatch.setattr(loop_mod, 'readiness_battle_launch',
                        _fail_stale_alternate)
    with fast_sleep():
        for _ in range(10):
            op.loop()
    assert len(calls) == 6, (
        f'总尝试上限内恰 6 次发射(2×守卫阈值),实得 {len(calls)} 次')
    assert stops == ['hook:prep_no_progress'], (
        f'总尝试达限后须回落守卫停机(交错不得无界自旋):{stops!r}')
    assert flags, '回落停机须写存证 flag'
    assert op._cw_exhaust_attempts == 0, '达限放弃时总尝试计数复位'


def test_loop_exhaustion_attempts_reset_across_episodes(
        test_context, monkeypatch) -> None:
    """ADR-0554「总限只辖单一冻结情节」锁(三审后补必修1):冻结情节内
    产生尝试计数(>0)后状态推进 → 守卫计数归零 → 总尝试计数必须同步
    归零(残留计数会让新冻结情节提前总限 giveup)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    monkeypatch.setattr(loop_mod, 'readiness_battle_launch',
                        lambda op_, ctx_: (False, 'stub-fail'))
    with fast_sleep():
        for _ in range(4):
            op.loop()
    assert op._cw_exhaust_attempts == 1, (
        f'冻结情节内须产生尝试计数,实得 {op._cw_exhaust_attempts}')
    # 状态推进(gold 变)→ 指纹变 → 守卫计数归零 → 总尝试同步归零
    session.last_state = SimpleNamespace(plane=1, round_num=5, gold=99)
    with fast_sleep():
        op.loop()
    assert op._cw_exhaust_attempts == 0, (
        '跨冻结情节总尝试计数必须归零(残留会让新情节提前 giveup)')
    assert stops == [], f'状态推进环不得停机:{stops!r}'
