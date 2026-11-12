"""货币战争复盘渲染器(tools/cw/replay_to_md.py)fixture 单测。

测试文件组织说明:tools/ 目录无 src 镜像先例(tools 不是 src-layout 包),
无法按「src 路径同源镜像」落位,按工具名组织为本文件(规范变通记录于
文件头,sr-od-test/README.md「测试文件组织」的镜像规则以 src 文件为基准)。

被测行为锁 = 渲染器自身设计约定(以 tools/cw/replay_to_md.py 实现为准):
- 渲染管线:行加载 / 节点分组 / 无 node 行归属链 / 画面章切分 /
  动作节切分与状态差分 / CLI
- 显示规范:骨架 / 局头 / 画面注册表 / 动作节显示 / 特殊情况
- 策略遥测装配:发现加载 / 章级挂载表 / 两级 join 与报告块 / 局头
  (动作级回执 dtag 语义与回执覆盖面)

fixture journal 全部自造、只写 pytest tmp_path,零真实副作用(不连真游戏、
不读本机易失产物;真实 journal 只用于人工验收,不进测试断言)。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_TOOL_PATH = (Path(__file__).resolve().parents[3] / 'tools' / 'cw'
              / 'replay_to_md.py')
_spec = importlib.util.spec_from_file_location('cw_replay_to_md', _TOOL_PATH)
assert _spec is not None and _spec.loader is not None  # 模块加载失败即收集错
mod = importlib.util.module_from_spec(_spec)
# dataclass 处理器按 cls.__module__ 回查 sys.modules,必须先注册再执行
sys.modules['cw_replay_to_md'] = mod
_spec.loader.exec_module(mod)  # 贵加载(含 src import 链)全会话只执行一次


# ---------------------------------------------------------------------------
# fixture 行构造器(journal 行模型最小面:渲染依赖的核心字段)
# ---------------------------------------------------------------------------


def mkrow(ts: str, field: str, after: Any, *, run: str = 'run_t',
          row: str = 'write', node: tuple[int, int, str] | None = (1, 1, 'reward'),
          screen: str | None = None, actor: str = 'cw_observation',
          family: str = 'obs', same_value: bool = False,
          values_extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造一行 journal(渲染依赖面:v/ts/run_id/row/field/after/same_value/
    state.values(node/current_screen/extra)/sig.family/sig.actor)。"""
    values: dict[str, Any] = {}
    if node is not None:
        values['node'] = {'plane': node[0], 'round_num': node[1],
                          'kind': node[2]}
    if screen is not None:
        values['current_screen'] = screen
    if values_extra:
        values.update(values_extra)
    return {
        'v': 1, 'ts': ts, 'run_id': run, 'row': row,
        'field': field, 'after': after, 'same_value': same_value,
        'state': {'values': values},
        'sig': {'family': family, 'actor': actor, 'mode': 'compute'},
    }


def receipt(op: str, reason: str = '', detail: str = '',
            screen: str = '', **extra: Any) -> dict[str, Any]:
    """一条动作回执(载荷结构 = note_action_receipt 写端形态,纯动作
    事实:op + reason 受阻码,无成败布尔)。"""
    r: dict[str, Any] = {'op': op, 'reason': reason}
    if detail:
        r['detail'] = detail
    if screen:
        r['screen'] = screen
    r.update(extra)
    return r


def receipts_row(ts: str, *recs: dict[str, Any], **kw: Any) -> dict[str, Any]:
    """receipts 基准行(after = 回执滚动窗整窗)。"""
    kw.setdefault('family', 'logic_action')
    kw.setdefault('actor', 'CwScreenPrep')
    return mkrow(ts, 'receipts', list(recs), **kw)


def build(rows: list[dict[str, Any]]):
    """行列表 → (Report, markdown 全文)。"""
    report = mod.build_report(rows, mod.JournalReadStats(), game_id='fixture')
    return report, mod.render_markdown(report)


def section_of_kind(report: Any, kind: str) -> Any:
    """取第一个指定 kind 的章组(无则断言失败)。"""
    hits = [s for s in report.sections if s.kind == kind]
    assert hits, f'无 kind={kind} 章组: {[s.kind for s in report.sections]}'
    return hits[0]


# ---------------------------------------------------------------------------
# 节点分组(pipeline §2)
# ---------------------------------------------------------------------------


def test_node_grouping_and_kind_first_row_wins():
    """节点按 (plane, round) 分组;类型取组内首行 node.kind——组内 kind
    翻转(备战→战斗窗过渡处 reward→battle 实测形态)不改变章标题。"""
    rows = [
        mkrow('t1', 'hp', 80, node=(1, 1, 'reward'), screen='货币战争-备战'),
        mkrow('t2', 'hp', 79, node=(1, 1, 'battle'), screen='货币战争-战斗等待'),
        mkrow('t3', 'hp', 78, node=(1, 2, 'supply'), screen='货币战争-备战'),
    ]
    report, md = build(rows)
    node_secs = [s for s in report.sections if s.kind == 'node']
    assert [s.node.kind_cn for s in node_secs] == ['奖励', '补给']
    assert [s.node.round for s in node_secs] == [1, 2]
    assert '## 节点 1-1 奖励' in md
    assert '## 节点 1-1 战斗' not in md  # 翻转值(次行)不选
    assert '## 节点 1-2 补给' in md


# ---------------------------------------------------------------------------
# 无 node 行三类归属(pipeline §3)
# ---------------------------------------------------------------------------


def test_no_node_rows_three_way_attachment():
    """无 node 行归属链(优先级从上到下,pipeline §3):首节点行之前 →
    开局段(含无证据行,开局段内开占位章);其后带画面证据 → 未归节
    虚拟组;其后无 node 且无画面证据 → 文末未归行清单(防静默丢行)。"""
    rows = [
        # 开局段:首节点行之前(归属链规则 1 优先,无证据行也在开局段)
        mkrow('t1', 'plane_bosses', ['bossA'], node=None,
              screen='货币战争-BOSS简报', actor='CwScreenBriefing'),
        mkrow('t2', 'gold', 5, node=None, actor='SimEngineV2'),
        mkrow('t3', 'hp', 80, node=(1, 1, 'reward'), screen='货币战争-备战'),
        # 未归节:首节点行之后、带画面证据(规则 2)
        mkrow('t4', 'invest_env_opts', ['a'], node=None, actor='CwScreenInvestEnv'),
        # 未归行:首节点行之后、无任何画面证据(规则 3)
        mkrow('t5', 'gold', 6, node=None, actor='SimEngineV2'),
    ]
    report, md = build(rows)
    assert [s.kind for s in report.sections] == ['open', 'node', 'unattached']
    assert len(report.annex_unattached) == 1
    assert 'SimEngineV2' in report.annex_unattached[0]
    assert '## 未归行' in md
    unattached = section_of_kind(report, 'unattached')
    assert unattached.screens[0].title == '画面-投资环境'


# ---------------------------------------------------------------------------
# 画面章切分(pipeline §4)
# ---------------------------------------------------------------------------


