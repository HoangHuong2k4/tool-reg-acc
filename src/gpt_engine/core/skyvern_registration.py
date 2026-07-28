from __future__ import annotations
import typing
# -*- coding: utf-8 -*-
"""Skyvern 云端浏览器注册入口。"""

from pathlib import Path

from core.browser_use_registration import run_browser_use_registration


def run_skyvern_registration(
    email: str,
    name: str,
    birthday: str,
    proxy: typing.Union[str, None] = None,
    otp_code: typing.Union[str, None] = None,
    batch_dir: typing.Union[Path, None] = None,
) -> dict:
    return run_browser_use_registration(
        email=email,
        name=name,
        birthday=birthday,
        proxy=proxy,
        otp_code=otp_code,
        batch_dir=batch_dir,
        cloud_provider="skyvern",
    )
