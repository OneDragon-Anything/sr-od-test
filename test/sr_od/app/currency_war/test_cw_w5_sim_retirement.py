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

# ==== ① 桥残余登记集(T-146 装配源迁移后实描;文件相对 currency_war 根)====
# 每项带辖域标签:消点推进时按标签找归属批,禁无主红。
_BRIDGE_REGISTERED: dict[str, str] = {
    # 桥本体(函数定义 + 退役 docstring)。src 活调用面已随 T-146 清零
    #(prep 根/cw_loop 双点/shop_action_ops/invest_strategy/planner/
    # flow 三 shim/cw_op_buy_cards fp 遥测全消;末项 = T-163 删帧链后
    # 入口帧合成进容器单例,fp 读直取单例)。本体物理删除挂「测试仓
    # harness 改指批」——22 测试文件 + fixtures 经桥构造容器夹具
    #(T-83 harness 波在用),删除须与测试仓改指同批,防夹具断链。
    'kernel/cw_game_state.py': '桥本体(函数定义+退役 docstring;删除挂测试仓 harness 改指批)',
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


def test_scalar_projection_equivalent_to_bridge_projection() -> None:
    """标量投影容器等价锁(T-145 766 缝退役):kernel scalar_projection_
    state 的输出与旧载体「惰性构造 CwWorkFrame + board_state_bridge 装箱」
    的投影**逐字段等价**——值/来源/evidence/工程结构经 full_state_snapshot
    逐项对拍。字段契约单一源 = scalar_projection_state docstring;桥本体
    映射将来变更时本锁强制两装配同批对账(禁静默漂移)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        board_state_bridge,
        scalar_projection_state,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame

    cases = [
        # (全参典型帧 / 全缺省 strategies=None / 空表 strategies=[]——
        #  空表与 None 同判不写 active_strategies,镜像桥行为)
        {'gold': 73, 'level': 5, 'hp': 82, 'plane': 1, 'round_num': 3,
         'strategies': ['淘金客', '定期福利']},
        {'gold': 0, 'level': 3, 'hp': 80, 'plane': 2, 'round_num': 7,
         'strategies': None},
        {'gold': 51, 'level': 7, 'hp': 44, 'plane': 1, 'round_num': 9,
         'strategies': []},
    ]
    for kw in cases:
        bs_new = scalar_projection_state(**kw)
        frame = CwWorkFrame(gold=kw['gold'], level=kw['level'],
                            hp=kw['hp'], plane=kw['plane'],
                            round_num=kw['round_num'])
        frame.active_strategies = list(kw['strategies'] or [])
        bs_old = board_state_bridge(frame)
        snap_new = bs_new.full_state_snapshot()
        snap_old = bs_old.full_state_snapshot()
        assert snap_new == snap_old, (
            f'标量投影容器与桥投影失配(全参支 {kw}):'
            f'new={snap_new!r} old={snap_old!r}')
        assert bs_new.bs_schema == bs_old.bs_schema


def test_last_state_write_points_pinned_three() -> None:
    """last_state 写点计数钉定(装配源读者面已随 T-146 尾批迁容器单例;
    写点存续依据 = 遗留读者面仍在:环守卫指纹/收口假局判定/局终
    MatchOutcome/identity_obs 等级链/exec_state gold 推进/词缀与效果
    账本引导窗回退/battle_wait/screen_prep 杂读/overlay_confirm——
    该面语义逐点钉在帧上(如 T-167 gold 指纹钉死),退役 = 各点独立
    重验,归「last_state 链退役收尾批」(未立项,候编排者)。计数变化
    = 该面推进或扩面,须人工对账后更新钉值。口径 = AST 赋值语句
    (注释/docstring 提及不计,同型误报实证 = cw_loop docstring 内装箱
    示例)。"""
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