def test_screen_split_group_base_popup_and_unregistered():
    """画面章切分四形态:组首行恒开章(基线=组边界);current_screen 广播
    行同值不开新章;弹层 actor 在该行处开章且后续无证据行挂弹层章;回到底层
    (广播值==快照章 id)续开该快照章;未注册 screen id 按原样 id 开章 + 缺口
    注记(缺口可见性 = 设计目标)。开章行 = current_screen 广播行本体
    (切章证据收窄:快照携带 cs 不再开章,渲染器 _locate_screen 注)。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),                        # 广播行开备战章
        mkrow('t2', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),                        # 同值续章
        mkrow('t3', 'invest_env_opts', ['a'],
              actor='CwScreenInvestEnv'),                        # 弹层章
        mkrow('t4', 'hp', 78),                                   # 挂弹层章
        mkrow('t5', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),                        # 回底层续章
        mkrow('t6', 'current_screen', '货币战争-大厅',
              screen='货币战争-大厅'),                        # 未注册 id
    ]
    report, md = build(rows)
    sec = section_of_kind(report, 'node')
    titles = [s.title for s in sec.screens]
    assert titles == ['画面-备战', '画面-投资环境', '货币战争-大厅']
    assert len(sec.screens[0].entry) >= 0
    assert '缺口: 画面「货币战争-大厅」未注册' in md


def test_placeholder_screen_when_no_evidence_at_group_head():
    """组首行无任何画面证据 → 占位章 + 缺口注记(sim 形态兜底),
    不静默丢章;后续广播行照常开快照章。"""
    rows = [
        mkrow('t1', 'hp', 80, actor='SimEngineV2'),              # 占位章
        mkrow('t2', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),                        # 广播行开快照章
    ]
    report, md = build(rows)
    sec = section_of_kind(report, 'node')
    assert [s.title for s in sec.screens] == ['(未观察)', '画面-备战']
    assert '缺口: 画面证据缺失' in md


def test_unregistered_screen_actor_gap_annotated_mid_chapter():
    """未注册画面 op 行(pipeline §4「未注册 actor」+「缺口可见性为设计
    目标」):不切分,挂当前画面章尾注 + 记缺口;obs 与非 obs 两 family 都
    显示 actor 名(同章同 actor 聚合一条带计数);非 obs 行禁止静默混入动作
    状态变化表(一律走尾注);receipts 动作节机制与快照章形态 op
    (CwScreenPrep 等)/非画面 actor(cw_observation)不受判定影响。"""
    rows = [
        mkrow('t1', 'hp', 80, screen='货币战争-备战'),            # 开备战章
        receipts_row('t2', receipt('BuyCard')),                   # 动作节 1
        # obs 未注册画面 op:值显示(观察尾注)+ actor 显示(缺口)
        mkrow('t3', 'new_screen_payload', {'opts': ['x']},
              screen='货币战争-备战', actor='CwScreenBrandNewPayload'),
        # 非 obs 未注册画面 op ×2:聚合一条尾注,不入变化表
        mkrow('t4', 'brand_new_choice', 'opt2', screen='货币战争-备战',
              family='logic_action', actor='CwScreenBrandNewPayload'),
        mkrow('t5', 'brand_new_pick', 'opt3', screen='货币战争-备战',
              family='logic_action', actor='CwScreenBrandNewPayload'),
        # 未注册画面 op 的 receipts 行仍走动作节机制(不静音)
        receipts_row('t6', receipt('BrandNewOp'),
                     actor='CwScreenBrandNewPayload'),
        mkrow('t7', 'hp', 79, screen='货币战争-备战'),            # 普通 obs 不受影响
    ]
    report, md = build(rows)
    scr = section_of_kind(report, 'node').screens[0]
    joined = '\n'.join(scr.annots)
    # actor 名显示:obs ×1 + 非 obs ×2 聚合一条带计数
    assert '缺口: 未注册写入者 CwScreenBrandNewPayload ×3' in joined
    assert '- 缺口: 未注册写入者 CwScreenBrandNewPayload ×3' in md
    # obs family:值显示进 0 观察动态段(非注册键观察写入);非 obs family:不走观察尾注
    assert '- new_screen_payload {"opts":["x"]}' in md
    assert not any(a.startswith('观察: new_screen_payload=')
                   for a in scr.annots)
    assert not any(a.startswith('观察: brand_new_choice') for a in scr.annots)
    assert not any(a.startswith('观察: brand_new_pick') for a in scr.annots)
    # 非 obs 未注册行禁入动作节 deltas 与章内变化块
    assert all(d.field not in ('brand_new_choice', 'brand_new_pick')
               for a in scr.actions for d in a.deltas)
    assert all(d.field not in ('brand_new_choice', 'brand_new_pick')
               for d in scr.trailing_changes)
    # 未注册 actor 的 receipts 行仍产动作节;快照形态 op / 非画面 actor 不判
    assert [a.op for a in scr.actions] == ['BuyCard', 'BrandNewOp']
    assert '未注册写入者 CwScreenPrep' not in joined
    assert '未注册写入者 cw_observation' not in joined


# ---------------------------------------------------------------------------
# 切章证据收窄与广播形态(渲染器 _locate_screen/SCREEN_REGISTRY 注:
# 切章基准 = field='current_screen' 写入行本体;相邻合并键 = title)
# ---------------------------------------------------------------------------


def test_stale_snapshot_cs_never_switches_chapter():
    """切章证据收窄:非广播行携带的快照 cs 只作归属,永不作为切章基准——
    结算段陈值 cs=备战(sim 广播节拍下两次广播之间的行全带陈值)不重开
    备战章,挂当前战斗章(幽灵章回归:只看键在场时章数近倍膨胀)。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        # 战斗章由 settlement 开章证据规则承载(pipeline §4 保留)
        mkrow('t2', 'settlement', {'hp_after': 84, 'killed': True},
              node=(1, 1, 'battle'), screen='货币战争-战斗等待',
              actor='CwScreenBattleWait'),
        # 结算段陈值 cs 行:挂战斗章,不重开备战章
        mkrow('t3', 'streak', 1, node=(1, 1, 'battle'),
              screen='货币战争-备战'),
        mkrow('t4', 'gold', 31, node=(1, 1, 'battle'),
              screen='货币战争-备战', family='logic_action',
              actor='SimEngineV2'),
    ]
    report, md = build(rows)
    titles = [s.title for s in section_of_kind(report, 'node').screens]
    assert titles == ['画面-备战', '画面-战斗']
    assert md.count('### 节点 1-1 奖励 画面-备战') == 1


def test_overlay_broadcast_and_actor_rows_merge_single_chapter():
    """overlay 相相邻合并键 = title:cs 广播行先、actor 行后,两者
    screen_id 异源(画面值 vs actor 名)而 title 相同 → 归一单章;
    合并沿用先开章规格。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        mkrow('t2', 'current_screen', '货币战争-备战-武装箱选择',
              screen='货币战争-备战-武装箱选择'),
        mkrow('t3', 'box_card_names', ['以太钻头'],
              screen='货币战争-备战-武装箱选择', actor='CwScreenBoxPick'),
        mkrow('t4', 'gold', 20, screen='货币战争-备战-武装箱选择'),
    ]
    report, _ = build(rows)
    sec = section_of_kind(report, 'node')
    assert [s.title for s in sec.screens] == ['画面-备战', '画面-箱子']
    box = sec.screens[1]
    assert box.screen_id == '货币战争-备战-武装箱选择'  # 合并沿用先开章
    assert not any('缺口' in a for a in box.annots)


def test_same_value_broadcast_does_not_reopen_chapter():
    """同值广播不重开章(kernel 写端落 same_value=true 行,渲染路由
    值==base 续开 base,零副作用)。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        mkrow('t2', 'current_screen', '货币战争-备战',
              screen='货币战争-备战', same_value=True),
        mkrow('t3', 'current_screen', '货币战争-备战',
              screen='货币战争-备战', same_value=True),
    ]
    report, _ = build(rows)
    assert [s.title for s in section_of_kind(report, 'node').screens] \
        == ['画面-备战']


def test_opening_note_skips_empty_value_rows():
    """开局注记空值跳过:prev_screen 首行空串(sim 广播首对的实测采集
    时序形态)不出「字段=—」噪声行;唯一注记被跳过后开局桶整节不渲染。"""
    rows = [
        mkrow('t1', 'prev_screen', '', node=None, actor='SimEngineV2'),
        mkrow('t2', 'current_screen', '货币战争-简报', node=None,
              screen='货币战争-简报', actor='SimEngineV2'),
        mkrow('t3', 'gold', 3, node=(1, 1, 'reward'), screen='货币战争-备战'),
    ]
    report, md = build(rows)
    open_sec = section_of_kind(report, 'open')
    assert open_sec.opening_notes == []
    assert '开局初始化与基线观察' not in md
    assert 'prev_screen=—' not in md


# ---------------------------------------------------------------------------
# 动作节(pipeline §5)
# ---------------------------------------------------------------------------


