# -*- coding: utf-8 -*-
"""r330 钩子帧态门测试(用户循环:稳定→观察→对账&hook)。"""
from __future__ import annotations

import inspect


def test_is_prep_like_frame_exists() -> None:
    """共享帧态判据在 cw_obs_core(id_mark 精准判定)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert hasattr(cw_obs_core, 'is_prep_like_frame')
    src = inspect.getsource(cw_obs_core.is_prep_like_frame)
    assert 'get_match_screen_name' in src   # 框架 id_mark 体系


def test_layout_hook_gated() -> None:
    """back_layout 停机钩子过帧态门(过渡帧跳过)。件③(W209/ADR-0385)重构:
    触发判据从「level 对应档无档」改到双通道对账原始格数 n_raw 无档(=7,
    钻石+1 局);帧态门(is_prep_like_frame)语义不变。"""
    from sr_od.application.currency_war.obs import cw_identity_obs
    src = inspect.getsource(cw_identity_obs.read_deployed_chars)
    assert 'is_prep_like_frame' in src
    assert "n_raw" in src, '触发判据应消费 resolve_back_slots 的 n_raw(双通道)'


def test_bookcard_stop_hook_removed() -> None:
    """bookcard 确认停机钩子退役(2026-08-30 开启语义确认,自动处理链接管):
    read_bench_chars 不再有停机逻辑;处理链接线在 battle_loop + handlers。
    (原锁 r133→r330「钩子过帧态门」钉的是停机语义,钩子删除后语义换新。)"""
    from sr_od.application.currency_war.obs import cw_identity_obs
    src = inspect.getsource(cw_identity_obs.read_bench_chars)
    assert 'bookcard_confirm' not in src   # 停机钩子段已删
    assert 'find_bookcards' in src   # 书册卡仍入 _obj_slots( summon 钩子不拦)
    assert src.count('is_prep_like_frame') >= 1   # summon 钩子帧态门仍在
    from sr_od.application.currency_war.operations import battle_loop
    loop_src = inspect.getsource(battle_loop)
    assert 'HandleBookcard' in loop_src   # 处理链接线(0k 分支 + 预清场)


def test_star_hook_gated() -> None:
    """star 回退留证钩子过帧态门(动画帧不留证)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    src = inspect.getsource(cw_reconcile._star_stop_hook)
    assert 'is_prep_like_frame' in src
