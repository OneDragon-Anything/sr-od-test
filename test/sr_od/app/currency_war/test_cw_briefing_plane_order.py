"""行为锁:简报 boss 位面序真值——LCS 清洗与对账网(ADR-0397 勘误节)。

钉三件事:
1. ``clean_boss_names_by_lcs``:简称/形变归一到 ``cw_enemy_data.BOSS_MECHANICS``
   规范 boss 名(boss_fit 消费端名字空间),归一不过阈值原名透传(防误配守卫),
   顺序原样保留(= 位面序);
2. ``briefing_reconcile_pairs``:逐位面配对(简报读数 vs 实采真值),None 不可判
   不猜,不一致可检出;
3. 对账门控 config.briefing_reconcile 默认开(验证期),且进 save 持久化。
"""
from __future__ import annotations


def test_lcs_clean_maps_abbreviations_to_canonical() -> None:
    """简称(简报卡名常见形态)归一到规范公司名;已是规范名原样返回。"""
    from sr_od.application.currency_war.cw_briefing_obs import clean_boss_names_by_lcs

    out = clean_boss_names_by_lcs(['造梦互动', '深穹智械', '巨鹿生物制药'])
    assert out == ['造梦互动娱乐', '深穹智械科技', '巨鹿生物制药'], (
        f'LCS 归一结果不符预期:{out}'
    )


def test_lcs_clean_unmatched_passes_through_in_order() -> None:
    """归一不过阈值的读数原名透传(不硬猜),顺序原样保留(位面序不被打乱)。"""
    from sr_od.application.currency_war.cw_briefing_obs import clean_boss_names_by_lcs

    out = clean_boss_names_by_lcs(['XYZ', '绘师家族产业', '火线动力机甲'])
    assert out == ['XYZ', '绘师家族产业', '火线动力机甲'], f'透传/顺序被破坏:{out}'


def test_reconcile_pairs_mismatch_detectable() -> None:
    """逐位面配对:一致 True / 不可判 None / 不一致 False 三态齐全。"""
    from sr_od.application.currency_war.cw_briefing_obs import briefing_reconcile_pairs

    pairs = briefing_reconcile_pairs(
        ['造梦互动', None, '完全不同'],
        ['造梦互动娱乐', None, '绘师家族产业'])
    assert [(p['plane'], p['match']) for p in pairs] == [(1, True), (2, None), (3, False)], (
        f'配对三态不符:{pairs}'
    )


def test_reconcile_pairs_no_briefing_all_undecidable() -> None:
    """简报未读得(None)→ 全部不可判,不产生伪不一致。"""
    from sr_od.application.currency_war.cw_briefing_obs import briefing_reconcile_pairs

    pairs = briefing_reconcile_pairs(None, ['巨鹿生物制药', None, '绘师家族产业'])
    assert all(p['match'] is None for p in pairs), f'简报空读不应产生判定:{pairs}'


def test_reconcile_gate_default_on_and_persisted() -> None:
    """门控默认开(验证期积累配对证据),且 save() 持久化(yml 可关)。

    持久化走静态锁(inspect save 源码)——不真调 save(),避免测试写真实 config 目录。
    """
    import inspect

    from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig

    cfg = CurrencyWarConfig()
    assert cfg.briefing_reconcile is True, '对账开关应默认开(验证期)'
    assert "'briefing_reconcile'" in inspect.getsource(CurrencyWarConfig.save), (
        '对账开关未持久化(yml 关不掉)'
    )
