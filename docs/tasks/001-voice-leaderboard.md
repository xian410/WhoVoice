# 任务 \#001 声纹匹配排行榜功能（一期轻量可扩展版｜二期可迭代）

**创建日期**：2026\-06\-22

**更新日期**：2026\-06\-23（可扩展轻量化重构）

**状态**：📋 待开发（一期简易版）

**优先级**：P1 \- 核心互动功能

**预估工时**：8\-10h（精简可上线版本）

**版本定位**：一期**规范底层、最小可用、高可扩展**，不堆砌功能；二期无缝迭代完善全部能力

## 一、整体开发策略（核心变更）

本次只开发**最小闭环可用版本**，核心目标两个：

1. **底层逻辑完全规范**：数据模型、校验规则、防刷机制、权限逻辑全部按生产标准写死，不留技术债；

2. **上层功能轻量化**：删减非刚需页面、缓存、定时任务、复杂统计，保证快速上线；

**分层迭代原则**：

- **一期（当前）**：核心上榜流程 \+ 单人明星榜单 \+ **全局人气热榜Top20** \+ 严格底层校验，保证功能可用、数据可信、无刷榜漏洞；

- **二期（后续）**：个人记录中心、周/月榜、分享海报、敏感词过滤、定时清理、缓存优化全部平滑叠加，**无需改表、无需重构接口**。

## 二、一期保留 \& 砍掉功能清单

### 2\.1 一期【必须保留】（底层规范\+核心功能）

- 标准数据库模型（含防刷、软删除、唯一约束、索引，完全对齐生产）

- 安全上榜核心逻辑：**后端task\_id溯源验分、禁止前端传分**

- 基础防刷体系：单task唯一上榜、0\.3阈值双层拦截、IP限流

- 用户自定义昵称 \+ 匿名兜底机制

- 单明星专属排行榜（Top50）\+ 全局人气热榜（Top20）\+ 实时排名返回

- 完整前后端提交流程、异常拦截、边界校验

- 基础隐私规范：音频不公开、gitignore隔离资源

### 2\.2 一期【暂时砍掉，二期迭代】（不影响底层架构）

- 我的个人挑战记录页

- 音频哈希去重、精细敏感词过滤

- 榜单缓存、高性能排序优化（二期完善，一期裸查可用）

- 90天音频自动清理定时任务

- 榜单分享、成就勋章、热门明星快捷入口

- 周榜/月榜时间维度榜单

**关键保障**：以上功能全部预留字段、接口、路由扩展位，二期直接开发，无需重构一期代码。

## 三、一期核心业务规则（100%生产严谨，无缩水）

底层规则完全对齐正式版本，从根源杜绝漏洞、数据错乱、刷榜问题，不做轻量化妥协。

1. **分数可信规则**：前端仅传 task\_id，后端从匹配任务溯源读取真实分数，彻底杜绝篡改；

2. **上榜阈值规则**：相似度≥0\.3可上榜，前端UI拦截 \+ 后端强制二次拦截；

3. **唯一上榜规则**：一个 task\_id 全局仅可提交一次上榜，数据库唯一约束兜底；

4. **同分排序规则**：分数一致时，先提交者排名靠前；

5. **昵称规则**：支持用户自定义昵称（2\-50字符），空值/非法格式自动兜底唯一匿名昵称`声纹探险家_xxxxxx`；

6. **限流规则**：单IP 1分钟最多3次上榜提交，防批量刷榜；

7. **热榜排序规则（一期新增）**：优先按**上榜总人数**降序，人数相同按**该歌手最高相似度**降序，取Top20；

8. **数据规范**：所有上榜数据携带IP、任务ID、时间戳，支持后续溯源治理。

## 四、一期交互流程（最简闭环）

用户录音/上传音频 → 声纹匹配完成 → Top1结果分数≥0\.3展示【挑战上榜】按钮

→ 点击按钮弹出弹窗（支持自定义昵称/留空）

→ 前端提交 task\_id \+ 音频 \+ 可选昵称

→ 后端全量校验、入库、返回实时排名

→ 弹窗展示上榜结果，支持跳转对应明星排行榜页面

## 五、后端开发（一期规范轻量版）

### Task B1：数据模型（完全完整版，不简化，预留二期扩展）

模型字段、索引、约束全部对齐生产版本，二期新增功能无需改表结构

