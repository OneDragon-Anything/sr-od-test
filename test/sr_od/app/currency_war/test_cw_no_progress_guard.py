"""环级无进展守卫锁(第 5 局放行硬门;F2 单键计数,T-167 迁移)。

设计出处 = docs/develop/currency_war/decisions/dd-030-no-progress-guard.md
(环级活性不变量)+ docs/develop/currency_war/flow/guards.md §1(防线总册)
+ docs/develop/currency_war/decisions/0554-prep-exhaustion-battle-launch.md
(ADR-0554 + T-167 修订节)。触发语义(F2):计数键 = 状态指纹单键
(prep_no_progress_state_fingerprint,只读 observe 现成字段;gold 分量
按开态可信帧钉死);连续 PREP_NO_PROGRESS_ROUNDS=3 环指纹零推进 →
出战臂或截图 + flag + stop_running。动作批 = 窗口并集累积器留证 + 臂
判别(EXHAUSTION_WINDOW_ACTIONS ⊆ 约束 ∧ 末批 RunDeploy)。旧键
(动作批, 指纹) 被签名振荡穿透的缺口 = T-167 事故结构根,本文件头至尾
按新键重推(锁的存在性纪律:锁红 ≠ 改动错,先重推语义再跟改)。

不误伤判据(F2 后重述):
①战斗等待期不进备战分支,回备战 round 必变 → 归零;
②正常多帧部署:每次成功动作改变身份/金(真购必经开店帧,gold 可信位
  单源钉死)→ 指纹变 → 归零;
③动作批振荡不再归零(F2 语义变更)——恒指纹下的振荡 = 忙而无功,
  恰是本守卫要捕的形态;第三类动作入窗口则出战臂店闭,落停机留证。
"""

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
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


def _simulate(rings: list[tuple[tuple[str, ...] | None, object]],
              ) -> tuple[int, bool, frozenset[str]]:
    """重放备战环序列:(动作批, session 或指纹元组),返回 (末次计数, 是否
    触发, 末次窗口动作批并集)。

    每环 = cw_loop 备战分支一次守卫判定(F2 单键:计数键 = 状态指纹,
    动作批入窗口并集累积器;动作批 None 模拟 overlay 交回环 = 共同出口
    归零)。
    """
    m = _fingerprint_module()
    sig_state = None
    count = 0
    union: frozenset[str] = frozenset()
    triggered = False
    for actions, sess in rings:
        if actions is None:
            sig_state = None
            count = 0
            union = frozenset()
            continue
        fp = sess if isinstance(sess, tuple) else \
            m.prep_no_progress_state_fingerprint(sess)
        sig_state, count, union = m.prep_no_progress_tick(
            sig_state, count, union, fp, actions)
        if count >= m.CwLoop.PREP_NO_PROGRESS_ROUNDS:
            triggered = True
    return count, triggered, union


def test_tick_accumulates_same_fingerprint_and_resets_on_change() -> None:
    """同指纹累加 / 异指纹归零(F2 单键核心语义;三历史重放锁随迁)。

    语义变更(T-167):计数键由 (动作批, 指纹) 改为指纹单键——动作批
    变化不再归零(振荡签名 + 恒指纹 = 忙而无功,恰是守卫要捕的形态);
    并集累积器同指纹逐环并入、指纹变化归零重开(F-6②)。"""
    m = _fingerprint_module()
    s, c, u = m.prep_no_progress_tick(None, 0, frozenset(), (1,), ('OpenShop',))
    assert (s, c) == ((1,), 0), '首见指纹计数从 0 起'
    assert u == {'OpenShop'}, '首环并集 = 本环动作批'
    _, c, u = m.prep_no_progress_tick(s, c, u, (1,), ('RunDeploy',))
    _, c, u = m.prep_no_progress_tick(s, c, u, (1,), ('OpenShop',))
    assert c == 2, '同指纹两次重复后计数=2(动作批振荡不归零,F2)'
    assert u == {'OpenShop', 'RunDeploy'}, '并集逐环并入'
    _, c, u = m.prep_no_progress_tick(s, c, u, (2,), ('RunDeploy',))
    assert c == 0, '指纹变化(状态推进)必须归零'
    assert u == {'RunDeploy'}, '并集随指纹变化归零重开(F-6②)'


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


