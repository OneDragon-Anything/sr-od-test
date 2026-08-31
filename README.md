# SR测试项目

需要将本目录设置成 test source folder

## 测试纪律(硬规则)

1. **`test_context` 是 session 级共享**(conftest):改其属性(`run_context`/`controller` 等)一律
   `monkeypatch.setattr`(自动还原);裸赋值会污染后续**别的测试文件**(单跑必过/全量必挂的假
   flaky),conftest 有 autouse 守卫(警告+还原),但守卫不是写裸赋值的许可。
2. **测试不写真实 `.debug/` 路径**:落盘一律 `tmp_path` 或 monkeypatch 重定向目标模块的
   `_DIR` 常量;`finally` 还原动过的外部状态(文件备份-恢复、flag 清理)。已有的:conftest
   autouse 机检层 `_isolate_debug_images` 把测试进程内 `debug_utils.save_debug_image` 恒重定向
   tmp_path(op 框架异常 handler 的自动存图也在内);其它落盘点照此办理。
3. **fixture 驱动的 op 流程测试**用 `test/harness/fixture_controller.py`(`FixtureController`
   + `WatchdogOperationMixin` + `enter_running_state`/`reset_running_state`);运行态前置/复位
   已封装在 helper 里,别手写 `_run_state` 裸赋值。
4. **op 流程测试的 `execute()` 必须包 `fast_sleep()`**(harness 提供):mock 画面瞬间切换,
   框架的轮间/点击前等待(`pre_delay`/`_after_round_wait`)纯属空等——2026-08-25 实测流程
   测试 ~60% 时间在 `time.sleep`。用法 `with fast_sleep(): result = op.execute()`。
5. **测试不发真实网络请求**:凡被测链路会触网(如配置初始化拉代理地址),在测试入口
   mock 掉——网络不仅慢(实测单次 ~1s)还引入不确定性(断网/代理变化 = 假 flaky)。
   已有的:conftest 短路 `ghproxy_service.update_proxy_url`;新增触网路径照此办理。
6. **锁契约不锁分布,重结果一次复用**:
   - 断言「输出结构/范围/回显」而非统计数值——锁分布数值 = change-detector 陷阱,
     任何合法改动必红(判例:`test_batch_stats_shape` 只锁形状;smoke 的 docstring 同款约定);
   - 同一份昂贵计算在**同一次测试运行内只算一次**,多条断言共享结果——逐条各算
     = 纯浪费(判例:kwarg 审计三条测试曾各扫全仓一遍 3×3s,现共享一次;
     cli_smoke 曾同 seed 独立跑两遍 25 局);
   - 昂贵的**可序列化中间产物**(逐局终值等)优先从已有产物(账本/报告)提取,
     别为断言再跑一遍。
7. **批量/循环模拟的 n 取「断言成立的最小值」**:断言全是形状检查时 n=10 与 n=60
   等价(实测 7.9s→1.2s);更大的样本量属于 sim A/B 日常工作流(n=300 三窗口),
   不该由单元测试承担。同理:不落盘选项(`ledger=False`)优先于默认落盘。
