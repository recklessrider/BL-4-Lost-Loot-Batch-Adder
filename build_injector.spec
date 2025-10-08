# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller Spec file for Lost Loot Injector
# This is configured for zero-dependency distribution (no installation required by user).

from PyInstaller.utils.hooks import collect_data_files

# --- Dependency Collection ---
# The primary solution for Cryptodome (Crypto) is relying on PyInstaller's
# built-in hook to detect the required files when blcrypt.py is imported.
yaml_datas = collect_data_files('yaml')

# --- Analysis ---
a = Analysis(
    ['lost_loot_injector.pyw'],  # <-- Target the main GUI script
    pathex=[],
    binaries=[],
    datas=yaml_datas,
    hiddenimports=['blcrypt'],  # <-- Ensure blcrypt.py is bundled
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=None)

# --- Executable Configuration ---
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.datas,
          [],
          name='LostLootInjector',
          debug=False,
          console=False,  # <-- Hides the command-line window
          strip=False,
          upx=False,  # <--- CRITICAL: Set to False to prevent AV false positives (results in a larger file)
          runtime_tmpdir=None,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