def test_receipt_same_value_noop_not_an_action():
    """动作基准 = receipts 且 same_value≠true;no-op 整窗重写(same_value=
    true,实测 524 条中 183 条)不产动作节。"""
    win = [receipt('BuyCard', screen='货币战争-备战-开商店')]
    rows = [
        receipts_row('t1', *win),
        receipts_row('t2', *win, same_value=True),  # no-op 重写
        receipts_row('t3', receipt('SellBench', detail='卖备战槽1 ✓')),
    ]
    report, _ = build(rows)
    actions = section_of_kind(report, 'node').screens[0].actions
    assert [a.op for a in actions] == ['BuyCard', 'SellBench']
    assert [a.no for a in actions] == [1, 2]


def test_retry_chain_merged_into_one_action():
    """重试链合并:连续回执同 op 且前条 reason 非空 → 合并一节,节内
    逐条列出(实测样例 StartBattle 重发链);异 op 基准仍开新节。"""
    rows = [
        receipts_row('t1', receipt('StartBattle', reason='弹窗未关')),
        receipts_row('t2', receipt('StartBattle', detail='出战已点击')),
        receipts_row('t3', receipt('BuyCard')),
    ]
    report, md = build(rows)
    actions = section_of_kind(report, 'node').screens[0].actions
    assert [a.op for a in actions] == ['StartBattle', 'BuyCard']
    assert len(actions[0].chain) == 2  # 链内逐条
    assert actions[0].chain[0]['reason'] == '弹窗未关'  # 合并判据基准 = reason 非空
    assert '#### 1 出战' in md
    assert '⚠ ' in md and 'applied' not in md  # 受阻样式挂 reason,布尔零显示


def test_transition_action_attributed_to_issuing_screen():
    """动作节章归属基准 = 回执 screen(动作发出画面;出处 =
    tools/cw/replay_to_md.py 模块头「渲染结构」):开商店回执在切屏写入行
    之后落窗(sim 实测形态:cs 先翻、回执后落),按发出画面回搜归备战章,
    不按位置落到变更后画面;后续动作(买牌)照常归商店章;开店自身零
    效果写入,买牌的效果写入因果归买牌节。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        # 切屏先落盘(开商店的状态副本推进)
        mkrow('t2', 'current_screen', '货币战争-备战-开商店',
              screen='货币战争-备战-开商店'),
        # 开店回执后落窗,screen = 发出画面(备战)
        receipts_row('t3', receipt('CwOpOpenShop',
                                   screen='货币战争-备战')),
        # 买牌效果写入(切屏后落盘)→ 待认领缓冲
        mkrow('t4', 'gold', 16, screen='货币战争-备战-开商店',
              family='logic_action', actor='CwActionBuyCardOp'),
        receipts_row('t5', receipt('CwActionBuyCardParam',
                                   screen='货币战争-备战-开商店')),
    ]
    report, md = build(rows)
    screens = section_of_kind(report, 'node').screens
    assert [s.title for s in screens] == ['画面-备战', '画面-商店']
    prep, shop = screens[0], screens[1]
    assert [a.op for a in prep.actions] == ['CwOpOpenShop']
    assert [a.op for a in shop.actions] == ['CwActionBuyCardParam']
    assert not prep.actions[0].deltas
    assert [(d.field, d.before, d.after)
            for d in shop.actions[0].deltas] == [('gold', None, 16)]
    assert '#### 1 开店' in md
    assert md.index('#### 1 开店') < md.index('### 节点 1-1 奖励 画面-商店')


def test_legacy_target_screen_receipt_stays_positional():
    """旧数据回退:历史 journal 的开商店回执 screen=目标画面语义
    (货币战争-备战-开商店,与回执落窗时的当前章一致)→ 位置归属照旧
    落商店章,旧局重渲染零回归。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        mkrow('t2', 'current_screen', '货币战争-备战-开商店',
              screen='货币战争-备战-开商店'),
        receipts_row('t3', receipt('CwOpOpenShop',
                                   screen='货币战争-备战-开商店')),
    ]
    report, _ = build(rows)
    screens = section_of_kind(report, 'node').screens
    assert [s.title for s in screens] == ['画面-备战', '画面-商店']
    assert [a.op for a in screens[1].actions] == ['CwOpOpenShop']
    assert not screens[0].actions


