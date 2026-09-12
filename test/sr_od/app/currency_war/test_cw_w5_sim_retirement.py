"""W5 sim 退役·桥收敛哨兵(波 5b 重建立并升格;原 T-98 段③哨兵随测试仓
86802d0 瘦身丢失,本文件按其机制原文重建 + 波 5b 双删面升格)。

三扇哨兵门(多/少皆红;少红 = 退役推进,同批删登记项):
- ① 桥(board_state_bridge)残余登记集:文件级扫描 == 登记集,防消点
  批漏删登记项或新回流调用点静默扩面。登记集 = 现实单一源,禁据任何
  docstring 误判消点进度(桥本体 docstring 同句声明)。
- ② 波 5b 双删墓碑:cw_bs_view / cw_expected_state 模块本体已物理删除,
  文件复活或 src 树内 import 回流即红。
- ③ back_size 死字段墓碑:last_state 写点计数钉定 —— back_size 按
  T-23-r1 §⑤.2 版本演进已移除(写读闭环终端消费者零),任何触点回写
  即红;last_state 三写点(prep 观察两处 + 买牌融合段一处)退役挂执行侧
  装配源迁移(ADR-0530 尾批/T-7),计数变化 = 该面推进或扩面,人工对账。
"""
from __future__ import annotations

import re
from pathlib import Path

# ==== ① 桥残余登记集(波 5b 消点后现树实描;文件相对 currency_war 根)====
# 每项带辖域标签:消点推进时按标签找归属批,禁无主红。
_BRIDGE_REGISTERED: dict[str, str] = {
    'kernel/cw_game_state.py': '机制本体(函数定义+退役 docstring)',
    # 波 5b 消点后仍活调用:
    'kernel/cw_economy.py': '活调用·标量投影缝无 session(结构性豁免 '
                           'ADR-0598),退役挂 session 通道批/T-7',
    # kernel/cw_evolution.py 登记项已删:模块本体随 W8(T-7 段2)整模块
    # 退役物理删除,桥引用随之消点(少红=推进协议,同批删登记项)。
    'prep_actions.py': '活调用·根(他批辖域,波 5b 禁触 :289-291 面)',
    'strategies/impl/flow.py': '活调用·策略域辖外',
    'operations/cw_loop.py': '活调用·在飞面他批辖',
    'operations/cw_op/cw_op_buy_cards.py': '活调用·他批辖域',
    'operations/cw_op/cw_shop_action_ops.py': '活调用·他批辖域',
    'operations/cw_screen/cw_screen_invest_strategy.py': '活调用·他批辖域',
    'operations/cw_screen/cw_screen_planner.py': '活调用·他批辖域',
    # 仅注释提及(非调用;登记防误判「文件已清零」):
    'kernel/cw_hp_policy.py': '注释提及(投影过渡语义描述,非调用)',
    'strategies/impl/mandate_v1/shop.py': '注释提及(W6 波3 装箱归属申报)',
}

_ROOT = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
         / 'currency_war')


def test_bridge_remnant_registration_set() -> None:
    """桥残余登记集门:扫描集 == 登记集(多 = 回流/漏登记,少 = 消点推进
    未同步登记)。全部登记项清零后,board_state_bridge 本体随批物理删除
    (其内部消费与删除同批,桥 docstring 同款口径)。"""
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


def test_last_state_write_points_pinned_three() -> None:
    """last_state 写点计数钉定(退役挂执行侧装配源迁移 ADR-0530 尾批/T-7;
    本批不删写点——读者面 ~18 点未迁,先删=断执行侧装配源,设计序见
    GameState-数据结构设计「消费切换余量归属/迁移尾批」)。计数变化 =
    该面推进或扩面,须人工对账后更新钉值。口径 = AST 赋值语句(注释/
    docstring 提及不计,同型误报实证 = cw_loop docstring 内装箱示例)。"""
    import ast
    hits: list[str] = []
    for path in _ROOT.rglob('*.py'):
        rel = path.relative_to(_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Attribute) and target.attr == 'last_state':
                hits.append(f'{rel}:L{node.lineno}')
    assert len(hits) == 3, (
        'last_state 写点数漂移(钉定 3 = cw_screen_prep 观察×2 + '
        f'cw_op_buy_cards 融合段×1),逐条对账: {hits}')