def test_fingerprint_gold_pinned_to_trusted_frames() -> None:
    """gold 分量钉死(F-5,T-167):仅开态可信帧(prep_obs_frame.state_
    gold_trusted)更新可信陈值,其余帧沿用陈值——店店帧 gold 噪声
    (0 兜底/OCR 抖动)不构成假推进也不毒化陈值。陈值载体 = session
    属性(PREP_GOLD_TRUSTED_ATTR),同一 session 跨帧存活;无陈值的新
    session 回退 raw 读数(开局首店前,噪声至多延迟出口)。"""
    m = _fingerprint_module()
    # 开态可信帧:陈值写入,gold 进指纹
    sess = _session(gold=31)
    sess.prep_obs_frame.state_gold_trusted = True
    fp_t = m.prep_no_progress_state_fingerprint(sess)
    assert fp_t[3] == 31
    # 店店帧(raw 29 = 事故局实测噪声形态):沿用陈值 31,指纹不变
    sess.prep_obs_frame.state_gold_trusted = False
    sess.last_state.gold = 29
    assert m.prep_no_progress_state_fingerprint(sess)[3] == 31, (
        '店店帧噪声不得改写 gold 分量(沿用陈值)')
    # 店店失读兜底 0 形态:同样沿用陈值(wholesale raw 写入链,方案审 F-5)
    sess.last_state.gold = 0
    assert m.prep_no_progress_state_fingerprint(sess)[3] == 31
    # 新可信帧推进 gold → 指纹变(真买入必经开店帧,进展检测无损)
    sess.prep_obs_frame.state_gold_trusted = True
    sess.last_state.gold = 28
    assert m.prep_no_progress_state_fingerprint(sess)[3] == 28
    # 无陈值的新 session(开局首店前)回退 raw 读数
    sess_fresh = _session(gold=17)
    sess_fresh.prep_obs_frame.state_gold_trusted = False
    assert m.prep_no_progress_state_fingerprint(sess_fresh)[3] == 17


# ==================== 不误伤:健康序列/战斗等待/闩跳过 ====================


def test_healthy_rotation_never_triggers() -> None:
    """健康轮转:每环 round 或部署/金在变 → 永不触发。"""
    rings = []
    for r in range(10):
        sess = _session(round_num=5 + r // 3, gold=30 + r,
                        deployed=('c',) if r % 2 == 0 else ('c', 'd'))
        rings.append((('OpenShop',), sess))
    _, triggered, _u = _simulate(rings)
    assert not triggered, '状态推进中的同批动作不得触发'


def test_action_oscillation_with_frozen_state_reaches_threshold() -> None:
    """T-167 事故形态核心锁(旧「动作批变化归零」语义的反转,先例 =
    2026-09-08 实机交替活锁:闩驱动的 OpenShop/RunDeploy 振荡 + 恒指纹
    每帧归零,相位出口全灭 15 分钟):状态冻结但动作批振荡 → F2 单键
    下计数照常累加,3 环达阈值——守卫不再被振荡穿透。"""
    frozen = _session()
    rings = [
        (('OpenShop',), frozen),
        (('RunDeploy',), frozen),   # 闩驱动交替(事故形态)
        (('OpenShop',), frozen),
        (('RunDeploy',), frozen),
    ]
    count, triggered, union = _simulate(rings)
    assert count == 3, f'振荡签名在恒指纹下必须累加,实得 {count}'
    assert triggered, '事故形态必须触达阈值(旧键每帧归零 = 缺口本体)'
    assert union == {'OpenShop', 'RunDeploy'}, '振荡动作批全量入窗口并集'