8. **锁的存在性纪律**(写锁/改锁/删锁四判据):
   - **出处落锁内,且必须是持久索引**:锁的设计出处写在 docstring/注释(不是
     commit message),取值为 ADR-NNNN / 文档路径+节名 / 纯语义描述(如
     「25 局实机 HP 轨迹校准」)。会话局部编号(W 轮次号 / review rN / D-xxx /
     T#97 等)不构成出处——它们在 docs 树里检索不到,等于没写。批报告类
     出处(`.debug/` 路径+批号)可暂记,但批报告属易失产物,后续批须回填
     ADR/文档指针。
   - **「登记门」与「快照锁」分形态给容差**:强迫显式登记语义的锁(如 registry
     字段面期望表:增删字段/改默认/改类型=红且点名字段)允许高频被动更新——
     它的高换手正是反机械跟绿机制的运转证据;与之相对,锁统计数值/不可读
     哈希差的纯快照锁才是 change-detector 陷阱。判别问句:**「这把锁红的时候,
     我知道该登记什么语义吗?」**知道=登记门,照常跟绿;不知道=快照陷阱,
     先重推语义再动。
   - **改锁值必须同步锁内旧表述**:断言值与 docstring/注释写的是同一事实,
     出现两个版本(如注释写 315、断言 335)= 机械跟绿已发生的现场证据。
     跟绿时注释不同步与跟绿本身同罪,改锁批必查。
   - **重复断言构成删/并理由,「老」不构成**:同一断言出现在两文件,或同文件
     两锁辖同一事实 → 择一保留、另一处删或留指针注释。「这锁老」不是删锁
     理由;判删必须引设计文档证被锁行为已非设计意图。
9. **测试隔离「整条副作用链」,生产副作用「缺省关+显式接通」**(w505 全集假红
   实证:安灯测试沿调用链惰性触发真停线 → gc 扫描命中 session 级 ctx 写停机位
   +真实 flag,monkeypatch 不辖此副作用 → 后续 execute 全撞刹车):
   - 被测生产路径含**模块级全局**(handler/闩锁/计数器/缓存)时,setup 必须
     一并桩化/清空——patch 清单来自「沿调用链 grep 模块全局」,不来自「我
     调了什么」;
   - 生产模块的对外副作用(停机/写 flag/截图/外部 IO)一律 `set_xxx_handler`
     注册模式,**缺省 None=不做**,生产在启动点显式接通;禁新写「缺省 None→
     惰性 import 真实现」(判例:L0 安灯槽注释,`cw_telemetry._L0_ANDON_HANDLER`);
   - conftest 已有守卫:整对象替换(`_guard_shared_ctx`)+ 运行残留
     (`run_context.last_run_result`,警告+自动复位)——守卫是防线不是许可,
     漏桩仍要在源头修。
10. **源码锁三档判据**(2026-08-31 瘦身批;CW 域实测 114 处 getsource 逐档处决后沉淀):
    - **实现形状锁 = 禁**:断言活代码的字面量/缩进/禁子串/变量名/调用行序——
      合法重构即假红(判例:断言 `reg_mod.DEFAULT_REGISTRY` 含某行、含缩进的
      换行字面量、用 `.index()` 比两行先后);
    - **接线存在性烟雾 = 容忍**(至多 1 条,docstring 须引用失守事故):断言某
      调用点存在,防证据链/防线静默脱落(判例:`test_cw_w518` briefing 遥测
      落账);该 op 有了 fixture harness 就应升级为行为锁;
    - **顺序即语义 = 容忍但记债**:断言的是行为边界而非行存在(判例:w222
      补拷 equips 必须在 decide_prep 之后——提前拷=改决策行为),无更便宜
      观测点时保留;重构该处代码时同步改写锁。
    - **合法的源码扫描**:①墓碑扫描——断言退役符号无残留(带变异自检更佳,
      范本 `test_cw_w620` grep 守卫);②依赖方向/单一源守卫——kernel 禁依 obs、
      判据禁第二源(判例:`test_cw_w724` 禁直调概率符号);③包/注册表布局守卫。
11. **数值锁必须推导锚定**:期望值从单一源推导式现算(registry 常量/证明集
    公式),不得手抄常数(判例正:`test_cw_blood_alarm_threshold_backing` 断言
    `emergency_hp ∈ (2×L_c(rung2), rebirth_floor+L_c)`;判例反:w245 断言评分
    栈==2.0 且自供「漂移即红」——红不含语义=change-detector,已删)。
12. **被测代码必须被调用,禁自抄复刻**:测试体不得复刻被测逻辑再断言自己抄的
    结果(判例:difficulty_readchain 曾在测试内重写「live 优先于 session」的
    if/else——生产翻转块改坏它照样绿;已删)。装饰品测试的识别特征:删掉被测
    函数后它依然绿。
13. **写新锁的落点与形状**:
    - 新锁写进所属机制的**主题文件**(如 `test_cw_merge.py`/`test_cw_plane_p2.py`),
      禁新建一轮一修复命名(`test_cw_wNNN_*`)的文件——主题合并批已把 125 个
      轮次文件归并为 22 个主题文件,别再长回来;
    - 已知 wart(docstring 自认「解耦时会改」的行为)不得立锁,登记挂账替代
      (判例:w313 boss 投影 +2 锁已删);
    - 同机制家族共用构造器,放主题文件头部;跨文件的复制夹具是漂移源头。

## 写锁/评审三问(进门自检)

1. 这条锁红的时候,我知道该登记什么语义吗?(答不出=快照陷阱,见第 8 条)
2. 什么**真实错误**会杀了它?答不出具体错误场景=装饰品(见第 12 条)。
3. 这条事实是否已有别的锁?同层有=删;跨层要说明新增价值(接线/端到端)。

## 运行速度

- **标准跑法 = 串行**:`uv run pytest sr-od-test/`(CI 资源有限,测试规范以串行为准;
  2026-08-25 全链路优化后实测:冷跑 ~2:15、warm 跑 **~2:00**;优化前 5:15)。
- **OCR 结果持久缓存**(`.pytest_cache/d/ocr_memo/`,conftest 内置):内容哈希
  + 模型指纹键控,跨会话复用同一 fixture 的推理结果(id_mark 单文件 65s→8s);
  模型更新自动失效,`pytest --cache-clear` 一键清;CI 恒冷路径,无收益也无成本。
- **OCR 设备跟随本地 `config/model.yml` 的 `ocr_use_gpu`**(测试 ctx 继承):
  本机 `true` = DirectML,实测 553ms/张 vs CPU 759ms/张(快 ~27%),且 6 张 fixture
  两种设备文本集完全一致、DML 同图多次自洽;无 DML 的环境(CI)自动回退纯 CPU,
  不会崩。注意:开 GPU 时若同机还有实机局/MCP server 在用 DML,会互相争用。
- **测试进程默认不写日志文件**(conftest 日志隔离,W276):pytest 进程退出共享
  日志写入方集合(框架 logger 挂 NullHandler 占位),从源头消掉与并行的 sim 批/
  regen 进程的午夜轮转竞态(WinError 32 随机红)。排查具体测试要看框架日志时,
  设 `SR_TEST_LOG_FILE=1` 走旧路径 `.log/test.log`(配合下一行降噪改 INFO)。
- **sim 日志已降噪**(conftest 模块级 framework log INFO→WARNING):sim 逐决策
  INFO 曾一轮全量写 100MB+ test.log。排查具体测试时,设 `SR_TEST_LOG_FILE=1`
  并临时把 conftest 里 `setLevel(logging.WARNING)` 改回 INFO 重跑。
- 本机可选 `-n 8`(dev 组已带 pytest-xdist;缓存生效后 OCR 大头已摊薄,并行
  边际收益缩小,不再显著优于串行 warm),**不作规范**:内存 ~1.2-2GB/worker、
  CPU 峰值 15+ 核;机器忙时(实机局/其他 agent 在跑)别用——实测两套 -n 8 并跑
  互相挤到 6 分钟且出时序性失败。
- 剩余耗时大头(warm 下都是真实覆盖成本):~1900 条纯逻辑测试本体、sim 真实
  计算、session 初始化(~13s)、少量冷路径 OCR(新 fixture 首见)。
- conftest 已内置两项 session 级优化:初始化时短路 `ghproxy_service.update_proxy_url`
  (避免真实网络请求);`ocr_service` 包内容哈希 memo(同一 fixture 图跨文件只推理一次)。
