"""W5 sim 退役·桥收敛哨兵(波 5b 重建立并升格;原 T-98 段③哨兵随测试仓
86802d0 瘦身丢失,本文件按其机制原文重建 + 波 5b 双删面升格;T-169 桥
本体删除批起 ① 门转墓碑)。

三扇哨兵门(多/少皆红;少红 = 退役推进,同批删登记项):
- ① 桥(board_state_bridge)src 零字样墓碑:src 树文件级扫描恒空集
  ——登记集已随 T-169 清零、桥本体已物理删除,此后 src 树任何文件
  再现 board_state_bridge 字样 = 回流/复活,即红。
- ② 波 5b 双删墓碑:cw_bs_view / cw_expected_state 模块本体已物理删除,
  文件复活或 src 树内 import 回流即红。
- ③ back_size 死字段墓碑 —— back_size 按
  T-23-r1 §⑤.2 版本演进已移除(写读闭环终端消费者零),任何触点回写
  即红。(last_state 写点计数钉定已随 T-170 链退役批退役:三写点与
  遗留读者面收口,防复活断言 = test_cw_game_state 全仓零标识符锁。)
"""
from __future__ import annotations

import re
from pathlib import Path

# ==== ① 桥零字样墓碑(T-169:登记集消点至零、本体已随批物理删除)====
# 历史登记集(kernel/cw_game_state.py 桥本体)已清零摘除;本表留空 =
# 墓碑态,src 树再现 board_state_bridge 字样即红(含 docstring 提及,
# 防旧注释面残留误导消点判断)。
_BRIDGE_REGISTERED: dict[str, str] = {}

_ROOT = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
         / 'currency_war')


def test_bridge_remnant_registration_set() -> None:
    """桥零字样墓碑门(T-169 起由登记集门转墓碑):扫描集恒空。红 =
    src 树再现 board_state_bridge 字样(本体复活/新调用点/残留提及)。"""
    scanned: set[str] = set()
    for path in _ROOT.rglob('*.py'):
        rel = path.relative_to(_ROOT).as_posix()
        if 'board_state_bridge' in path.read_text(encoding='utf-8'):
            scanned.add(rel)
    registered = set(_BRIDGE_REGISTERED)
    extra = sorted(scanned - registered)
    missing = sorted(registered - scanned)
    assert not extra, f'桥引用出现于登记集外文件(回流或漏登记): {extra}'
    assert not missing, (f'登记集内文件已无桥引用 = 消点推进,同批删登记项'
                         f'(登记时带辖域标签找归属批): {missing}')


def test_w5b_double_deletion_tombstones() -> None:
    """波 5b 双删墓碑:两模块本体不存在 + src 树零 import 回流。"""
    assert not (_ROOT / 'kernel' / 'cw_bs_view.py').exists(), \
        'cw_bs_view.py 应已物理删除(波 5b 双删)'
    assert not (_ROOT / 'kernel' / 'cw_expected_state.py').exists(), \
        'cw_expected_state.py 应已物理删除(波 5b 双删;apply_op_effect 迁 ' \
        'kernel/cw_exec_state)'
    for mod in ('cw_bs_view', 'cw_expected_state'):
        hits: list[str] = []
        for path in _ROOT.rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            if re.search(rf'import\s+\S*{mod}\b|from\s+\S*{mod}\s+import', text):
                hits.append(path.relative_to(_ROOT).as_posix())
        assert not hits, f'{mod} import 回流: {hits}'


def test_back_size_dead_field_tombstone() -> None:
    """back_size 死字段墓碑(波 5b 版本演进移除,T-23-r1 §⑤.2):src 树零
    触点回写;两载体字段位断言(Snapshot / PrepObservation)。"""
    import dataclasses as _dc

    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        PrepObservation,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.contracts import (
        SNAPSHOT_SCHEMA_VERSION,
        Snapshot,
    )
    assert SNAPSHOT_SCHEMA_VERSION >= 2, \
        'back_size 移除按契约升版(字段只增不改删,移除须动版本号)'
    assert 'back_size' not in {f.name for f in _dc.fields(Snapshot)}
    assert 'back_size' not in {f.name for f in _dc.fields(PrepObservation)}
    hits: list[str] = []
    for path in _ROOT.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        hits += [f'{path.relative_to(_ROOT).as_posix()}:{m.start()}'
                 for m in re.finditer(r'\bback_size\s*=[^=]', text)]
    assert not hits, f'back_size 触点回写(死字段复活): {hits}'


# (test_scalar_projection_equivalent_to_bridge_projection 已随 T-169 桥
#  本体删除退役:该锁 = scalar_projection_state 对旧桥投影的差分等价
#  锁,对拍对象随本体消亡,锁语义无现存载体可继承——非重锚而是退役;
#  字段契约单一源 = kernel scalar_projection_state docstring 自辖。)


# (test_last_state_write_points_pinned_three 已随 T-170 链退役批退役:
#  三写点(cw_screen_prep 观察×2 + cw_op_buy_cards 融合段×1)与全部
#  遗留读者已收口,写端退役 + StrategySession 槽本体删除——「写点计数
#  钉定」失去对象,非重锚而是退役。防复活断言面按原申报扩展 =
#  test_cw_game_state.test_ast_currency_war_reads_no_last_state(CW 包
#  全仓零标识符命中,永久锁);装配源四文件窄锁(下方)保留作双保险。)


def test_assembly_source_files_zero_last_state() -> None:
    """装配源迁移完成锁(T-146 尾批,ADR-0530 决策2 换源核销):执行侧
    装配源四文件(cw_op_deploy/cw_op_equip_all/prep_actions 执行器/
    strategies flow)last_state 读点归零——属性加载与 getattr 字符串
    两形态全扫(注释/docstring 提及不计)。红 = 装配源回流或迁移面
    扩入新读者,人工对账。"""
    import ast
    _FILES = ('operations/cw_op/cw_op_deploy.py',
              'operations/cw_op/cw_op_equip_all.py',
              'prep_actions.py',
              'strategies/impl/flow.py')
    for rel in _FILES:
        tree = ast.parse((_ROOT / rel).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            ok = not (isinstance(node, ast.Attribute)
                      and node.attr == 'last_state')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == 'getattr' and len(node.args) >= 2:
                a = node.args[1]
                ok = ok and not (isinstance(a, ast.Constant)
                                 and a.value == 'last_state')
            assert ok, f'{rel}:L{node.lineno} last_state 读点回流(装配源应全容器)'
