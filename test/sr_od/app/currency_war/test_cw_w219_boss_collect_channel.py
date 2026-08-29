"""行为锁:简报 boss 位面序真值链(ADR-0397 勘误后设计)。

设计变更背景:ADR-0397 原「简报三卡排列≠位面序」结论系单条日志孤证误判
(对照日志通道不可靠),已被用户 2026-08-28 裁决推翻(详见 ADR-0397 文内
勘误节)。旧锁钉「简报读数不进 session」——用户裁决=设计变更,锁跟设计
不跟旧码,本文件整体改写钉新语义:

- **简报读数=位面序真值进 session**:读侧 ``clean_boss_names_by_lcs`` 清洗
  (参考表 = ``cw_enemy_data.BOSS_MECHANICS`` 规范 boss 名,防 OCR 简称/形变)
  → ``battle_loop.__init__`` copy 进 ``session.briefing_bosses`` →
  ``state.plane_bosses`` → boss_fit;
- **实采通道保留(接管场景重采)**:CollectPlaneIntel 写入端仍在,触发条件
  「新 match 且 session 空」——开局局简报读得时不触发(简报即真值,零额外
  采集),接管局/简报读空时兜底;
- **对账网**:实采完成后与简报读数逐位面 LCS 比对存证(kind='briefing_reconcile'),
  不一致进 defect 台账(L2 留证),门控 config.briefing_reconcile(默认开)。

静态锁模式沿用 inspect.getsource 断言接线形态先例。
"""
import inspect


def test_briefing_bosses_copied_into_session() -> None:
    """锁①(改写):简报位面序真值 copy 进 session(接线在 loop __init__)。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '_session.briefing_bosses = list(self.ctx.cw_briefing_bosses)' in src, (
        '简报真值→session copy 接线消失(boss_fit 失去开局输入,ADR-0397 勘误节)'
    )
    # ctx 简报槽无「取走清空」消费:槽保留作实采对账源;跨局残留由
    # HandleBriefing 每局重读覆写/读空清 None 兜住(该行为有专锁)。
    assert 'self.ctx.cw_briefing_bosses = None' not in src


def test_briefing_read_side_cleans_and_overwrites() -> None:
    """锁②(新):读侧 LCS 清洗接线 + 每局覆写/读空清 None(防跨局残留成假真值)。"""
    from sr_od.application.currency_war.operations.handlers import handle_briefing

    src = inspect.getsource(handle_briefing)
    assert 'clean_boss_names_by_lcs' in src, '简报读数未过 LCS 清洗(简称/形变直进 boss_fit)'
    assert 'self.ctx.cw_briefing_bosses = clean_boss_names_by_lcs(_bosses) if _bosses else None' in src, (
        '读侧覆写/清 None 兜底消失(跨局残留会被 loop copy 成假真值)'
    )


def test_collect_plane_intel_is_takeover_refill_channel() -> None:
    """锁③(语义更新):CollectPlaneIntel 实采写入端在(接管重采/读空兜底)。"""
    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '_sess.briefing_bosses = _names' in src, (
        'CollectPlaneIntel 实采接线消失(接管场景失去重采通道)'
    )
    # 触发条件仍含「session.briefing_bosses 空」:开局局简报读得时 session 已由
    # __init__ 填(不重复采),接管局/读空时兜底——条件消失=简报信任被绕过。
    assert "not getattr(self.ctx.cw_match.session, 'briefing_bosses', None)" in src
    assert 'CollectPlaneIntel(self.ctx)' in src


def test_reconcile_wiring_in_both_collect_paths() -> None:
    """锁④(新):对账网接线在两条实采完成路径上都在(loop 内联块 + takeover 写回)。"""
    from sr_od.application.currency_war.operations import battle_loop
    from sr_od.application.currency_war.operations.entry import (
        takeover_collect_plane_intel,
    )

    assert 'reconcile_briefing_vs_plane_intel(' in inspect.getsource(battle_loop.CurrencyWarRunLoop), (
        'loop 内联实采块缺对账接线'
    )
    assert 'reconcile_briefing_vs_plane_intel(' in inspect.getsource(
        takeover_collect_plane_intel.TakeoverCollectPlaneIntel.write_back), (
        'takeover 写回缺对账接线'
    )


def test_session_collected_bosses_flow_to_state_plane_bosses() -> None:
    """锁⑤(原锁③保留;default 栈退役批重钉):session.briefing_bosses
    (位面序真值)→ state.plane_bosses。注入点已从 default update_target
    平移到观测层(cw_observation.read_game_state,对 session 透传无条件注入)
    ——重钉为源级锁,防注入链再断。"""
    import inspect

    from sr_od.application.currency_war import cw_observation
    src = inspect.getsource(cw_observation)
    assert "state.plane_bosses = list(_sess.briefing_bosses)" in src, (
        '观测层注入点丢失:session.briefing_bosses 真值不再流向 state.plane_bosses'
    )
