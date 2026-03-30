# MultiLoader Template

这个模板用于同时维护 `common / fabric / neoforge` 三端代码，并提供基于 `gradle.properties` 的一键同步脚本。

## 使用流程

1. 克隆或使用模板创建项目。
2. 修改根目录 [gradle.properties](./gradle.properties) 中与你项目相关的配置。
3. 执行 `syncProjectFromProperties` 同步项目结构和命名。
4. 如果你写了 `accesstransformer.cfg`，再执行 `generateClassTweakerFromAt` 生成 Fabric 侧的 `.classtweaker`。

## 需要修改的关键配置

至少确认以下字段：

- `group`：Java 包名根路径（例如 `com.yourname.yourmod`）
- `mod_id`：模组 ID（小写）
- `mod_name`：模组显示名
- `common_mainclassname`：Common 主类名
- `fabric_mainclassname`：Fabric 主类名
- `neoforge_mainclassname`：NeoForge 主类名
- `license`：许可证标识（标准 SPDX/GitHub license key 时会自动同步 LICENSE 文本）

## 同步命令

### 1) 一键同步模板命名

```powershell
.\gradlew syncProjectFromProperties
```

该任务会根据 `gradle.properties`：

- 同步三模块包名
- 同步 common/fabric/neoforge 各自主类名
- 同步 `mod_id` 相关文件名与文本引用（包括 mixin 文件名等）
- 更新 common 主类中的 `MOD_ID` / `MOD_NAME`
- 当 `license` 为标准许可证名时，通过 GitHub API 更新根目录 `LICENSE`
- 自动触发一次 classtweaker 生成

### 2) 仅生成 classtweaker

```powershell
.\gradlew generateClassTweakerFromAt
```

输入文件：

- `common/src/main/resources/META-INF/accesstransformer.cfg`

输出文件：

- `common/src/main/resources/<mod_id>.classtweaker`

## AT -> CT 转换说明

- 转换器会忽略注释行。
- 只自动处理原版的访问加宽。
- 非原版类或无法可靠转换的条目会标记为 `SKIPPED`，请手动处理。
- 对于 AT 字段未写 descriptor 的情况，会尝试从 `common/build/moddev/artifacts/vanilla-*-sources.jar` 推断类型。

---

## 发布任务与 Maven 依赖控制

### Maven 发布与依赖白名单 (`mavenDependencyWhitelist`)

在 `common/build.gradle.kts`、`fabric/build.gradle.kts` 和 `neoforge/build.gradle.kts` 中，可以通过 `extra["mavenDependencyWhitelist"]` 控制哪些依赖会出现在生成的 Maven POM 文件中。

**为什么需要白名单？**  
默认情况下，Maven 发布会自动包含所有声明的依赖，但有些依赖（如 Mixin、Fabric API、NeoForge 内部依赖）不应暴露给下游使用者，否则可能导致依赖冲突或打包体积膨胀。

**白名单配置方式（支持三种匹配规则）：**

```kotlin
extra["mavenDependencyWhitelist"] = listOf(
    "org.spongepowered",               // 按 groupId 匹配（所有该 group 的依赖）
    "mixin",                           // 按 artifactId 匹配（所有该 artifact 的依赖）
    "io.github.llamalad7:mixinextras-common" // 按完整坐标 groupId:artifactId 精确匹配
)
```

**在子模块中使用：**

- `common/build.gradle.kts` 已预留白名单配置位置，默认 `emptyList()`
- `fabric/build.gradle.kts` 和 `neoforge/build.gradle.kts` 同样支持该配置

**注意：**  
白名单配置只影响 Maven 发布（`mavenJava` publication），不会影响项目编译或运行时的依赖解析。

---

### 发布到平台服务（Modrinth / CurseForge）

#### 单端发布

- Fabric 端发布任务：
  ```powershell
  .\gradlew :fabric:publishToPlatformServices
  ```
- NeoForge 端发布任务：
  ```powershell
  .\gradlew :neoforge:publishToPlatformServices
  ```

#### 聚合发布

如果需要同时发布 Fabric 和 NeoForge 两个平台，可以使用根项目的聚合任务：

```powershell
.\gradlew publishLoaderReleases
```

该任务会按顺序依次执行 `:fabric:publishToPlatformServices` 和 `:neoforge:publishToPlatformServices`。

**发布参数配置（在 `gradle.properties` 中）：**

| 属性 | 说明 |
|------|------|
| `release_type` | 发布类型：`release` / `beta` / `alpha` |
| `release_dist` | 发布目标：`client` / `server` / `both` |
| `release_changelog` | 更新日志（支持 `\n` 换行） |
| `modrinth_project_fabric` | Fabric 端 Modrinth 项目 ID |
| `modrinth_project_neoforge` | NeoForge 端 Modrinth 项目 ID |
| `curseforge_project_fabric` | Fabric 端 CurseForge 项目 ID |
| `curseforge_project_neoforge` | NeoForge 端 CurseForge 项目 ID |

**环境变量要求：**

- `MODRINTH_TOKEN`：Modrinth 发布 Token
- `CURSEFORGE_TOKEN`：CurseForge 发布 Token
- `SIGHS_PUBLISH_USER` / `SIGHS_PUBLISH_PASSWORD`：Maven 私有仓库凭证（可选）

所有发布任务在缺少对应 Token 或项目 ID 时会自动跳过。