"""货币战争复盘渲染器(tools/cw/replay_to_md.py)fixture 单测。

测试文件组织说明:tools/ 目录无 src 镜像先例(tools 不是 src-layout 包),
无法按「src 路径同源镜像」落位,按工具名组织为本文件(规范变通记录于
文件头,sr-od-test/README.md「测试文件组织」的镜像规则以 src 文件为锚)。

被测行为锁 = 渲染设计约定,出处(持久索引):
- docs/develop/sr_od/application/currency_war/changes/2026-10-16-journal-review-renderer/
  details/pipeline.md(§1 行加载 / §2 节点分组 / §3 无 node 行归属链 /
  §4 画面章切分 / §5 动作节切分与状态差分 / §7 CLI)
- 同目录 details/render-spec.md(§1 骨架 / §2 局头 / §3 画面注册表 /
  §4 动作节显示 / §5 特殊情况)

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


def receipt(op: str, applied: bool = True, reason: str = '', detail: str = '',
            screen: str = '', **extra: Any) -> dict[str, Any]:
    """一条动作回执(载荷结构 = note_action_receipt 写端形态)。"""
    r: dict[str, Any] = {'op': op, 'applied': applied, 'reason': reason}
    if detail:
        r['detail'] = detail
    if screen:
        r['screen'] = screen
    r.update(extra)
    return r


def receipts_row(ts: str, *recs: dict[str, Any], **kw: Any) -> dict[str, Any]:
    """receipts 锚行(after = 回执滚动窗整窗)。"""
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
    显影 actor 名(同章同 actor 聚合一条带计数);非 obs 行禁止静默混入动作
    状态变化表(一律走尾注);receipts 动作节机制与快照章形态 op
    (CwScreenPrep 等)/非画面 actor(cw_observation)不受判定影响。"""
    rows = [
        mkrow('t1', 'hp', 80, screen='货币战争-备战'),            # 开备战章
        receipts_row('t2', receipt('BuyCard')),                   # 动作节 1
        # obs 未注册画面 op:值显影(观察尾注)+ actor 显影(缺口)
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
    # actor 名显影:obs ×1 + 非 obs ×2 聚合一条带计数
    assert '缺口: 未注册写入者 CwScreenBrandNewPayload ×3' in joined
    assert '- 缺口: 未注册写入者 CwScreenBrandNewPayload ×3' in md
    # obs family:值仍由观察尾注显影;非 obs family:不走观察尾注
    assert any(a.startswith('观察: new_screen_payload=') for a in scr.annots)
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
# 切章锚 = field='current_screen' 写入行本体;相邻合并键 = title)
# ---------------------------------------------------------------------------


def test_stale_snapshot_cs_never_switches_chapter():
    """切章证据收窄:非广播行携带的快照 cs 只作归属,永不作为切章锚——
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
    """动作锚 = receipts 且 same_value≠true;no-op 整窗重写(same_value=
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
    """重试链合并:连续回执同 op 且前条 applied=false → 合并一节,节内
    逐条列出(实测样例 StartBattle 重发链);异 op 锚仍开新节。"""
    rows = [
        receipts_row('t1', receipt('StartBattle', applied=False,
                                   reason='弹窗未关')),
        receipts_row('t2', receipt('StartBattle', applied=True,
                                   detail='出战已点击')),
        receipts_row('t3', receipt('BuyCard')),
    ]
    report, md = build(rows)
    actions = section_of_kind(report, 'node').screens[0].actions
    assert [a.op for a in actions] == ['StartBattle', 'BuyCard']
    assert len(actions[0].chain) == 2  # 链内逐条
    assert actions[0].chain[0]['applied'] is False
    assert '#### 1 出战' in md


def test_delta_prev_chain_chapter_attribution_and_trailing():
    """状态差分:前值 = 之前最近同 field 写入行 after(链跨行);无前值行
    → 章内变化块(无锚前缀写入行);变化行挂自身所在画面章(跨章不串挂);
    章内变化块在动作锚之前。"""
    rows = [
        # 节点 1-1:开章行(gold 首写,无前值 → 章内变化块)→ 锚 → 变化
        mkrow('t1', 'gold', 30, screen='货币战争-备战',
              family='logic_action', actor='PrepActionExecutor'),
        receipts_row('t2', receipt('BuyCard')),
        mkrow('t3', 'gold', 29, screen='货币战争-备战',
              family='logic_action', actor='PrepActionExecutor'),
        # 节点 1-2:变化行挂自身章,前值跨组接链(29)
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
    assert [(d.field, d.before, d.after) for d in s11.actions[0].deltas] \
        == [('gold', 30, 29)]
    assert [(d.field, d.before, d.after) for d in s11.trailing_changes] \
        == [('gold', None, 30)]
    s12 = secs[1].screens[0]
    assert [(d.field, d.before, d.after) for d in s12.actions[0].deltas] \
        == [('gold', 29, 27)]  # 前值跨组接链;归属在 1-2 章(不串挂 1-1)
    assert '| 金 | 30 → 29 |' in md
    assert '| 金 | (起点) → 30 |' in md


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
    assert any(a.startswith('观察: round_fresh_buys=')
               for a in prep.annots)
    # settlement 行(cs=战斗等待)归「画面-战斗」章的章内变化块,不入
    # 动作节 deltas、不入备战章(render-spec §3 战斗章注册行)
    battle = [s for s in screens if s.title == '画面-战斗']
    assert battle and [d.field for d in battle[0].trailing_changes] \
        == ['settlement']
    assert '| 结算 | (起点) → 胜 血 84 进度 +2 等级 4 经验 0/6 连胜 0 |' in md


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
    assert '- 概率 1→100%、2→0%' in md


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
    assert '| 金 | (起点) → 15 |' in md
    assert '| 金 | 15 → 15 |' not in md
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
    """观察尾注规则(§5 修订):空值不渲染;prev_screen/current_screen 路由
    键跳过;同章同 (field, 值) 去重。"""
    rows = [
        mkrow('t1', 'hp', 80, node=(1, 1, 'reward'), screen='货币战争-备战'),
        mkrow('t2', 'prev_screen', '货币战争-战斗等待', node=(1, 1, 'reward'),
              screen='货币战争-备战'),
        mkrow('t3', 'overflow_card', '', node=(1, 1, 'reward'),
              screen='货币战争-备战'),
        # 去重样本用非 entry 键字段(entry 键整条跳过,见 entry 键跳过测试)
        mkrow('t4', 'node_pos', [1, 1], node=(1, 1, 'reward'),
              screen='货币战争-备战'),
        mkrow('t5', 'node_pos', [1, 1], node=(1, 1, 'reward'),
              screen='货币战争-备战'),
    ]
    _, md = build(rows)
    assert 'prev_screen' not in md
    assert '溢出卡' not in md
    assert md.count('node_pos=[1,1]') == 1


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
    章 0 观察显影,观察回读是重复显影且时间窗归属会误挂进无关动作;非
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
    assert '- 观察: pending_loss=' in md
