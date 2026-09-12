"""货币战争假游戏 fixture 包(T-120 sim 重设计 批 0 骨架)。

**假游戏(fake game)** = 冒充游戏本体的测试替身:持有对局状态机并按
游戏规则响应动作。本包内容:

- :mod:`fake_match` —— ``FakeMatch`` 状态机(单一对象):真 GameState
  + 画面身份 + 浮层栈 + 四股随机流;动作转移唯一入口 ``apply`` 直调
  ``cw_state.simulate`` 单一源;战斗结算直调 coarse 主路径与 Δ池;
- :mod:`fake_ports` —— 观察源/执行器两端口的假实现(实现
  ``sr_od.application.currency_war.cw_game_ports`` 的协议)。

**住点与依赖方向**:住测试仓(``sr-od-test/fixtures/``),import 生产
模块单向合法,生产 import 测试仓 = 结构违规(方案 §2.2 住点行;§3.3
禁散写判据)。方案出处 = `.debug/temp/currency_war/t120_sim_redesign/
方案.md` §2.2(**易失产物**,ADR 落点待 T-120 退役批分配,后续批回填)。

**骨架范围申报(批 1 补全)**:本包交付「状态容器 + 动作转移单一源直调 +
战斗结算直调」的最小实现;收入/装备发放/位面继承的规则模块、遥测同构、
真 op 跑通归批 1+(方案 §6.2 分批表)。
"""
