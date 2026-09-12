"""特殊投资策略商店采集停机钩子测试(临时捕获钩子,od-dev-stop-hooks §2.1)。

被测 = ``cw_screen_prep.CwScreenPrep._spec_invest_shop_stop_hook``(独立钩子方法)
+ ``visit_open_shop`` 入口挂点(商店画面处理最前,click 前)。

锁两面(用户 2026-09-10 指令:特殊投资策略逐条确定采证,采够删整段):
①在场效果清单含名单效果 → 采集(商店/备战席双截图 + 效果清单转储 +
state 账本引用入 flag)+ ``stop_running``;不含 → 直通 None 零副作用;
②防重采:同一效果组合进程内只停一次,组合变化(新增名单效果)再停。

本测试文件属临时段:钩子整段删除时本文件一并删除,不留孤儿锁。
"""
from types import SimpleNamespace

import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.kernel import cw_obs_core
from sr_od.application.currency_war.kernel.cw_game_state import board_state_of
from sr_od.application.currency_war.kernel.cw_effect_inventory import ActiveEffect
from sr_od.application.currency_war.kernel.cw_investments import STRATEGY_EFFECTS
from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep

#: 购买经验面板三 area 的 screen_info pc_rect(生产值快照,仅供 stub 裁切)
_XP_AREA_RECTS = {
    '备战标识-购买经验': Rect(229, 841, 363, 878),
    '文本-升级所需经验': Rect(228, 933, 363, 962),
    '文本-购买经验金币数': Rect(228, 965, 364, 1016),
}


def _entry(spec_name: str) -> ActiveEffect:
    """按注册表规范名建一条在场效果实例(source/acquired_t 取生产登记形态)。"""
    return ActiveEffect(spec=STRATEGY_EFFECTS[spec_name], source='strategy',
                        acquired_t=5, remaining_nodes=None, remaining_uses=None)


def _prep(monkeypatch, tmp_path, entries: list, *, frame=None, area_rects=None):
    """免 SrContext 构造的 CwScreenPrep(object.__new__ + stub;test_cw_equip_expect
    _stub_director 同款)+ stub 接缝:screenshot/ctx.run_context/哨兵目录/
    防重采集合/screen_info area 全部隔离进 tmp_path 与本测内。
    area_rects=None → 生产三 rect 快照;传 {} → 全缺失态。返回 (pd, stops)。"""
    monkeypatch.setattr(cw_screen_prep.CwScreenPrep, '_SPEC_INVEST_CAPTURED', set())
    sentinel_dir = tmp_path / 'sentinel'
    monkeypatch.setattr(cw_screen_prep.CwScreenPrep, '_spec_invest_sentinel_dir',
                        lambda *a, **k: sentinel_dir)
    rects = _XP_AREA_RECTS if area_rects is None else area_rects
    monkeypatch.setattr(cw_obs_core, '_area_rect',
                        lambda ctx, name, screen_name=None: rects.get(name))
    pd = object.__new__(cw_screen_prep.CwScreenPrep)
    sess = SimpleNamespace()
    board_state_of(sess).effects.entries = list(entries)
    pd._match = lambda: SimpleNamespace(session=sess)
    stops: list[str] = []
    pd.ctx = SimpleNamespace(run_context=SimpleNamespace(
        stop_running=lambda reason='': stops.append(reason)))
    if frame is None:
        # 1080p 全帧尺寸:面板特写裁切(y 821-1036)需在界内
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    pd.screenshot = lambda: frame
    return pd, stops, sentinel_dir


def test_watch_hit_captures_stops_and_dedups(tmp_path, monkeypatch) -> None:
    """在场含名单效果(采购专员·金)→ 采集 + stop_running;同组合第二次调用
    防重采直通(进程内存,重启清零=允许重采)。"""
    pd, stops, sdir = _prep(monkeypatch, tmp_path, [_entry('采购专员·金')])
    res = pd._spec_invest_shop_stop_hook()
    assert res is not None and '特殊投资策略采集停机' in res, f'触发停机回执: {res}'
    assert '采购专员·金' in res, '回执含触发效果名'
    assert stops == ['hook:spec_invest_shop'], f'stop_running 恰一次: {stops}'
    # sentinel 五件:商店/备战席全帧双截图 + 购买经验面板特写 + flag + 效果清单转储
    pngs = sorted(p.name for p in sdir.glob('*.png'))
    assert len(pngs) == 3, f'商店+备战席双截图+经验面板特写落盘: {pngs}'
    assert any(n.startswith('shop_') for n in pngs), '商店画面截图在'
    assert any(n.startswith('bench_') for n in pngs), '备战席画面截图在'
    assert any(n.startswith('xp_panel_') for n in pngs), '购买经验面板特写在'
    flag = sdir / 'spec_invest_shop_hook.flag'
    assert flag.exists(), 'flag 主哨兵落盘'
    text = flag.read_text(encoding='utf-8')
    for needle in ('[HOOK-STOP]', '临时捕获', '钩子位置', '处理步骤', '删除条件',
                   '采购专员·金'):
        assert needle in text, f'flag 三要素+触发名单含 {needle!r}:\n{text}'
    dump = sdir / 'effects_dump.json'
    assert dump.exists(), '效果实例清单转储落盘'
    dump_text = dump.read_text(encoding='utf-8')
    assert '201201' in dump_text and '采购专员·金' in dump_text, \
        f'转储含 spec id+name: {dump_text}'
    # 防重采:同组合第二次调用直通,不重复停机不重复采集
    res2 = pd._spec_invest_shop_stop_hook()
    assert res2 is None, '同效果组合已采集 → 不再触发'
    assert stops == ['hook:spec_invest_shop'], '防重采:不重复 stop_running'
    assert len(list(sdir.glob('*.png'))) == 3, '防重采:不重复采集截图'