def test_retry_chain_across_screen_switch_stays_on_issuing_chapter():
    """重试链跨切屏:受阻开店回执(备战)→ 切屏 → 重试开店回执(备战,
    位置落商店章)→ 合并进备战章的单节——链判据 = 组内最近动作(跨章),
    不再按当前章找链。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        receipts_row('t2', receipt('CwOpOpenShop',
                                   reason='定位缺失(按钮-商店)',
                                   screen='货币战争-备战')),
        mkrow('t3', 'current_screen', '货币战争-备战-开商店',
              screen='货币战争-备战-开商店'),
        receipts_row('t4', receipt('CwOpOpenShop',
                                   screen='货币战争-备战')),
    ]
    report, md = build(rows)
    screens = section_of_kind(report, 'node').screens
    assert [s.title for s in screens] == ['画面-备战', '画面-商店']
    assert [a.op for a in screens[0].actions] == ['CwOpOpenShop']
    assert len(screens[0].actions[0].chain) == 2
    assert not screens[1].actions
    assert '⚠ ' in md  # 受阻样式挂 reason


def test_legacy_applied_key_receipts_render_clean():
    """旧 journal 兼容(历史批回执含 applied/gold_delta 双键):两键不读
    不显(extra 排除表承接,两处排除字面量保留判据),布尔与金差字样
    零显示;合并判据只看 reason(旧受阻条 reason 非空照常并链),重渲染
    零异常。"""
    legacy_blocked = {'op': 'StartBattle', 'applied': False,
                      'reason': '弹窗未关', 'detail': '旧数据'}
    legacy_ok = {'op': 'BuyCard', 'applied': True, 'reason': '',
                 'gold_delta': -3}
    rows = [
        receipts_row('t1', legacy_blocked),
        receipts_row('t2', {'op': 'StartBattle', 'applied': True,
                            'reason': '', 'detail': '出战已点击'}),
        receipts_row('t3', legacy_ok),
    ]
    report, md = build(rows)
    actions = section_of_kind(report, 'node').screens[0].actions
    assert [a.op for a in actions] == ['StartBattle', 'BuyCard']
    assert len(actions[0].chain) == 2  # 旧受阻条 reason 非空 → 照常并链
    assert 'applied' not in md  # 布尔字样零显示
    assert 'gold_delta' not in md  # 退役金差键零显示(extra 排除表承接)


def test_delta_causal_flush_and_cross_node_chain():
    """状态差分因果归属(出处 = tools/cw/replay_to_md.py 模块头「渲染结构」
    章内差分规则):logic_action 写入行挂其后最近回执的动作节——动作的
    效果写入先于其回执落盘(journal 实测形态:写 v=N,回执窗更新 v=N+k),
    修「效果显影滞后一节」;前值 = 之前最近同 field 写入行 after(链跨行);
    组尾无回执认领的挂起写入 → 组尾扫入章内变化块(防静默丢行)。"""
    rows = [
        # 节点 1-1:gold 首写(无前值)在回执前 → 因果归 BuyCard 节
        mkrow('t1', 'gold', 30, screen='货币战争-备战',
              family='logic_action', actor='PrepActionExecutor'),
        receipts_row('t2', receipt('BuyCard')),
        mkrow('t3', 'gold', 29, screen='货币战争-备战',
              family='logic_action', actor='PrepActionExecutor'),
        # 节点 1-2:1-1 组尾的 gold29 无回执认领 → 尾扫 1-1 章内变化块;
        # 1-2 基准节吸收组内待认领写入,前值跨组接链(29)
        mkrow('t4', 'hp', 78, node=(1, 2, 'reward'), screen='货币战争-备战'),
        receipts_row('t5', receipt('BuyCard'), node=(1, 2, 'reward')),
        mkrow('t6', 'gold', 27, node=(1, 2, 'reward'),
              screen='货币战争-备战', family='logic_action',
              actor='PrepActionExecutor'),
    ]
    report, md = build(rows)
    secs = [s for s in report.sections if s.kind == 'node']
    s11 = secs[0].screens[0]
    assert len(s11.actions) == 1
    # t1 的写入因果归 t2 的 BuyCard 节(不再显示滞后为下一动作的效果)
    assert [(d.field, d.before, d.after) for d in s11.actions[0].deltas] \
        == [('gold', None, 30)]
    # t3 组尾无回执认领 → 章内变化块
    assert [(d.field, d.before, d.after) for d in s11.trailing_changes] \
        == [('gold', 30, 29)]
    s12 = secs[1].screens[0]
    # t6 在 1-2 组内位于回执之后、组尾无回执认领 → 章内变化块;
    # 前值跨组接链(t3 的 29)仍成立,显示随动作节所在章解耦
    assert s12.actions[0].deltas == []
    assert [(d.field, d.before, d.after) for d in s12.trailing_changes] \
        == [('gold', 29, 27)]
    assert '| 金(gold) | (起点) → 30 |' in md
    assert '| 金(gold) | 30 → 29 |' in md


def test_obs_rows_not_in_delta_settlement_to_trailing():
    """obs 道不入状态变化表(观察是读数不是动作效果):非章首 obs 行进
    章尾注;logic_hook 行入变化表且说明列标(效果钩子);settlement 写入行
    例外走章内变化块(render-spec §3 战斗章注册行)。"""
    rows = [
        mkrow('t1', 'hp', 80, screen='货币战争-备战'),
        receipts_row('t2', receipt('BuyCard')),
        # obs → 尾注(独有字段;entry 键如 hp 的回读已被跳过规则吞掉)
        mkrow('t3', 'round_fresh_buys', {'phase': [1, 1], 'names': ['翡翠']},
              screen='货币战争-备战'),
        mkrow('t4', 'node', {'plane': 1, 'round_num': 1, 'kind': 'battle'},
              screen='货币战争-备战', family='logic_hook',
              actor='derive_node_observed'),                     # hook → 变化表
        mkrow('t5', 'settlement', {'hp_after': 84, 'killed': True,
                                   'progress_delta': 2, 'gold': None,
                                   'level': 4, 'xp': [0, 6],
                                   'streak_after': 0},
              screen='货币战争-战斗等待', actor='CwScreenBattleWait'),
    ]
    report, md = build(rows)
    screens = section_of_kind(report, 'node').screens
    prep = screens[0]
    assert [(d.field, d.is_hook) for d in prep.actions[0].deltas] \
        == [('node', True)]
    assert all(d.field != 'round_fresh_buys' for d in prep.actions[0].deltas)
    # obs 回读显示进 0 观察动态段(非注册键观察写入)
    assert '- 本轮新买(round_fresh_buys) phase[1, 1]: 翡翠' in md
    assert not any(a.startswith('观察: round_fresh_buys=')
                   for a in prep.annots)
    # settlement 行(cs=战斗等待)归「画面-战斗」章的章内变化块,不入
    # 动作节 deltas、不入备战章(render-spec §3 战斗章注册行)
    battle = [s for s in screens if s.title == '画面-战斗']
    assert battle and [d.field for d in battle[0].trailing_changes] \
        == ['settlement']
    assert '| 结算(settlement) | (起点) → 胜 血 84 进度 +2 等级 4 经验 0/6 连胜 0 |' in md


# ---------------------------------------------------------------------------
# 显示规范(render-spec)
# ---------------------------------------------------------------------------


def test_action_word_param_alias_normalized():
    """动作词参数型别名归一(sim 实测形态):CwActionBuyCardParam→买牌 /
    CwActionCollectOreParam→采晶矿;开放词表未命中原样显示(禁猜)。"""
    rows = [
        receipts_row('t1', receipt('CwActionBuyCardParam')),
        receipts_row('t2', receipt('CwActionCollectOreParam')),
        receipts_row('t3', receipt('WeirdFutureOp')),
    ]
    _, md = build(rows)
    assert '#### 1 买牌' in md
    assert '#### 2 采晶矿' in md
    assert '#### 3 WeirdFutureOp' in md  # 未命中原样显示


def test_empty_action_screen_keeps_obs_and_eval_only():
    """空动作画面章:只渲染 0 观察 + 章内变化块(若有)+ 策略评价(若决策面);
    非决策面章(战斗)不渲染策略评价节;「复盘者附加」固定空节恒在。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        mkrow('t2', 'current_screen', '货币战争-战斗等待',
              node=(1, 1, 'battle'), screen='货币战争-战斗等待'),
    ]
    _, md = build(rows)
    assert '#### 0 观察' in md
    assert '#### 1 ' not in md  # 无动作节
    assert md.count('#### 策略评价') == 1  # 仅备战章(决策面)
    battle_pos = md.index('画面-战斗')
    eval_pos = md.index('#### 策略评价')
    assert eval_pos < battle_pos  # 策略评价节在备战章内,战斗章无
    assert md.rstrip().endswith('## 复盘者附加')


def test_shop_entry_table_and_probs():
    """商店快照章 0 观察:牌面表(槽/牌名/阵营/费用/星级,槽三态)+ 概率
    档→概率串(render-spec §3 商店行)。开章行 = 广播行形态。"""
    shop = {'cards': [
        {'kind': 'content', 'card': {'name': '爻光', 'faction': '仙舟',
                                     'cost': 1, 'star': 1}},
        {'kind': 'empty', 'card': None},
        {'kind': 'unknown', 'card': None},
    ], 'refresh_probs': {'1': 1.0, '2': 0.0}}
    rows = [mkrow('t1', 'current_screen', '货币战争-备战-开商店',
                  node=None, screen='货币战争-备战-开商店',
                  actor='CwScreenShop',
                  values_extra={'shop': shop, 'gold': 19})]
    report, md = build(rows)
    scr = section_of_kind(report, 'open').screens[0]
    assert scr.title == '画面-商店'
    assert '| 1 | 爻光 | 仙舟 | 1 | 1★ |' in md
    assert '| 2 | 空 |  |  |  |' in md
    assert '| 3 | 识别失败 |  |  |  |' in md
    assert '- 概率(refresh_probs) 1→100%、2→0%' in md


def test_prep_deployed_entry_table_before_bench():
    """备战章 0 观察:deployed 表格化(上阵表:行标签 前排/后排,null → 空,
    列数 = max(前后排槽数),前排不足列补 —),位置紧贴备战席表前,散列
    前排/后排两行不再出现(上阵跟备战席同款表格化)。"""
    deployed = {'front_slots': [{'char_id': '绯英', 'star': 1},
                                None, None, None],
                'back_slots': [{'char_id': '爻光', 'star': 1},
                               None, None, None, None, None]}
    bench = {'slots': [{'kind': 'unit', 'unit': {'char_id': '桑博', 'star': 1}},
                       {'kind': 'empty', 'unit': None}]}
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战', node=(1, 2, 'reward'),
              screen='货币战争-备战',
              values_extra={'deployed': deployed, 'bench': bench}),
    ]
    _, md = build(rows)
    assert '**上阵(deployed)**' in md
    assert '| 排 | 1 | 2 | 3 | 4 | 5 | 6 |' in md
    assert '| 前排 | 绯英1★ | 空 | 空 | 空 | — | — |' in md
    assert '| 后排 | 爻光1★ | 空 | 空 | 空 | 空 | 空 |' in md
    assert '- 前排(front_slots)' not in md
    assert '- 后排(back_slots)' not in md
    assert md.index('**上阵(deployed)**') < md.index('**备战席(bench)**')


def test_prep_deployed_table_all_empty_opening_frame():
    """开局帧前后排全 null 也照常出全「空」上阵表(结构稳定),不回落散列行。"""
    deployed = {'front_slots': [None] * 4, 'back_slots': [None] * 6}
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战', values_extra={'deployed': deployed}),
    ]
    _, md = build(rows)
    assert '| 前排 | 空 | 空 | 空 | 空 | — | — |' in md
    assert '| 后排 | 空 | 空 | 空 | 空 | 空 | 空 |' in md
    assert '- 前排(front_slots)' not in md


