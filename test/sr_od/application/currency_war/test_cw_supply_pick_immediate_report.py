"""补给选卡即时上报 + 装备名注册表级分层归一 行为锁(迭代
changes/2026-09-21-event-refresh-unify-supply-pick landing 3.1 判据面;
design §2.0B/§3 验收锚 1)。

- **pick 即时上报锁**(fixture 剧本,宿主机械半全桩):确认点击后
  (不等下一帧)容器即持 owned 规范名 + 单位腿 + 装备后果腿;
  ``chosen_supply`` 三元组在派发前已由画面 op 写(写点 = 选择点,
  ``op-layer.md`` §2.2 动作事实边界);画面 op 无落地相补写面
  (节点完成门 miss 后零容器写);
- **分层归一三型锁**(``normalize_registry_equip_name``):
  互撞族(垃圾袋/金垃圾袋、生命之花/生命之环、追击/击破星徽)与
  特权/后缀族完美 OCR 恒命中(精确快道);OCR 形变救援(containment
  装饰噪声消解 + LCS 相似唯一命中);多命中拒识返回 ''(fail-closed,
  禁猜)。

报告函数级未解析/内容未知翻来源留证锁 = test_cw_pick_channels_t60
承重,本文件不重复。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_events import (
    normalize_registry_equip_name,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    bench_units_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickSupplyParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenSupplyNode')


def _seeded_gs():
    """剧本容器:bench 两枚 1★银狼 + equips 空读(后果腿合成级联素材)。"""
    session = StrategySession()
    gs = game_state_of(session)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='银狼', star=1, slot=i + 1))
             for i in range(2)]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return session, gs


def _make_match(test_context, monkeypatch, session):
    match = SimpleNamespace(session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    return match


def _units(gs) -> list[tuple[str, int]]:
    return [(u.char_id, u.star) for u in bench_units_of(gs)]


def test_pick_confirm_reports_full_result_immediately(
        test_context, monkeypatch) -> None:
    """pick 即时上报锁:确认点击后(机械半全桩,零落地相)容器即持
    owned 规范名 + 单位腿(1★入席合成级联)+ 装备后果腿(分身墨镜
    → 送 1★银狼)——一口写,无发射/落地两相。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_pick_supply_action as pa,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_env import (
        OverlayPickExecEnv,
    )

    session, gs = _seeded_gs()
    _make_match(test_context, monkeypatch, session)
    host = SimpleNamespace(
        ctx=SimpleNamespace(controller=SimpleNamespace(
            mouse_move=lambda p: None, click=lambda p, **k: None)),
        screenshot=lambda: object(),
        round_by_find_and_click_area=lambda *a, **k: _Area(True),
    )
    env = OverlayPickExecEnv(op=host, match=None, idx=0,
                                target=SimpleNamespace(x=900, y=550),
                                picked=None)
    op = pa.CwActionPickSupplyOp(
        test_context,
        CwActionPickSupplyParam(idx=0, char_name='银狼', norm_item='分身墨镜'),
        env)
    result = _run_node(test_context, op, op.run)
    assert result.is_success
    assert gs.equips.value == ['分身墨镜'], 'owned 即时持规范名(不等下一帧)'
    assert gs.equips.source == 'logic', '入栏 write_logic'
    units = _units(gs)
    assert ('银狼', 2) in units and ('银狼', 1) in units, \
        '单位腿 1★入席合成 2★ + 后果腿送出 1★'