def test_watch_list_contains_exp_is_wealth() -> None:
    """名单含「经验就是财富」(编排者 2026-09-10 追加:145 局零样本需持卡采证;
    经验改道核销采证入口)。"""
    assert '经验就是财富' in cw_screen_prep.CwScreenPrep._SPEC_INVEST_WATCH_NAMES


def test_xp_panel_area_missing_still_stops(tmp_path, monkeypatch) -> None:
    """screen_info 三 area 全缺失 → 跳过特写(双全帧仍在),照常停机+flag 在
    (特写是采集增强项,失败不拦停机)。"""
    pd, stops, sdir = _prep(monkeypatch, tmp_path, [_entry('采购专员·金')],
                            area_rects={})
    res = pd._spec_invest_shop_stop_hook()
    assert res is not None, 'area 缺失仍停机'
    assert stops == ['hook:spec_invest_shop']
    pngs = sorted(p.name for p in sdir.glob('*.png'))
    assert len(pngs) == 2, f'双全帧仍在、无特写: {pngs}'
    assert (sdir / 'spec_invest_shop_hook.flag').exists(), 'flag 主哨兵在'


def test_watch_miss_passes_through(tmp_path, monkeypatch) -> None:
    """在场效果不在名单(免战牌)→ 直通 None:不停机、零采集零落盘。"""
    pd, stops, sdir = _prep(monkeypatch, tmp_path, [_entry('免战牌')])
    res = pd._spec_invest_shop_stop_hook()
    assert res is None, '非名单效果直通'
    assert stops == [], '直通不停机'
    assert not sdir.exists() or not list(sdir.iterdir()), '零 sentinel 落盘'


def test_empty_inventory_passes_through(tmp_path, monkeypatch) -> None:
    """空效果清单(未登记/登记面缺位的局)→ 直通 None,不炸执行链。"""
    pd, stops, _sdir = _prep(monkeypatch, tmp_path, [])
    assert pd._spec_invest_shop_stop_hook() is None
    assert stops == []


def test_new_combo_triggers_again(tmp_path, monkeypatch) -> None:
    """组合变化(在原组合上新增名单效果 商业间谍)→ 视为新组合再停再采。"""
    pd, stops, sdir = _prep(monkeypatch, tmp_path, [_entry('采购专员·金')])
    assert pd._spec_invest_shop_stop_hook() is not None
    board_state_of(pd._match().session).effects.entries.append(_entry('商业间谍'))
    res2 = pd._spec_invest_shop_stop_hook()
    assert res2 is not None, '效果组合变化 → 允许再采'
    assert stops == ['hook:spec_invest_shop', 'hook:spec_invest_shop'], \
        f'新组合再停: {stops}'


def test_no_match_passthrough(tmp_path, monkeypatch) -> None:
    """无对局(match=None)→ 直通 None(离线/局外上下文不炸)。"""
    pd, stops, _sdir = _prep(monkeypatch, tmp_path, [_entry('采购专员·金')])
    pd._match = lambda: None
    assert pd._spec_invest_shop_stop_hook() is None
    assert stops == []


def test_frame_missing_still_stops(tmp_path, monkeypatch) -> None:
    """截图通道缺失(frame=None)→ flag 主哨兵仍落盘 + 照常停机
    (截图失败不拦停机;证据缺失显式留痕,同 launch_dead 通道纪律)。"""
    pd, stops, sdir = _prep(monkeypatch, tmp_path, [_entry('采购专员·金')],
                            frame=None)
    pd.screenshot = lambda: None
    res = pd._spec_invest_shop_stop_hook()
    assert res is not None, '证据缺失仍停机(停机是第一动作)'
    assert stops == ['hook:spec_invest_shop']
    assert (sdir / 'spec_invest_shop_hook.flag').exists(), 'flag 主哨兵在'


def test_mount_wired_in_visit_open_shop() -> None:
    """挂点接线锁:visit_open_shop(商店访问编排单一源,显式开店与 0n 转交
    共用)入口调用钩子方法,且位于买牌循环(run_buy_waves)之前——
    钩子段删除时本测一并删(临时段,不留孤儿锁)。"""
    import inspect
    src = inspect.getsource(cw_screen_prep.CwScreenPrep.visit_open_shop)
    assert '_spec_invest_shop_stop_hook' in src, 'visit_open_shop 入口挂点在位'
    # rindex = 实际调用点(docstring 里也提到 run_buy_waves,不作位判据)
    assert src.index('_spec_invest_shop_stop_hook') < src.rindex('run_buy_waves'), \
        '挂点先于买牌循环(画面处理最前,click 前)'
    assert hasattr(cw_screen_prep.CwScreenPrep, '_spec_invest_shop_stop_hook'), \
        '钩子为独立方法'
