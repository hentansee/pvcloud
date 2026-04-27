[app]

# 应用基本信息
title = 光伏智云管理系统
package.name = pvcloud
package.domain = org.pvcloud
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json

# 主入口（Kivy 版）
entrypoint = main_kivy.py

version = 1.0.0

# 依赖包（Android 环境下需要的 Python 包）
requirements = python3,kivy,plyer

# Android 权限
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET,CAMERA

# Android API 版本（建议 30+）
android.minapi   = 21
android.ndk      = 25b
android.sdk      = 33
android.api      = 33

# 架构（支持 64 位）
android.archs    = arm64-v8a, armeabi-v7a

# 允许安装在 SD 卡
android.allow_backup = True

# 不自动添加以下权限
android.add_compile_options = "sourceCompatibility = JavaVersion.VERSION_1_8"

# 屏幕方向（portrait=竖屏，landscape=横屏，sensor=随设备）
orientation = portrait

# 是否全屏
fullscreen = 0

# 图标（可替换为自定义图标，放置在 assets/ 目录）
# icon.filename = %(source.dir)s/assets/icon.png

# 启动图（可选）
# presplash.filename = %(source.dir)s/assets/presplash.png
# presplash.color = #0969da

# iOS（暂不需要）
[buildozer]

# Buildozer 日志级别：0=错误，1=一般，2=详细
log_level = 2

# 是否警告非标准 Python 包
warn_on_root = 1

# 编译缓存路径
# build_dir = ./.buildozer

# 构建产物输出目录
# bin_dir = ./bin
