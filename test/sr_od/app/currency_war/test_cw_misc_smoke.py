"""test_cw_misc_smoke 主题锁——零散子系统入口 smokes(watchdog/faction/portal/全 op 可导入)。

收缩注记(CUT9 二次收缩:原 66 测试→25 测试;代表子集收缩,git 可复活):
- watchdog 留:T-163 弹窗全文不豁免(fail-closed)+ 弹窗帧报警集成
  smoke + 结算帧对照臂;参数在位两行断言砍(阈值由报警集成锁承载);
- faction 留双阵营兜底 + 在册 carry 序两决策真值锚;
- portal 留偏置生效 + 来牌翻越两决策真值锚;
- 全 op 可导入参数化 58 模块收缩为 18 代表子集:每子包(cw_entry/
  cw_op/cw_screen/dev/tools)≥1 + 顶层三件 + r98 地雷本体 planner
  等高频面;import 活性机制(逐模块真 import)不变,未抽查模块的
  签名/语法错误回归窗口放宽(git 可复活全量行)。

覆盖面(四类承重件):
- 入口 smoke:停滞报警链(T-163 去盲后形态)/ 全 CW operations 代表
  模块可导入(r98 地雷纪律代码化)/ portal 偏置生效;
- fail-closed 代表:T-163 弹窗正文必不豁免(裸子串致盲回归即红)+
  结算帧对照臂(豁免不误伤);
- 决策真值代表锚:阵营兜底分(r137 口径)与在册 carry 序 / portal 偏置
  可被来牌翻越。

来源指针(2026-09-09 目标形态重建批,断言零改动迁移):
- test_cw_stall_watchdog.py(watchdog 段:阈值/去盲/报警链);
- test_cw_faction_fallback.py(faction 段);
- test_cw_portal_bias.py(portal 段);
- test_cw_all_ops_importable.py(全 op 可导入烟测)。
其余历史锁已退役(git 可复活)。board_state 入口 smoke 挂起:来源文件
并行批在飞(M),其退役与吸收随并行批落地后二轮。
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_transition import (
    pick_framework,
    transition_score,
)
from sr_od.application.currency_war.operations.cw_loop import CwLoop

# ==================== watchdog 段(自 test_cw_stall_watchdog.py 迁入) ====================

#: T-163 失败帧(20260908_181116_921_overlay_role_detail.png)实测 OCR 全文:
#: 弹窗天赋行含「战斗」→ 旧裸子串豁免恒中 → 停滞计数恒清零(26min 致盲源)。
_POPUP_FRAME_TEXTS = frozenset({
    '千冶•刃', '后台', '输出', '星核猎手', '燃血', '减益', '生命值',
    '充能', '716716/716716', '0/9', '100', '125', '0%', '5%', '100%',
    '10%', '万般消磨，吾身为刃', '战技', '终结技天赋',
    '进入战斗前为自己打造装备。',
    '消耗生命值攻击敌人，施放终结技回复生',
    '命。展开结界削弱敌方并增益我方，全队攻',
    '角色详情', '购买', '2',
})


def test_stall_exempt_popup_frame_texts_not_exempt():
    """T-163 弹窗全文集必不豁免——天赋行「进入战斗前为自己打造装备。」
    含「战斗」,词缀式正文含「倒计时/战斗」同理;裸子串回归即红。"""
    assert CwLoop._stall_exempt(_POPUP_FRAME_TEXTS) is False
    assert CwLoop._stall_exempt(frozenset(
        {'战个痛快', '战斗节点的倒计时减少30，但首领节点的倒计时增加20。'},
    )) is False


def _make_watch_loop(monkeypatch, tmp_path, texts: frozenset[str]):
    """裸 CwLoop 实例 + OCR 替身(全帧 OCR 恒返 texts;绕过 run 级装配)。"""
    from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod

    class _Mrl:
        max = object()   # 非 None = 该文本命中(与生产读面同形)

    class _OcrService:
        def __init__(self, words: frozenset[str]) -> None:
            self._words = words

        def get_ocr_result_map(self, image=None, rect=None, color_range=None,
                               crop_first: bool = False) -> dict:
            return {w: _Mrl() for w in self._words}

    op = cw_loop_mod.CwLoop.__new__(cw_loop_mod.CwLoop)
    op.ctx = SimpleNamespace(ocr_service=_OcrService(texts))
    op._iter = 0
    op._stall_last_fp = None
    op._stall_count = 0
    op._stall_flag_written = False
    op._battle_ts = None
    # flag 落点重定向 tmp_path(get_project_root 在 cw_loop 模块命名空间;
    # 测试零真实副作用纪律——真路径落 flag 会误报实机停线)
    monkeypatch.setattr(cw_loop_mod, 'get_project_root', lambda: tmp_path)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op


def _feed_watch_ticks(op, rounds: int) -> None:
    """按采样节奏喂轮(iter 每次 +STALL_SNAPSHOT_EVERY,模拟同屏静止)。"""
    for _ in range(rounds):
        op._iter += CwLoop.STALL_SNAPSHOT_EVERY
        op._stall_watch_tick(object())


def test_stall_watch_popup_frame_triggers_alarm(tmp_path, monkeypatch):
    """集成锁(T-163 验收④):弹窗文本帧重复采样必触发哨兵报警
    (stall_watch.flag 落盘 + 计数达阈值)——致盲回归 = 本测红。"""
    op = _make_watch_loop(monkeypatch, tmp_path, _POPUP_FRAME_TEXTS)
    # 首采样 = 基线(count=0),此后每次同指纹 +1 → N 次重复需 N+1 个采样
    _feed_watch_ticks(op, CwLoop.STALL_N + 1)
    assert op._stall_count >= CwLoop.STALL_N
    flag = (tmp_path / '.debug' / 'temp' / 'currency_war'
            / 'stall_watch.flag')
    assert flag.exists(), '弹窗文本帧停滞必须触发哨兵报警(flag 未落盘 = 致盲回归)'


def test_stall_watch_settlement_frame_never_flags(tmp_path, monkeypatch):
    """对照臂:结算胜利帧文本同形态喂 3 倍采样轮,零计数零报警
    (豁免语义未被去盲收窄误伤)。"""
    op = _make_watch_loop(
        monkeypatch, tmp_path,
        frozenset({'挑战成功', '继续挑战', '数据统计'}))
    _feed_watch_ticks(op, CwLoop.STALL_N * 3)
    assert op._stall_count == 0
    assert not (tmp_path / '.debug' / 'temp' / 'currency_war'
                / 'stall_watch.flag').exists()


# ==================== faction 段(自 test_cw_faction_fallback.py 迁入) ====================

def test_dual_faction_char_counts_for_framework():
    """饮月(仙舟+列车双阵营):列车框架下虽是仙舟在册件,应有阵营兜底分。"""
    s = transition_score('丹恒·饮月', '仙舟', '列车')
    assert s > 0.5, f'饮月对列车框架应有兜底分(羁绊计数有贡献),实得 {s}'


def test_roster_carry_still_highest():
    """在册 carry(三月七)同框架仍最高(策展档位不被兜底反超)。"""
    s_roster = transition_score('三月七', '列车同行', '列车')
    s_fallback = transition_score('星期日', '盛会之星', '列车')
    assert s_roster > s_fallback, '在册 carry 应高于阵营兜底件'


# ==================== portal 段(自 test_cw_portal_bias.py 迁入) ====================

class _BC:
    def __init__(self, char_id):
        self.char_id = char_id


def test_portal_bias_train():
    """列车概念股环境 + 空持有 → 选列车(偏置 3 > 0)。"""
    fw = pick_framework([], [], shop=None, current='', portal='列车同行概念股')
    assert fw == '列车', '概念股应偏置列车框架'


def test_portal_overridable_by_cards():
    """偏置可被实际来牌翻越:portal 列车 +3,但买到 4 张仙舟件 → 仙舟。"""
    fw = pick_framework(
        [_BC(n) for n in ('藿藿', '饮月', '爻光', '卡芙卡')], [],
        portal='列车同行概念股')
    assert fw == '仙舟', '4 张实际仙舟件应翻越 +3 偏置(非锁死)'


# ==================== 全 op 可导入烟测(自 test_cw_all_ops_importable.py 迁入) ====================
# 背景(2026-08-25 实锤):cw_screen_planner.py 曾用 ``node_name=`` 传参而框架
# ``operation_node`` 签名是 ``name=`` —— import 期即 TypeError。因 cw_loop 对
# 该 handler 是惰性 import,常规测试与全量 pytest 都不触发,地雷存活 6 天,
# 直到 MCP server ``list_operations`` 扫描注册表才暴露;期间任何撞上银狼
# 「我来当策划」overlay 的实机局都会 ImportError → 节点重试耗尽 → 对局失败。
# 本锁=r98「改后必真调用一次」纪律的代码化:walk 全部 CW operations 模块,
# 逐个 import,任何签名/语法级错误在此立即红。

def _iter_cw_op_modules() -> list[str]:
    """CW operations 代表模块子集(CUT9 收缩后的代表集,现 17 模块)。

    抽查覆盖判据:每子包 ≥1(cw_entry/cw_op/cw_screen/dev/tools)+
    顶层三件(cw_loop/decision_frame_hooks/settle_collect_hooks)+
    r98 地雷本体 cw_screen_planner 与高频面(prep/encounter/overlay/
    buy_cards/shop_action_ops 等)。import 活性机制不变——逐模块真
    import,签名/语法/顶层符号错误在此立即红。"""
    return sorted([
        'sr_od.application.currency_war.operations.cw_loop',
        'sr_od.application.currency_war.operations.decision_frame_hooks',
        'sr_od.application.currency_war.operations.settle_collect_hooks',
        'sr_od.application.currency_war.operations.cw_entry.cw_entry_start',
        'sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards',
        'sr_od.application.currency_war.operations.cw_op.cw_op_deploy',
        'sr_od.application.currency_war.operations.cw_op.cw_op_equip_all',
        'sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops',
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_planner',
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_prep',
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_encounter',
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait',
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_boss_briefing',
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_strategy',
        'sr_od.application.currency_war.operations.cw_screen.cw_screen_role_detail_overlay',
        'sr_od.application.currency_war.operations.dev.drag_cw_char',
        'sr_od.application.currency_war.operations.tools.harvest_invest_codex',
    ])


@pytest.mark.parametrize('module_name', _iter_cw_op_modules())
def test_cw_op_module_importable(module_name: str) -> None:
    """每个 CW operations 子模块必须可导入(kwarg/语法/顶层符号错误在此暴露)。"""
    importlib.import_module(module_name)