def test_third_action_in_window_blocks_launch_but_still_counts() -> None:
    """第三类动作入窗口(DeferSpheres 等)= 语义未核实形态:计数照常
    累加(忙而无功),但出战臂被并集约束店闭 → 落守卫停机留证(F2
    边界:不代打)。"""
    frozen = _session()
    rings = [
        (('OpenShop',), frozen),
        (('DeferSpheres',), frozen),
        (('OpenShop',), frozen),
        (('DeferSpheres',), frozen),
    ]
    count, _t, union = _simulate(rings)
    assert count == 3, '恒指纹下第三类动作窗口照常计数'
    assert not ('RunDeploy' in union and
                union <= _fingerprint_module().EXHAUSTION_WINDOW_ACTIONS), (
        '窗口含白名单外动作,出战臂必须店闭')
    m = _fingerprint_module()
    assert not m.prep_exhaustion_launch_eligible(
        ('DeferSpheres',), True, frozenset({'OpenShop', 'DeferSpheres'})), (
        '第三类动作窗口不得 eligible')


def test_overlay_interlude_and_battle_wait_reset_and_silence() -> None:
    """战斗等待期/overlay 交回环(动作批 None)不累计且中断已累计连击:
    ①纯 None 环长序列不触发;②卡死中插入 None(战斗)后计数与并集
    清零(F-6①②:overlay 垄断形态维持哨兵档,并集一并归零)。"""
    rings = [(None, None)] * 20
    _, triggered, _u = _simulate(rings)
    assert not triggered, '战斗等待/overlay 环必须静默'

    frozen = _session()
    rings = [
        (('RunDeploy',), frozen),
        (('RunDeploy',), frozen),
        (None, None),                 # 中途一场战斗/overlay 交回
        (('RunDeploy',), frozen),
        (('RunDeploy',), frozen),
    ]
    count, triggered, union = _simulate(rings)
    assert not triggered, 'None 环必须清零计数(战斗静默期不误伤)'
    assert union == {'RunDeploy'}, (
        f'None 环后并集只含 None 环后的动作批,实得 {union!r}')


# ==================== 存证 flag(测试零真实副作用:tmp_path) ====================


def test_write_no_progress_flag_content(tmp_path) -> None:
    """flag 三要素:计数 + 状态指纹(F2 单键)+ 截图路径,处理流程可执行。"""
    m = _fingerprint_module()
    p = tmp_path / 'prep_no_progress.flag'
    out = m.write_no_progress_flag(3, (1, 5, 'battle', 30, ('a',), ('c',)),
                                   '<shot>', path=p)
    assert out == str(p)
    text = p.read_text(encoding='utf-8')
    assert '3' in text and '30' in text and '<shot>' in text
    assert '[HOOK-STOP]' in text and '处理流程' in text


# ==================== 接线:备战单轮 op 写签名 / loop 消费 ====================


def _make_round_director(test_context, monkeypatch, scripted_actions,
                         overlay=None):
    """备战单轮单测装配(最小集)。

    同域镜像副本 = test_cw_stall_cache 的 prep 写点测(同款桩面):
    彼锁 cw4_frame_action_record token 载体写点,本文件锁
    last_prep_action_sig 签名写点——两写点同一决策出口,禁删边留角。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    class _StubStrategy:
        def decide_prep_screen(self, session, config):
            return list(scripted_actions)

    d = pd_mod.CwScreenPrep(test_context)
    session = StrategySession()
    match = SimpleNamespace(strategy=_StubStrategy(), session=session)
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
    """备战单轮决策出口把动作类型序列写 exec_state_of(session).last_prep_action_sig
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
    assert exec_state_of(session).last_prep_action_sig == ('OpenShop',), (
        f'决策出口须写动作批签名:{exec_state_of(session).last_prep_action_sig!r}')


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
    assert exec_state_of(session).last_prep_action_sig is None, (
        'overlay 交回不得写签名(None 才能让外环清计数)')


