# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import copy_metadata

datas = [('D:\\codespace\\beimeng_workspace\\apps\\temu-auto-publish\\web_panel\\templates', 'web_panel/templates'), ('D:\\codespace\\beimeng_workspace\\apps\\temu-auto-publish\\config', 'config'), ('D:\\codespace\\beimeng_workspace\\apps\\temu-auto-publish\\web_panel\\fields.py', 'web_panel')]
binaries = []
hiddenimports = ['web_panel.api', 'web_panel.service', 'web_panel.cli', 'src.workflows.complete_publish_workflow', 'itsdangerous']
datas += copy_metadata('playwright')
datas += copy_metadata('playwright_stealth')
hiddenimports += collect_submodules('src')
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('playwright_stealth')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:\\codespace\\beimeng_workspace\\apps\\temu-auto-publish\\start_web_panel_entry.py'],
    pathex=['D:\\codespace\\beimeng_workspace', 'D:\\codespace\\beimeng_workspace\\apps\\temu-auto-publish', 'D:\\codespace\\beimeng_workspace\\apps\\temu-auto-publish\\src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TemuWebPanel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
