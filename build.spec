# -*- mode: python ; coding: utf-8 -*-
import os

sm_src = os.path.join(
    SPECPATH, 'venv', 'Lib', 'site-packages',
    'selenium', 'webdriver', 'common', 'windows', 'selenium-manager.exe'
)
sm_dst = os.path.join('selenium', 'webdriver', 'common', 'windows')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(sm_src, sm_dst)],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'pyperclip',
        'win32clipboard',
        'win32con',
        'pywintypes',
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.aead',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.common.action_chains',
        'selenium.webdriver.common.actions',
        'selenium.webdriver.common.actions.action_builder',
        'selenium.webdriver.common.actions.interaction',
        'selenium.webdriver.common.actions.key_actions',
        'selenium.webdriver.common.actions.key_input',
        'selenium.webdriver.common.actions.mouse_button',
        'selenium.webdriver.common.actions.pointer_actions',
        'selenium.webdriver.common.actions.pointer_input',
        'selenium.webdriver.common.actions.wheel_actions',
        'selenium.webdriver.common.actions.wheel_input',
        'selenium.webdriver.remote',
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.remote.webelement',
        'selenium.webdriver.remote.command',
        'selenium.webdriver.common.selenium_manager',
        'selenium.webdriver.common.driver_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NaverBlogAutomation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/favicon.ico',
)