def _make_loop_op(test_context, monkeypatch, session, stops, flags,
                  sig=('OpenShop',)):
    """真 loop 路径单测装配:真 CwLoop 实例 + 画面分发桩(只认备战双锚)。

    桩面 = loop() 顶层分发的「画面判定与外部出口」:round_by_* 桩让全部分支
    不命中、唯备战双锚命中;投资浮层重探恒缺席;观察/识别族
    (find_trial_reveal_cards/find_bookcards/read_node_sequence)与备战单轮
    (CwScreenPrep)桩为空——本锁辖「守卫消费签名 → 停机」接线,不辖备战
    环内部(备战桩不重写签名 → 跨环冻结)。
    遥测全局(state.start_run/get_recorder/分配器)桩化,满足「模块级全局
    一并桩化」纪律;flag 写入重定向收集器(测试零真实 .debug/ 副作用)。
    handle_init 不跑(重装配结算链/配置),loop() 消费但守卫路径不消费的
    run 级属性按 False/0 显式布线。
    """
    exec_state_of(session).last_prep_action_sig = sig
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
    # ADR-0588:生产铸造单点前移,构造调用从 state.start_run 换成 ensure_run_started
    # (桩点随调用点迁移;本 helper 意图不变 = 「CwLoop 构造不触真实遥测」)
    monkeypatch.setattr(loop_mod.state, 'ensure_run_started',
                        lambda match=None, difficulty='': None)
    monkeypatch.setattr(loop_mod.state, 'get_recorder',
                        lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(loop_mod, '_get_or_init_allocator', lambda ctx: None)
    monkeypatch.setattr(loop_mod, 'read_node_sequence', lambda ctx, screen: [])
    # 0e 投资浮层重探桩:生产在「备战双锚命中 ∧ 首探 miss」形态付 0.6s 裸
    # time.sleep(INVEST_REPROBE_WAIT)+新截图(淡入期防误判探针);裸 time.sleep
    # 不经 op 框架 time 对象,fast_sleep 拦不到——不桩则每环白付 0.6s(cProfile
    # 实测:4 环 2.4s 全在该 sleep)。恒判浮层缺席与既有 round_by_* 桩同语义,
    # 守卫/耗尽臂锁不辖路由探针。
    monkeypatch.setattr(loop_mod, '_invest_overlay_dispatch',
                        lambda op_, screen_: (False, screen_))
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
    exec_state_of(session).last_prep_action_sig → 截图存证 + write_no_progress_flag +
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
    """判据真值表(F2 放宽版;ADR-0554 T-167 修订节):窗口并集 ⊆
    {OpenShop, RunDeploy} ∧ 末批 RunDeploy ∧ 上环 success 唯一 eligible;
    末批 OpenShop/失败环/None 批/白名单外动作一律不 eligible。"""
    from sr_od.application.currency_war.operations import cw_loop as m
    e = m.prep_exhaustion_launch_eligible
    assert e(('RunDeploy',), True, frozenset({'RunDeploy'})), (
        'RunDeploy 稳态 no-op + 上环 success = 收益耗尽')
    assert e(('OpenShop', 'RunDeploy'), True,
             frozenset({'OpenShop', 'RunDeploy'})), (
        '振荡窗口(RunDeploy 末批)= F2 放宽核心,旧判据 set=={RD} 恒假'
        '即事故缺口本体')
    assert not e(('RunDeploy',), False, frozenset({'RunDeploy'})), (
        '上环 fail = 执行面失败,须停机留证')
    assert not e(('RunDeploy',), None, frozenset({'RunDeploy'})), (
        '无上环记录(首轮)不 eligible')
    assert not e(None, True, frozenset()), 'None 批(overlay 交回)不累计不 eligible'
    assert not e((), True, frozenset()), '空批非 RunDeploy 末批,不 eligible'
    assert not e(('OpenShop',), True, frozenset({'OpenShop'})), (
        '末批 = OpenShop 的第 3 恒指纹环:F-4  parity B,判据假 → 落停机'
        '(3 环内必有出口的确定性不变)')
    assert not e(('OpenShop', 'RunEquip'), True,
                 frozenset({'OpenShop', 'RunEquip'})), '装备环形态,须停机'
    assert not e(('RunDeploy', 'OpenShop'), True,
                 frozenset({'OpenShop', 'RunDeploy'})), (
        '混合批末批非 RunDeploy 不 eligible')
    assert not e(('RunDeploy',), True,
                 frozenset({'RunDeploy', 'StartBattle'})), (
        '窗口含白名单外动作(StartBattle)不 eligible')


def _make_loop_op_altsig(test_context, monkeypatch, session, stops, flags,
                         sigs):
    """振荡签名版 loop 装配(基于 _make_loop_op,CwScreenPrep 桩逐环改写
    exec_state 签名;恒指纹 session 由调用方保证)——T-167 事故形态的
    真环重放载体(F-4 parity 双形态锁用)。"""
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=sigs[0])
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    # 桩写序从 sigs[1] 起:守卫在 loop 内先读后派发,本环写值由下环守卫
    # 读到——初值 sigs[0] 已被 _make_loop_op 置入,占读序第 1 位,桩从
    # 读序第 2 位开始续写,保证守卫读到的签名序列恰为 sigs 的循环。
    _it = {'i': 1}

    class _AltPrep:
        def __init__(self, ctx) -> None:
            pass

        def execute(self):
            sig = sigs[_it['i'] % len(sigs)]
            _it['i'] += 1
            exec_state_of(session).last_prep_action_sig = sig
            return SimpleNamespace(success=True, status='stub')

    monkeypatch.setattr(loop_mod, 'CwScreenPrep', _AltPrep)
    return op


