import os

spec_path = 'buildozer.spec'

with open(spec_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'title = My Application',
    'title = Ping Test'
)

content = content.replace(
    'package.name = myapp',
    'package.name = pingtest'
)

content = content.replace(
    'package.domain = org.test',
    'package.domain = org.kastorsky'
)

content = content.replace(
    'requirements = python3,kivy',
    'requirements = python3,kivy==2.3.0'
)

content = content.replace(
    '#android.permissions = INTERNET',
    'android.permissions = INTERNET'
)

content = content.replace(
    '#android.archs = arm64-v8a, armeabi-v7a',
    'android.archs = arm64-v8a'
)

with open(spec_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated buildozer.spec successfully!")