[app]

title = Ping Test
package.name = pingtest
package.domain = org.kastorsky

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 0

android.permissions = INTERNET

android.accept_sdk_license = True
android.api = 34
android.minapi = 24
android.sdk = 34
android.ndk = 28c
android.build_tools_version = 34.0.0