def test_battle_chapter_deployed_keeps_bullets():
    """战斗章快照虽含 deployed(其注册键集含此键),上阵不表格化——
    非备战章维持散列行现状,上阵表只在与备战席表同章的画面生效。"""
    deployed = {'front_slots': [{'char_id': '绯英', 'star': 1},
                                None, None, None],
                'back_slots': [None] * 6}
    rows = [
        mkrow('t1', 'current_screen', '货币战争-战斗等待',
              node=(1, 1, 'battle'), screen='货币战争-战斗等待',
              values_extra={'deployed': deployed}),
    ]
    _, md = build(rows)
    assert '**上阵(deployed)**' not in md
    assert '- 前排(front_slots) 绯英1★' in md
    assert '- 后排(back_slots) (空)' in md


# ---------------------------------------------------------------------------
# 行加载与 CLI(pipeline §1/§7)
# ---------------------------------------------------------------------------


def _write_journal(tmp_path: Path, lines: list[str]) -> Path:
    d = tmp_path / 'state'
    d.mkdir()
    f = d / 'journal.jsonl'
    f.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return f


def test_tolerant_read_counts_bad_lines(tmp_path: Path, capsys: Any):
    """宽容读取:坏行/非对象行逐行跳过 + 计数留痕(禁炸),计数进局头
    「数据完整性」行(render-spec §2:坏行 N/非对象 N/字节修复 N)。"""
    good = json.dumps(mkrow('t1', 'hp', 80), ensure_ascii=False)
    f = _write_journal(tmp_path, [good, '{"v": 1, 截断半行', '[1, 2]', good])
    out = tmp_path / 'out.md'
    code = mod.main(['--journal', str(f), '--game-id', 'badtest',
                     '--out', str(out)])
    assert code == 0
    md = out.read_text(encoding='utf-8')
    assert '- 数据完整性: 坏行 1/非对象 1/字节修复 0' in md
    assert '# 货币战争复盘 badtest' in md


def test_cli_usage_errors_exit_2(tmp_path: Path):
    """CLI 用法错误一律退出码 2(pipeline §7):--run 未知值(语义变更:
    旧渲染器「未知 run 全渲染+警告」已废);--match 档案缺失;--match 与
    --journal 互斥;二者均缺。"""
    f = _write_journal(tmp_path, [json.dumps(mkrow('t1', 'hp', 80))])
    assert mod.main(['--journal', str(f), '--game-id', 'x',
                     '--run', 'run_unknown']) == 2
    assert mod.main(['--match', 'g_not_exist_9999']) == 2
    assert mod.main(['--match', 'a', '--journal', str(f)]) == 2
    assert mod.main([]) == 2


def test_cli_stdout_renders_header(tmp_path: Path, capsys: Any):
    """--stdout 打印不落盘;局头 meta 逐行(render-spec §2)。"""
    rows = [
        mkrow('t1', 'hp', 80, run='run_a'),
        mkrow('t2', 'match_final', {'final_type': 'stopped', 'plane': 1,
                                    'round_num': 3, 'hp': 84, 'gold': 31,
                                    'duration_s': 206.3,
                                    'code_commit': 'c0ffee1',
                                    'registry_fingerprint': 'fp1'},
              run='run_a', family='logic_hook', actor='MatchClose'),
    ]
    f = _write_journal(tmp_path, [json.dumps(r, ensure_ascii=False)
                                  for r in rows])
    code = mod.main(['--journal', str(f), '--game-id', 'cli_smoke',
                     '--stdout'])
    assert code == 0
    md = capsys.readouterr().out
    assert '# 货币战争复盘 cli_smoke' in md
    assert '- 运行段: run_a' in md
    assert '- 策略版本 commit: c0ffee1' in md
    assert '- 终局: stopped 位面 P1-R3 hp 84 金 31 时长 206s' in md
    assert '- 数据完整性: 无' in md

# ---------------------------------------------------------------------------
# 显示抛光(T-5:渲染同值过滤 / 开局段归属桶 / 观察行规则 / 人读格式)
# ---------------------------------------------------------------------------


def test_same_value_delta_filtered_with_counter_note():
    """渲染同值行(same_value=False 但格式化后前=后)= 零信息 → 不进变化表,
    章尾计数注记(§5 修订);真变化照常渲染。"""
    rows = [
        mkrow('t1', 'hp', 80, node=(1, 1, 'reward'), screen='货币战争-备战'),
        mkrow('t2', 'gold', 15, node=(1, 1, 'reward'), screen='货币战争-备战',
              family='logic_action', actor='SimEngineV2'),
        mkrow('t3', 'gold', 15, node=(1, 1, 'reward'), screen='货币战争-备战',
              family='logic_action', actor='SimEngineV2'),
    ]
    report, md = build(rows)
    scr = section_of_kind(report, 'node').screens[0]
    assert scr._same_skipped == 1
    assert '| 金(gold) | (起点) → 15 |' in md
    assert '| 金(gold) | 15 → 15 |' not in md
    assert '- 同值写入 ×1 略(前=后,零信息)' in md


def test_opening_unattributed_rows_bucketed():
    """开局段无画面归属行(写入者非注册画面 actor 且无 current_screen)→
    组级注记桶(开局初始化/开局基线观察),不粘进当前画面章的章内变化
    (§3 修订);注册 actor 行照常开章。"""
    rows = [
        mkrow('t1', 'node_path',
              {'plane': 1, 'seq': [{'token': 'reward'}]},
              node=None, actor='GsOpeningSeed', family='logic_action'),
        mkrow('t2', 'board', {'仙舟': 1}, node=None, actor='cw_observation'),
        mkrow('t3', 'plane_bosses', ['bossA'], node=None,
              screen='货币战争-BOSS简报', actor='CwScreenBriefing'),
        mkrow('t4', 'hp', 80, node=(1, 1, 'reward'), screen='货币战争-备战'),
    ]
    report, md = build(rows)
    open_sec = section_of_kind(report, 'open')
    assert len(open_sec.opening_notes) == 2
    assert '开局初始化' in open_sec.opening_notes[0]
    assert 'GsOpeningSeed' in open_sec.opening_notes[0]
    assert '开局基线观察' in open_sec.opening_notes[1]
    assert '### 开局初始化与基线观察' in md
    briefing = open_sec.screens[0]
    assert briefing.title == '画面-BOSS简报'
    assert not briefing.trailing_changes  # 种子行不再粘进简报章
    assert not open_sec.screens[0]._same_skipped


def test_obs_note_rules_skip_dedup_and_route_keys():
    """观察显示规则:空值不渲染;prev_screen/current_screen 路由键跳过;
    非注册键观察写入进 0 观察动态段(首写定帧值),同值回读不重复显示。"""
    rows = [
        mkrow('t1', 'hp', 80, node=(1, 1, 'reward'), screen='货币战争-备战'),
        mkrow('t2', 'prev_screen', '货币战争-战斗等待', node=(1, 1, 'reward'),
              screen='货币战争-备战'),
        mkrow('t3', 'overflow_card', '', node=(1, 1, 'reward'),
              screen='货币战争-备战'),
        # 动态段样本用非 entry 键字段(entry 键整条跳过,见 entry 键跳过测试)
        mkrow('t4', 'node_pos', [1, 1], node=(1, 1, 'reward'),
              screen='货币战争-备战'),
        mkrow('t5', 'node_pos', [1, 1], node=(1, 1, 'reward'),
              screen='货币战争-备战'),
    ]
    _, md = build(rows)
    assert 'prev_screen' not in md
    assert '溢出卡' not in md
    assert md.count('- 节点序位(node_pos) [1,1]') == 1  # 首写进 0 观察,同值回读不重复
    assert '观察: node_pos' not in md