def test_loop_incident_parity_a_alternation_launches_battle(
        test_context, monkeypatch) -> None:
    """F-4 parity A(真环行为锁):恒指纹 + OpenShop/RunDeploy 交替签名,
    第 3 恒指纹环末批 = RunDeploy → 收益耗尽臂出战(T-167 事故形态的
    出口恢复;旧键下此形态计数每帧归零永不可达)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op_altsig(test_context, monkeypatch, session, stops,
                              flags, sigs=[('OpenShop',), ('RunDeploy',)])
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    launches: list = []
    monkeypatch.setattr(loop_mod, 'readiness_battle_launch',
                        lambda op_, ctx_: (launches.append(1), (True, 'x'))[1])
    with fast_sleep():
        for _ in range(5):
            op.loop()
    assert launches, '末批 RunDeploy 相位必须出战(F-4 parity A)'
    assert stops == [], f'eligible 相位不得停机:{stops!r}'


def test_loop_incident_parity_b_openshop_last_stops_with_evidence(
        test_context, monkeypatch) -> None:
    """F-4 parity B(真环行为锁):同振荡形态但第 3 恒指纹环末批 =
    OpenShop → 判据假 → 落守卫停机留证(不出战、不发射)——3 环内必有
    出口的确定性闭合,「必出战」只对 parity A 成立(任务书钉死口径)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op_altsig(test_context, monkeypatch, session, stops,
                              flags, sigs=[('RunDeploy',), ('OpenShop',)])
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    launches: list = []
    monkeypatch.setattr(loop_mod, 'readiness_battle_launch',
                        lambda op_, ctx_: (launches.append(1), (True, 'x'))[1])
    with fast_sleep():
        for _ in range(4):
            op.loop()
    assert launches == [], '末批 OpenShop 相位不得出战(F-4 parity B)'
    assert stops == ['hook:prep_no_progress'], (
        f'parity B 须落守卫停机留证:{stops!r}')
    assert flags, 'parity B 停机须写存证 flag'


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


