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


def test_loop_consumes_signature_and_stops() -> None:
    """接线锁:cw_loop 备战分支消费 last_prep_action_sig,守卫触发走
    stop_running(与既有停机钩子同构),存证走 write_no_progress_flag。"""
    import inspect

    from sr_od.application.currency_war.operations import cw_loop

    src = inspect.getsource(cw_loop.CwLoop.loop)
    assert 'last_prep_action_sig' in src, '备战分支缺动作批签名消费'
    assert 'prep_no_progress_state_fingerprint' in src, '缺状态指纹消费'
    assert 'hook:prep_no_progress' in src and 'stop_running' in src, (
        '守卫停机未接线(旧线只留证语义已废)')
    assert 'write_no_progress_flag' in src, '缺存证 flag 写入'
    # 全模块签名写入端唯一性:CwScreenPrep 决策出口/破墙段两处,无第三写点
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pd_mod,
    )
    prep_src = inspect.getsource(pd_mod)
    assert prep_src.count('last_prep_action_sig = ') >= 2, (
        '备战 op 缺签名写点(决策出口/破墙段)')
