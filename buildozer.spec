[app]

title = VelWallet
package.name = velwallet
package.domain = velcoin.vlc

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 2.0

requirements = python3,kivy,requests,urllib3,idna,certifi

orientation = portrait
fullscreen = 0
log_level = 2


# ---------- Android permissions ----------

android.permissions = INTERNET


# ---------- Android SDK / NDK ----------

android.api = 31
android.minapi = 21
android.ndk_api = 21
android.archs = arm64-v8a,armeabi-v7a

android.debug_artifact = apk
android.allow_backup = True
android.accept_sdk_license = True


# ---------- Packaging ----------

# Rutas RELATIVAS — compatibles con Docker / GitHub Actions
icon.filename = icon.png
presplash.filename = presplash.png


# ---------- Build behavior ----------

warn_on_root = 0


# ---------- Python for Android ----------

p4a.branch = master


# ---------- Excludes ----------

source.exclude_exts = spec
source.exclude_dirs = tests,bin,.git,__pycache__


# ---------- Kivy ----------

osx.kivy_version = 2.2.1
