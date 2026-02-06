[app]

title = VelWallet
package.name = velwallet
package.domain = velcoin.vlc

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0

requirements = python3,kivy,ecdsa,requests,qrcode,pillow

orientation = portrait

fullscreen = 0

log_level = 2


# ---------- Android ----------

android.permissions = INTERNET

android.api = 31
android.minapi = 21
android.ndk_api = 21

android.archs = arm64-v8a,armeabi-v7a

android.debug_artifact = apk

android.allow_backup = True

android.accept_sdk_license = True


# ---------- Build behavior ----------

warn_on_root = 0


# ---------- Python for Android ----------

p4a.branch = master


# ---------- Packaging ----------

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png


# ---------- Excludes ----------

source.exclude_exts = spec
source.exclude_dirs = tests,bin,.git,__pycache__


# ---------- Kivy ----------

osx.kivy_version = 2.2.1