def test_delta_cells_human_formats():
    """差分单元格人读格式(§4.3):bench=名★+空×N、spheres=N 座(色×n)、
    node_path=token 中文链——禁截断 raw JSON。"""
    bench_before = {'slots': [{'kind': 'unit',
                               'unit': {'char_id': '爻光', 'star': 1}}]}
    bench_after = {'slots': [{'kind': 'unit',
                              'unit': {'char_id': '爻光', 'star': 1}},
                             {'kind': 'empty', 'unit': None}]}
    rows = [
        mkrow('t1', 'bench', bench_before, node=(1, 1, 'reward'),
              screen='货币战争-备战'),
        mkrow('t2', 'bench', bench_after, node=(1, 1, 'reward'),
              screen='货币战争-备战', family='logic_action', actor='SimEngineV2'),
        mkrow('t3', 'spheres', {'count': 2, 'colors': ['灰', '灰']},
              node=(1, 1, 'reward'), screen='货币战争-备战'),
        mkrow('t4', 'spheres', {'count': 1, 'colors': ['灰']},
              node=(1, 1, 'reward'), screen='货币战争-备战',
              family='logic_action', actor='SimEngineV2'),
        mkrow('t5', 'node_path',
              {'plane': 1, 'seq': [{'token': None}, {'token': 'reward'},
                                   {'token': 'battle'}]},
              node=(1, 1, 'reward'), screen='货币战争-备战',
              family='logic_action', actor='SimEngineV2'),
    ]
    _, md = build(rows)
    assert '爻光1★(空×1)' in md
    assert '爻光1★' in md
    assert '2 座(灰×2)' in md
    assert '1 座(灰×1)' in md
    assert 'P1: —→奖励→战斗' in md
    assert '"kind":"unit"' not in md  # raw JSON 不再入单元格


def test_action_payload_brief_and_settlement_battle_chapter():
    """action 载荷人读摘要(§4 动作行,T-5);settlement 写入行 = 战斗章开章
    证据(sim 无 current_screen 形态,pipeline §4 修订),本体走章内变化块。"""
    rows = [
        mkrow('t1', 'gold', 10, node=(1, 1, 'reward'),
              family='logic_action', actor='SimEngineV2'),
        receipts_row('t2', receipt(
            'BuyCard',
            action={'card': {'name': '翡翠', 'faction': '公司', 'cost': 1,
                             'slot': 5},
                    'reason': 'dead_gold_press_buy', 'char_id': '藿藿'}),
            node=(1, 1, 'reward')),
        mkrow('t3', 'settlement', {'hp_after': 84, 'killed': True,
                                   'progress_delta': 2},
              node=(1, 1, 'battle')),
    ]
    _, md = build(rows)
    assert '翡翠(公司,1金,槽5)' in md
    assert 'reason=dead_gold_press_buy' in md
    assert '"card":' not in md
    assert '### 节点 1-1 奖励 画面-战斗' in md
    assert '胜 血 84 进度 +2' in md


def test_obs_note_entry_keys_skipped_unique_fields_kept():
    """观察尾注跳过已注册画面 0 观察键(注册表并集)——这些字段必在对应画面
    章 0 观察显示,观察回读是重复显示且时间窗归属会误挂进无关动作;非
    entry 键(pending_loss 等独有信息)保留。"""
    rows = [
        mkrow('t1', 'hp', 80, node=(1, 1, 'reward'), screen='货币战争-备战'),
        mkrow('t2', 'gold', 15, node=(1, 1, 'reward'), screen='货币战争-备战'),
        mkrow('t3', 'pending_loss',
              {'plane': 1, 'round_num': 1, 'node_type': 'battle'},
              node=(1, 1, 'reward'), screen='货币战争-备战'),
    ]
    _, md = build(rows)
    assert '- 观察: 金=15' not in md
    assert '- 败态登记(pending_loss) P1-R1 (battle)' in md