```python
class LeaderboardEntry(models.Model):
    """声纹匹配排行榜条目【一期规范可扩展版】"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    celebrity_name = models.CharField(max_length=255, db_index=True)
    nickname = models.CharField(max_length=50, default="", blank=True)
    score = models.FloatField(db_index=True)
    audio_path = models.CharField(max_length=512, blank=True, default="")
    task_id = models.CharField(max_length=64, unique=True, db_index=True)
    client_ip = models.CharField(max_length=64, blank=True, default="")
    audio_hash = models.CharField(max_length=64, blank=True, default="")
    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-score", "created_at"]
        indexes = [
            models.Index(fields=["celebrity_name", "-score"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.nickname or '匿名用户'} → {self.celebrity_name} ({self.score:.2%})"

```

### Task B2：序列化器（精简可用，预留扩展）

```python
class LeaderboardSubmitSerializer(serializers.ModelSerializer):
    audio = serializers.FileField(write_only=True, required=True)
    nickname = serializers.CharField(max_length=50, required=False, allow_blank=True)
    task_id = serializers.CharField(max_length=64, required=True)

    class Meta:
        model = LeaderboardEntry
        fields = ["task_id", "nickname", "audio"]

class LeaderboardEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardEntry
        fields = ["rank", "nickname", "score", "created_at"]

```

### Task B3：一期仅保留2个核心API

删减二期接口，保证一期极简，同时路由结构规范，二期直接新增即可

- `POST /api/voice-matching/leaderboard/submit/`：上榜提交核心接口（全量校验逻辑）

- `GET /api/voice-matching/leaderboard/{name}/`：单明星排行榜查询接口

- `GET /api/voice-matching/leaderboard/`：全局人气热榜接口（一期新增，返回Top20热门明星）

### Task B4：核心业务逻辑（完全规范无缩水）

一期核心校验逻辑全部保留，不做简化，保证数据可信：

1. 通过 task\_id 溯源匹配任务，获取真实明星名、真实分数；

2. 校验分数≥0\.3、task\_id 未重复上榜；

3. 校验昵称格式，非法/空昵称自动兜底默认匿名名称；

4. 记录客户端IP，执行限流判断；

5. 保存音频与榜单数据，计算并返回用户实时排名。

### Task B5：Admin 注册 \+ 数据迁移

完整后台管理能力，方便一期数据核查、二期数据治理

## 六、前端开发（一期极简闭环）

### 保留核心能力

- 结果卡片 Top1 上榜按钮 UI 展示

- 上榜确认弹窗（自定义昵称输入、loading、成功提示）

- 排行榜页面双 Tab 切换：【明星榜单 / 人气热榜】

- 单明星榜：前三名特殊样式、空状态、分页

- 人气热榜：展示 Top20 热门明星（挑战人数\+最高相似度）

- 基础路由、状态管理

### 一期前端删减内容

- 导航栏榜单入口（二期再加）

- 个人记录页

- 复杂筛选、搜索、热门标签（二期优化）

## 七、一期测试用例（聚焦核心漏洞）

1. 前端/抓包篡改分数，后端溯源拦截，榜单分数可信；

2. 同一task\_id重复提交，拦截重复上榜；

3. 低分＜0\.3强制提交，后端二次拦截；

4. 超长/特殊符号/空白昵称，自动兜底匿名名称；

5. 高频IP请求，触发限流拦截。

## 八、二期可扩展清单（无需重构，直接叠加）

所有扩展能力均**基于一期现有表结构、路由架构、数据规范**，零改造成本：

- 新增个人挑战记录查询接口、个人中心模块

- 叠加音频哈希去重、精细化敏感词过滤

- 新增榜单缓存、热榜高性能排序优化（一期裸查，二期加缓存提速）

- 开发定时任务：90天音频自动清理

- 迭代周榜/月榜时间维度榜单

- 新增分享海报、成就勋章、热门明星筛选功能

## 九、开发优先级

- **P0 必做（一期上线）**：完整底层模型、核心校验逻辑、上榜提交、单明星榜单、前后端闭环

- **P1 暂缓（二期迭代）**：所有增值功能、优化功能、统计功能

## 十、架构可扩展性总结

本次一期开发严格遵循**底层卡死规范、上层最小可用**原则：

数据模型、安全校验、防刷逻辑、路由规范全部按生产标准落地，无临时方案、无技术债；仅删减非刚需展示层与优化层功能，后续二期所有功能均可**无缝叠加、无需改表、无需重构、无需数据迁移**，完美适配快速上线\+长期迭代的开发节奏。

> （注：部分内容可能由 AI 生成）