def test_chosen_supply_written_before_dispatch_and_no_landing_phase(
        test_context, monkeypatch) -> None:
    """画面 op 侧锁:chosen_supply 三元组在动作派发前已写(写点 = 选择点,
    ``op-layer.md`` §2.2);选卡派发即终结(_do_action 返回 True);
    节点完成门 miss(act 分发身份安全网)后零容器写(无落地相补写面)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_action_registry,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    session, gs = _seeded_gs()
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(
            decide_supply=lambda: CwActionPickSupplyParam(idx=0, reason='test')))
    match.gs = gs
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True)
    monkeypatch.setattr(sn, 'read_supply_options',
                        lambda ctx, screen: [(opt, SimpleNamespace(x=900, y=550))])
    monkeypatch.setattr(op, '_read_node_bar', lambda screen: None)
    monkeypatch.setattr(op, '_read_refresh_anchor', lambda screen: None)

    chosen_at_dispatch: list = []

    class _ProbeStubOp:
        def execute(self) -> bool:
            chosen_at_dispatch.append(gs.chosen_supply.value)
            return True

    monkeypatch.setattr(cw_action_registry, 'action_op_for',
                        lambda act, ctx, env: _ProbeStubOp())
    _run_node(test_context, op, op.observe)   # 观察 node 装载 obs(report 落容器)
    assert op._do_action() is True, '选卡派发即终结(终结交回)'
    assert chosen_at_dispatch == [('希儿', '星币收集器', True)], \
        'chosen_supply 三元组在派发前已写(写点 = 选择点)'
    write_seq_after_dispatch = gs.write_seq
    # 节点完成门 miss(overlay 已关)= 分发身份安全网 success 交回,
    # 零落地相补写面(证据闩已随即时上报批退役)。
    monkeypatch.setattr(op, '_in_node', lambda screen: False)
    result = _run_node(test_context, op, op.act)
    assert result.is_success, '门 miss = 节点完成 success 交回'
    assert gs.write_seq == write_seq_after_dispatch, \
        '门 miss 后零容器写(无落地相补写面)'


# ==================== 分层归一三型锁 ====================


def test_registry_norm_exact_hits_on_collision_families() -> None:
    """互撞族/特权/后缀族完美 OCR 恒命中(第 1 层精确快道):纯 LCS 判据
    直移 158 名键集时这些名会多命中拒识——精确相等必须先走快道。"""
    for name in ('垃圾袋', '金垃圾袋', '生命之花', '生命之环',
                 '追击星徽', '击破星徽', '昼之半神星徽', '夜之半神星徽',
                 '很硬的甲', '很硬的甲·特权', '分身墨镜', '分身墨镜Max',
                 '数据拷贝仪Pro', '管理员手套ProMax',
                 '白昼·光速螺旋桨', '极·白昼·光速螺旋桨',
                 '财富', '财富(基础)', '穿刺死棘之枪', '穿越死棘之枪'):
        assert normalize_registry_equip_name(name) == name, \
            f'完美 OCR 恒命中(精确快道):{name}'


def test_registry_norm_rescues_ocr_deformation() -> None:
    """OCR 形变救援:containment 层消解装饰噪声(括号/前后缀文案,
    longest-first 使后缀族长名胜出);相似层救援无 containment 命中的
    字形形变(LCS ≥0.75 唯一命中)。"""
    assert normalize_registry_equip_name('【垃圾袋】') == '垃圾袋'
    assert normalize_registry_equip_name('生命之花!') == '生命之花'
    assert normalize_registry_equip_name('获得 信心注入器·特权 x1') \
        == '信心注入器·特权'
    assert normalize_registry_equip_name('极·白昼·光速螺旋桨(已装备)') \
        == '极·白昼·光速螺旋桨', 'longest-first:极·白昼 先于 白昼· 胜出'
    assert normalize_registry_equip_name('折叠小偈') == '折叠小刀', \
        '字形形变相似救援(无 containment 命中,LCS 3/4 唯一)'


def test_registry_norm_multi_hit_refuses() -> None:
    """多命中拒识(fail-closed,禁猜):相似层多命中返回 ''(追击/击破
    星徽互撞形变);containment 并列最长落相似层后仍多命中返回 '';
    注册表外名零命中返回 ''。"""
    assert normalize_registry_equip_name('追 击星徽') == '', \
        '相似层双命中(追击星徽 LCS 1.0 / 击破星徽 0.75)= 拒识'
    assert normalize_registry_equip_name('生命之花与生命之环') == '', \
        'containment 并列最长(两 4 字键)→ 相似层多命中 = 拒识'
    assert normalize_registry_equip_name('星币收集器') == '', \
        '注册表外名零命中 = 拒识(禁猜)'