def test_obs_writes_surface_in_screen_observations():
    """0 观察动态段 = 画面 op 观察到什么本章显什么(出处 =
    tools/cw/replay_to_md.py 模块头「渲染结构」0 观察规则):非注册键的
    观察写入(实证形态 = 备战帧节点锚定 node_pos)进本章 0 观察,不再
    降级成游离章尾注记(旧形态:注记挂在最后一个动作节下,读起来像动作
    的产物);同值回读不重复,异值回读 → 章尾注记。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战',
              screen='货币战争-备战'),
        receipts_row('t2', receipt('CwOpOpenShop',
                                   screen='货币战争-备战')),
        mkrow('t3', 'node_pos', [1, 1], screen='货币战争-备战'),
        mkrow('t4', 'node_pos', [1, 1], screen='货币战争-备战'),
        mkrow('t5', 'node_pos', [1, 2], screen='货币战争-备战'),
    ]
    report, md = build(rows)
    scr = section_of_kind(report, 'node').screens[0]
    assert scr._obs_entries == {'node_pos': '[1,1]'}  # 首写定帧值
    assert '- 节点序位(node_pos) [1,1]' in md
    assert scr.annots == ['观察: 节点序位(node_pos)=[1,2]']  # 异值回读 → 章尾注记


# ---------------------------------------------------------------------------
# 策略遥测装配(render-assembly §1-§4;策略遥测迭代 T-5)
# ---------------------------------------------------------------------------


def mkrec(dtag: str, entry: str, *, op: str = 'CwActionObsParam',
          node: tuple[int, int] | None = (1, 1), payload: dict[str, Any] | None = None,
          strategy_id: str = 'probe', reason: str = '', route_tag: str = '',
          run_id: str = 'run_t') -> dict[str, Any]:
    """一条策略决策记录行(sink 落盘形态:envelope+payload;信封键闭集 =
    capture-store §2,sink 补 run_id)。"""
    env: dict[str, Any] = {
        'strategy_id': strategy_id, 'schema_version': 1,
        'dseq': int(dtag.rsplit(':', 1)[-1]),
        'dtag': dtag, 'entry': entry,
        'node': None if node is None else
                {'plane': node[0], 'round_num': node[1], 'kind': 'reward'},
        'ts': '2026-10-24T19:16:33',
        'emitted': [{'op': op, 'reason': reason, 'route_tag': route_tag}],
        'run_id': run_id,
    }
    return {'envelope': env, 'payload': payload if payload is not None else {}}


def write_strategy(tmp_path: Path, recs: list[dict[str, Any]], *,
                   name: str = 'probe_run_t.jsonl') -> Path:
    """决策记录 → tmp_path/strategy/*.jsonl(sink 同构落点)。"""
    d = tmp_path / 'strategy'
    d.mkdir(exist_ok=True)
    f = d / name
    f.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in recs) + '\n',
        encoding='utf-8')
    return d


def build_t(rows: list[dict[str, Any]], recs: list[dict[str, Any]],
            tmp_path: Path):
    """行 + 决策记录 → (report, md)(真实加载器 + build_report 两级 join)。"""
    tele = None
    if recs:
        tele = mod.load_strategy_telemetry(write_strategy(tmp_path, recs),
                                           {'run_t'})
    report = mod.build_report(rows, mod.JournalReadStats(), game_id='fixture',
                              strategy=tele)
    return report, mod.render_markdown(report)


def test_entry_screen_map_closed_set_14_rows():
    """章级挂载表 = render-assembly §2 的 14 行闭集直译(entry → 渲染章键,
    禁漂移;prep/shop/supply 动作级 join、其余 11 选择族章级挂载)。"""
    assert mod.ENTRY_SCREEN_MAP == {
        'decide_prep_screen': '画面-备战',
        'decide_shop_action': '画面-商店',
        'decide_invest_env': '画面-投资环境',
        'decide_invest_strategy': '画面-投资策略',
        'decide_supply': '画面-补给',
        'decide_encounter': '画面-遭遇',
        'decide_megastar': '画面-巨星',
        'decide_partner': '画面-伙伴',
        'decide_planner': '画面-银狼策划',
        'decide_fortune': '画面-命运卜者',
        'decide_wish_trial': '画面-祈愿试炼',
        'decide_box_card': '画面-箱子',
        'decide_expert_invite': '画面-专家邀请',
        'decide_star_tome': '画面-书卡',
    }


def test_star_tome_registry_fix_and_box_unchanged():
    """零差异例外清单(落地修订配套):SCREEN_REGISTRY 补星徽秘典
    弹窗广播行(→ 画面-书卡/star_tome_opts);CwScreenBookcard 键集修复
    (box_card_names → star_tome_opts 存量错行);武装箱两行
    (box_card_names)不动。广播行开「画面-书卡」章无缺口注记,0 观察显示
    star_tome_opts;CwScreenBoxPick 章仍「画面-箱子」。"""
    assert mod.SCREEN_REGISTRY['货币战争-星徽秘典弹窗'].title == '画面-书卡'
    assert mod.SCREEN_REGISTRY['货币战争-星徽秘典弹窗'].entry_fields \
        == ('star_tome_opts',)
    assert mod.ACTOR_REGISTRY['CwScreenBookcard'].entry_fields \
        == ('star_tome_opts',)
    assert mod.ACTOR_REGISTRY['CwScreenBoxPick'].entry_fields \
        == ('box_card_names',)
    assert mod.SCREEN_REGISTRY['货币战争-备战-武装箱选择'].entry_fields \
        == ('box_card_names',)
    rows = [
        mkrow('t1', 'current_screen', '货币战争-星徽秘典弹窗',
              screen='货币战争-星徽秘典弹窗',
              values_extra={'star_tome_opts': ['仙舟', '公司']}),
        mkrow('t2', 'current_screen', '货币战争-备战-武装箱选择',
              screen='货币战争-备战-武装箱选择',
              values_extra={'box_card_names': ['以太钻头']}),
    ]
    report, md = build(rows)
    screens = section_of_kind(report, 'node').screens
    assert [s.title for s in screens] == ['画面-书卡', '画面-箱子']
    assert screens[0].entry == [('star_tome_opts', ['仙舟', '公司'])]
    assert screens[1].entry == [('box_card_names', ['以太钻头'])]
    assert '缺口' not in md   # 星徽秘典弹窗已成注册键,不再原样开章
    assert '- 星徽秘典候选(star_tome_opts) ["仙舟","公司"]' in md


def test_strategy_feature_off_zero_diff(tmp_path: Path):
    """功能关闭态(render-assembly §1):journal 同根无 strategy/(或目录
    空)→ 路径解析 None;记录全被 run 过滤 → 同关闭态;两种形态报告与
    无遥测渲染逐字节一致(局头无策略遥测行、无策略依据块);显式路径
    不存在 = 用法错。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战', screen='货币战争-备战'),
        receipts_row('t2', receipt('CwActionWearEquipParam', dtag='probe:1')),
    ]
    assert mod.strategy_telemetry_path(None, tmp_path) is None
    (tmp_path / 'strategy').mkdir()
    assert mod.strategy_telemetry_path(None, tmp_path) is None   # 空目录
    report = mod.build_report(rows, mod.JournalReadStats(), game_id='x')
    md_off = mod.render_markdown(report)
    assert '策略遥测' not in md_off
    assert '策略依据' not in md_off
    other = mod.load_strategy_telemetry(write_strategy(
        tmp_path, [mkrec('probe:1', 'decide_prep_screen', run_id='run_z')]),
        {'run_t'})
    assert other.records == []   # run 过滤全滤出
    report2 = mod.build_report(rows, mod.JournalReadStats(), game_id='x',
                               strategy=other)
    assert mod.render_markdown(report2) == md_off   # 零记录 = 关闭态零差异
    try:
        mod.strategy_telemetry_path(str(tmp_path / 'nope'), None)
        raise AssertionError('应抛 _UsageError')
    except mod._UsageError:
        pass


def test_loader_tolerates_bad_lines_and_filters_run(tmp_path: Path):
    """加载(render-assembly §1):非法行(坏 JSON/非对象/缺 envelope/缺
    dtag)逐行跳过不致命;envelope.run_id ∉ 本局运行段过滤丢弃;重复
    dtag 首现优先(dseq 唯一)。"""
    d = tmp_path / 'strategy'
    d.mkdir()
    good1 = json.dumps(mkrec('probe:1', 'decide_supply',
                             payload={'k': 1}), ensure_ascii=False)
    good2 = json.dumps(mkrec('probe:2', 'decide_supply'), ensure_ascii=False)
    dup = json.dumps(mkrec('probe:1', 'decide_box_card'), ensure_ascii=False)
    other = json.dumps(mkrec('probe:9', 'decide_supply', run_id='run_z'),
                       ensure_ascii=False)
    (d / 'probe_run_t.jsonl').write_text(
        '\n'.join(['{"v": 1, 截断半行', '[1, 2]', '"just a string"',
                   '{"no": "envelope"}', good1, good2, dup, other]),
        encoding='utf-8')
    tele = mod.load_strategy_telemetry(d, {'run_t'})
    assert [r.dtag for r in tele.records] == ['probe:1', 'probe:2']
    assert tele.by_dtag['probe:1'].entry == 'decide_supply'   # 首现优先
    assert tele.records[0].payload == {'k': 1}
    assert ('decide_supply', 1, 1) in tele.by_chapter


def test_action_join_basis_block_position_and_payload(tmp_path: Path):
    """动作级 join(render-assembly §3 适用集):回执 dtag → 信封 dtag;
    依据块嵌入动作节(标题行下、动作行与状态变化表前);payload 通用
    键值渲染(嵌套紧凑 JSON,不解释语义),空 payload 单行占位。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战', screen='货币战争-备战'),
        mkrow('t2', 'gold', 30, screen='货币战争-备战',
              family='logic_action', actor='PrepActionExecutor'),
        receipts_row('t3', receipt('CwActionWearEquipParam',
                                   screen='货币战争-备战', dtag='probe:1')),
    ]
    recs = [
        mkrec('probe:1', 'decide_prep_screen', op='CwActionWearEquipParam',
              payload={'direction': {'locked': True},
                       'k_members': ['爻光']}),
        mkrec('probe:2', 'decide_prep_screen', op='CwActionWearEquipParam',
              payload={}),
    ]
    report, md = build_t(rows, recs, tmp_path)
    scr = section_of_kind(report, 'node').screens[0]
    assert [r.dtag for r in scr.actions[0].basis] == ['probe:1']
    assert '- 策略依据: probe:1(entry=decide_prep_screen, ' \
           'op=CwActionWearEquipParam)' in md
    assert '    - direction: {"locked":true}' in md
    assert '    - k_members: ["爻光"]' in md
    i_title = md.index('#### 1 穿装备')
    i_basis = md.index('- 策略依据: probe:1')
    i_action = md.index('- 动作:')
    i_table = md.index('| 字段 |')
    assert i_title < i_basis < i_action < i_table   # 标题下、变化表前
    # probe:2 无回执匹配 → 归属章「策略决策未落地」注记(不落章级小节)
    assert '- 策略决策未落地: probe:2(CwActionWearEquipParam)' in md
    assert '- 策略遥测: probe (2 条)' in md


def test_action_join_op_normalize_and_mismatch_note(tmp_path: Path):
    """指纹一致性校验(render-assembly §3):回执 op 经归一映射后与信封
    emitted.op 比对——CwOpOpenShop → CwActionOpenShopParam 命中正常挂
    依据;失配(陈旧 dtag 搭错)→ 回执按无依据处理 + 章尾「策略 dtag
    失配」注记。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战', screen='货币战争-备战'),
        receipts_row('t2', receipt('CwOpOpenShop', screen='货币战争-备战',
                                   dtag='probe:1')),
        receipts_row('t3', receipt('CwActionBuyCardParam', dtag='probe:2')),
    ]
    recs = [
        mkrec('probe:1', 'decide_prep_screen', op='CwActionOpenShopParam'),
        mkrec('probe:2', 'decide_prep_screen', op='CwActionWearEquipParam'),
    ]
    report, md = build_t(rows, recs, tmp_path)
    prep = section_of_kind(report, 'node').screens[0]
    assert [a.op for a in prep.actions] == ['CwOpOpenShop',
                                            'CwActionBuyCardParam']
    assert [r.dtag for r in prep.actions[0].basis] == ['probe:1']  # 归一命中
    assert prep.actions[1].basis == []   # 失配 = 按无依据
    assert '- 策略 dtag 失配: probe:2(CwActionBuyCardParam)' in md
    assert not report.strategy.unattached   # 失配记录已消费,不再计未归属


def test_retry_chain_multi_basis_in_receipt_order(tmp_path: Path):
    """重试链一节多回执(render-assembly §3):依据块按回执顺序逐条列出,
    每条标各自 dtag;链内无 dtag 回执跳过。"""
    rows = [
        receipts_row('t1', receipt('CwActionStartBattleParam',
                                   reason='弹窗未关', dtag='probe:1')),
        receipts_row('t2', receipt('CwActionStartBattleParam',
                                   reason='定位缺失', dtag='probe:2')),
        receipts_row('t3', receipt('CwActionStartBattleParam')),  # 无 dtag → 跳过
    ]
    recs = [
        mkrec('probe:1', 'decide_prep_screen', op='CwActionStartBattleParam'),
        mkrec('probe:2', 'decide_prep_screen', op='CwActionStartBattleParam'),
    ]
    report, md = build_t(rows, recs, tmp_path)
    act = section_of_kind(report, 'node').screens[0].actions[0]
    assert len(act.chain) == 3   # 三条回执合并一节
    assert [r.dtag for r in act.basis] == ['probe:1', 'probe:2']
    assert md.index('策略依据: probe:1') < md.index('策略依据: probe:2')


def test_chapter_level_fifo_and_section_position(tmp_path: Path):
    """章级挂载(render-assembly §3;章级族 fixture 取遭遇——补给已迁动作
    级 join,不再作章级 fixture):(entry, node) 匹配 + 同键
    多章 FIFO(records dseq 序对章首现序分配);依据 = 0 观察后独立小节
    「#### 策略依据」,不破坏「0 观察 → 动作×N → 策略评价」结构。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-遭遇节点',
              node=(1, 1, 'encounter'), screen='货币战争-遭遇节点'),
        mkrow('t2', 'current_screen', '货币战争-备战', node=(1, 1, 'encounter'),
              screen='货币战争-备战'),
        mkrow('t3', 'current_screen', '货币战争-遭遇节点',
              node=(1, 1, 'encounter'), screen='货币战争-遭遇节点'),
    ]
    recs = [
        mkrec('probe:1', 'decide_encounter', node=(1, 1), payload={}),
        mkrec('probe:2', 'decide_encounter', node=(1, 1),
              payload={'window': {'爻光': {'open': True}}}),
    ]
    report, md = build_t(rows, recs, tmp_path)
    screens = section_of_kind(report, 'node').screens
    assert [s.title for s in screens] == ['画面-遭遇', '画面-备战', '画面-遭遇']
    assert [r.dtag for r in screens[0].strategy_records] == ['probe:1']
    assert [r.dtag for r in screens[2].strategy_records] == ['probe:2']
    assert '- probe:1(entry=decide_encounter, op=CwActionObsParam)' in md
    assert '- payload: (本帧无策略载荷)' in md
    assert '- window: {"爻光":{"open":true}}' in md   # 嵌套紧凑 JSON
    i_obs = md.index('#### 0 观察')
    i_basis = md.index('#### 策略依据')
    i_next = md.index('### 节点 1-1 遭遇 画面-备战')
    assert i_obs < i_basis < i_next   # 0 观察后、下一章前
    assert not report.strategy.unattached


def test_supply_action_join_and_chapter_skip(tmp_path: Path):
    """补给迁动作级 join(补给决策链接入批):decide_supply ∈ 动作级适用
    集——回执 CwActionPickSupplyOp 经归一映射对 CwActionPickSupplyParam,
    依据块挂动作节;章级小节对适用集入口关闭(两级互斥);无回执匹配的
    补给记录 → 归属章「策略决策未落地」注记(与 prep/shop 同待遇)。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-补给', node=(1, 1, 'supply'),
              screen='货币战争-补给'),
        receipts_row('t2', receipt('CwActionPickSupplyOp',
                                   screen='货币战争-补给', dtag='probe:1')),
    ]
    recs = [
        mkrec('probe:1', 'decide_supply', op='CwActionPickSupplyParam'),
        mkrec('probe:2', 'decide_supply', op='CwActionPickSupplyParam'),
    ]
    report, md = build_t(rows, recs, tmp_path)
    scr = section_of_kind(report, 'node').screens[0]
    assert [r.dtag for r in scr.actions[0].basis] == ['probe:1']
    assert '- 策略依据: probe:1(entry=decide_supply, ' \
           'op=CwActionPickSupplyParam)' in md
    assert not scr.strategy_records   # 章级小节对适用集入口关闭
    assert '#### 策略依据' not in md
    assert '- 策略决策未落地: probe:2(CwActionPickSupplyParam)' in md


def test_header_three_states_and_unattached_counts(tmp_path: Path):
    """局头策略遥测行三态(render-assembly §4):无遥测整行省略;全归属 =
    「- 策略遥测: <sid> (N 条)」;未归属(node=null 帧 / 无归属章)> 0 →
    行尾追加 (未归属 M 条) 且不逐条展开。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-备战', screen='货币战争-备战'),
        receipts_row('t2', receipt('CwActionWearEquipParam', dtag='probe:1')),
    ]
    recs_ok = [mkrec('probe:1', 'decide_prep_screen',
                     op='CwActionWearEquipParam')]
    _, md_ok = build_t(rows, recs_ok, tmp_path)
    assert '- 策略遥测: probe (1 条)' in md_ok
    assert '未归属' not in md_ok
    recs_null = recs_ok + [
        mkrec('probe:2', 'decide_partner', node=None,
              op='CwActionPickPartnerParam'),   # node=null → 不入章级
        mkrec('probe:3', 'decide_supply', node=(5, 5)),   # 无归属章
    ]
    report_n, md_n = build_t(rows, recs_null, tmp_path)
    assert '- 策略遥测: probe (3 条)(未归属 2 条)' in md_n
    assert 'probe:2' not in md_n   # 未归属不逐条展开
    assert 'probe:3' not in md_n
    assert report_n.strategy.unattached and len(report_n.strategy.unattached) == 2


def test_cli_strategy_telemetry_end_to_end(tmp_path: Path, capsys: Any):
    """CLI 集成(render-assembly §1):journal 同根 strategy/ 缺省发现生效
    (--stdout 报告含局头行与章级依据节;章级族 fixture 取遭遇——补给已迁
    动作级 join);无 strategy/ 目录时零差异(无策略遥测行);显式路径不
    存在 = 用法错退出 2。"""
    rows = [
        mkrow('t1', 'current_screen', '货币战争-遭遇节点',
              node=(1, 1, 'encounter'), screen='货币战争-遭遇节点'),
    ]
    f = _write_journal(tmp_path, [json.dumps(r, ensure_ascii=False)
                                  for r in rows])
    argv = ['--journal', str(f), '--game-id', 'cli_t', '--stdout']
    assert mod.main(argv) == 0
    assert '策略遥测' not in capsys.readouterr().out   # 无 strategy/ → 关闭态
    rec = mkrec('probe:1', 'decide_encounter', node=(1, 1),
                payload={'k_members': ['爻光']})
    d = tmp_path / 'strategy'
    d.mkdir()
    (d / 'probe_run_t.jsonl').write_text(
        json.dumps(rec, ensure_ascii=False), encoding='utf-8')
    assert mod.main(argv) == 0
    md = capsys.readouterr().out
    assert '- 策略遥测: probe (1 条)' in md
    assert '#### 策略依据' in md   # 章级 = 独立小节(非动作级前缀形态)
    assert '- 策略依据: ' not in md
    assert '- probe:1(entry=decide_encounter, op=CwActionObsParam)' in md
    assert '    - k_members: ["爻光"]' in md
    assert mod.main(argv + ['--strategy-telemetry',
                            str(tmp_path / 'nope')]) == 2   # 显式缺路径 = 用法错