def test_loop_exhaustion_success_registers_flow_heartbeat(
        test_context, monkeypatch) -> None:
    """发射成功帧心跳登记锁(局33 复盘定谳的静默失效修复):收益耗尽臂
    发射成功必须经 register_flow_heartbeat 登记 decisions 心跳行
    (sid=cw:flow:exhaustion_battle_launch)——接线断裂时本锁红
    (旧病:_state.get_recorder() 恒 AttributeError 被 best-effort 静默吞,
    心跳从未落盘且无任何可见信号)。"""
    session = _session()
    stops: list = []
    flags: list = []
    op = _make_loop_op(test_context, monkeypatch, session, stops, flags,
                       sig=('RunDeploy',))
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    beats: list = []
    monkeypatch.setattr(loop_mod.state, 'get_recorder',
                        lambda: SimpleNamespace(enabled=True))
    # 策略失活检查在 recorder enabled 时走 read_phase_round(真 OCR)——
    # 桩化为 None(零真识别;本锁只辖心跳登记面)
    monkeypatch.setattr(loop_mod, 'read_phase_round',
                        lambda ctx, screen: None)
    monkeypatch.setattr(loop_mod.recorder, 'record_decision',
                        lambda *a, **k: beats.append((a, k)))
    monkeypatch.setattr(loop_mod, 'readiness_battle_launch',
                        lambda op_, ctx_: (True, 'stub-launch'))
    with fast_sleep():
        for _ in range(4):
            op.loop()
    assert len(beats) == 1, (
        f'发射成功帧必须恰登记 1 条心跳行,实得 {len(beats)}')
    _args, kwargs = beats[0]
    assert kwargs.get('extra', {}).get('strategy_id') == \
        'cw:flow:exhaustion_battle_launch', (
        f'心跳行 strategy_id 接线错误:{kwargs!r}')


# ==================== F2 排除族(F2 边界;单一源 = prep_exhaustion_exclusion_reason)====================

def test_exhaustion_exclusion_family(monkeypatch) -> None:
    """排除族锁(可扩展形态):补给节点 → exhaustion_supply(出战不推进,
    正确出口是补流程);奖励节点 ∧ 球在场 → exhaustion_reward_sphere
    (实机观测项标注,离线不可判);奖励节点球已收清 → 不排除(合取
    防误排除,方案审 F2 §5);非上述节点 → ''(可出战)。"""
    from sr_od.application.currency_war.operations import cw_loop as m

    class _Slot:
        def __init__(self, node_type: str) -> None:
            self.state = 'current'
            self.node_type = node_type

    ctx = SimpleNamespace()
    cases: list[tuple[str, str, list, list, str]] = [
        # (用例名, node_type, node_sequence 返回, spheres 返回, 期望)
        ('补给节点', 'supply', [_Slot('supply')], [], 'exhaustion_supply'),
        ('奖励节点球在场', 'reward', [_Slot('reward')], [('gold',)],
         'exhaustion_reward_sphere'),
        ('奖励节点球已收清', 'reward', [_Slot('reward')], [], ''),
        ('战斗节点有球不辖', 'battle', [_Slot('battle')], [('gold',)], ''),
        ('boss 无节点序', 'boss', [], [('gold',)], ''),
    ]
    for name, _nt, seq, spheres, want in cases:
        monkeypatch.setattr(m, 'read_node_sequence',
                            lambda ctx_, screen, _seq=seq: _seq)
        import sr_od.application.currency_war.obs.cw_identity_obs as ident
        monkeypatch.setattr(ident, 'read_reward_spheres',
                            lambda ctx_, screen, _s=spheres: _s)
        got = m.prep_exhaustion_exclusion_reason(ctx, object())
        assert got == want, f'{name}: 期望 {want!r} 实得 {got!r}'


def test_exhaustion_exclusion_sphere_detect_error_opens_arm(monkeypatch) -> None:
    """检测退化方向锁:球识别异常 → 不排除(出战优先,同前置引入前的
    现行为;排除腿失效方向显式钉死防将来误改)。"""
    from sr_od.application.currency_war.operations import cw_loop as m

    class _Slot:
        state = 'current'
        node_type = 'reward'

    monkeypatch.setattr(m, 'read_node_sequence',
                        lambda ctx_, screen: [_Slot()])

    def _boom(ctx_, screen):
        raise RuntimeError('识别退化')

    import sr_od.application.currency_war.obs.cw_identity_obs as ident
    monkeypatch.setattr(ident, 'read_reward_spheres', _boom)
    assert m.prep_exhaustion_exclusion_reason(SimpleNamespace(), object()) == ''
