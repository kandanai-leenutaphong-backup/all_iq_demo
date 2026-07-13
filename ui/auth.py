"""Generic MSAL device-code sign-in widget, used for Work IQ.

Mirrors the pattern in ../../workiq-demo/streamlit_app.py (same app
registration) but trimmed down to just what the unified chat page needs: an
access token to hand to the orchestrator's /chat endpoint.

Web IQ no longer uses this — it's API-key-only via the orchestrator (see
backend/sources/web_iq.py), since live probing confirmed there's no working
REST route that accepts a raw API key, and the user opted to skip sign-in
for Web IQ entirely rather than complete delegated auth.
"""

import time

import httpx
import msal
import streamlit as st

from backend import config


def _msal_app() -> msal.PublicClientApplication:
    if "msal_cache" not in st.session_state:
        st.session_state.msal_cache = msal.SerializableTokenCache()
    return msal.PublicClientApplication(
        config.AZURE_CLIENT_ID, authority=config.AUTHORITY,
        token_cache=st.session_state.msal_cache,
    )


def _poll_once(device_code: str, scopes: list[str]) -> tuple[dict, str]:
    token_url = f"{config.AUTHORITY}/oauth2/v2.0/token"
    try:
        r = httpx.post(token_url, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": config.AZURE_CLIENT_ID,
            "device_code": device_code,
            "scope": " ".join(scopes),
        }, timeout=15)
        data = r.json() if r.content else {}
    except Exception as exc:
        return {"error": str(exc)}, "error"

    if r.status_code == 200 and "access_token" in data:
        return data, "success"
    err = data.get("error", "")
    if err == "authorization_pending":
        return data, "pending"
    if err == "slow_down":
        return data, "slow"
    return data, "error"


def is_authenticated(session_key: str) -> bool:
    return bool(st.session_state.get(session_key))


def sign_in_widget(key: str, scopes: list[str], label: str, session_key: str) -> None:
    """Renders a device-code sign-in button/flow for `label`, storing the
    resulting access token in `st.session_state[session_key]`. No-op once
    that session key is already populated.

    `key` namespaces this widget's own session-state bookkeeping (flow,
    status, poll count) so multiple sign-in widgets can coexist on one page.
    """
    if is_authenticated(session_key):
        return

    status = st.session_state.get(f"{key}_status")

    if status is None:
        if st.button(f"Sign in — {label}", key=f"btn_{key}", use_container_width=True):
            with st.spinner("Generating sign-in code…"):
                flow = _msal_app().initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                st.error(f"Device flow failed: {flow.get('error_description', flow)}")
                return
            st.session_state[f"{key}_flow"] = flow
            st.session_state[f"{key}_interval"] = max(flow.get("interval", 5), 3)
            st.session_state[f"{key}_polls"] = 0
            st.session_state[f"{key}_status"] = "polling"
            st.rerun()
        return

    flow = st.session_state.get(f"{key}_flow", {})
    interval = st.session_state.get(f"{key}_interval", 5)

    st.info(
        f"**{label} — Sign in**\n\n"
        f"1. Open **{flow.get('verification_uri', 'https://microsoft.com/devicelogin')}**  \n"
        f"2. Enter code: &nbsp; **`{flow.get('user_code', '')}`**"
    )

    if status == "polling":
        polls = st.session_state[f"{key}_polls"]
        if polls > 180:
            st.error("Sign-in timed out after ~15 minutes. Click Sign in to retry.")
            st.session_state[f"{key}_status"] = None
            return

        col_a, col_b = st.columns([3, 1])
        col_a.caption(f"⏳ Waiting for you to complete sign-in… (check #{polls + 1})")
        if col_b.button("Cancel", key=f"cancel_{key}"):
            for k in [f"{key}_flow", f"{key}_status", f"{key}_polls", f"{key}_interval"]:
                st.session_state.pop(k, None)
            st.rerun()
            return

        data, kind = _poll_once(flow["device_code"], scopes)
        st.session_state[f"{key}_polls"] = polls + 1

        if kind == "success":
            st.session_state[session_key] = data["access_token"]
            for k in [f"{key}_flow", f"{key}_status", f"{key}_polls", f"{key}_interval"]:
                st.session_state.pop(k, None)
            st.success(f"{label} signed in!")
            st.rerun()
            return

        if kind in {"pending", "slow"}:
            if kind == "slow":
                st.session_state[f"{key}_interval"] = interval + 2
            time.sleep(interval)
            st.rerun()
            return

        st.error(f"Auth failed: {data.get('error_description', data.get('error', 'unknown'))}")
        st.session_state[f"{key}_status"] = None


def is_workiq_authenticated() -> bool:
    return is_authenticated("workiq_token")


def workiq_sign_in_widget() -> None:
    sign_in_widget("wiq", config.WORKIQ_SCOPES, "Work IQ", "workiq_token")
