import asyncio
import httpx
from email.utils import formatdate
import contextvars
import os

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from backend.auth import acquire_obo_token, msal_app, AAD_REDIRECT_URI

# Context variable for OBO token
_obo_token_ctx = contextvars.ContextVar("obo_token")

def get_current_obo_token() -> str:
    return _obo_token_ctx.get(None)

def set_request_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

def azure_tool(scopes):
    def decorator(func):
        from functools import wraps
        @tool
        @wraps(func)
        async def async_wrapper(config: RunnableConfig, *args, **kwargs):
            user_info = config.get("configurable", {}).get("langgraph_auth_user", {})
            user_token = user_info.get("user_access_token")
            if not user_token:
                return "❌ No user access token found. Please log in again."
            try:
                obo_token = await asyncio.to_thread(acquire_obo_token, user_token, scopes)
            except Exception as e:
                if "AADSTS65001" in str(e):
                    url = msal_app.get_authorization_request_url(
                        scopes=scopes,
                        redirect_uri=AAD_REDIRECT_URI,
                        prompt="consent"
                    )
                    return (
                        f"❌ The user needs to grant additional permissions. "
                        f"Please tell them to click this link to authorize: {url}"
                    )
                return f"❌ Failed to acquire delegated token: {str(e)}"
            token_token = _obo_token_ctx.set(obo_token)
            try:
                return await func(config, *args, **kwargs)
            finally:
                _obo_token_ctx.reset(token_token)
        return async_wrapper
    return decorator


@azure_tool(scopes=["User.Read"])
async def get_user_profile(config: RunnableConfig) -> str:
    """
    Get the user's profile information from Microsoft Graph (displayName, email, jobTitle).
    """
    obo_token = get_current_obo_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers=set_request_headers(obo_token)
        )
        if response.status_code == 200:
            profile = response.json()
            display_name = profile.get("displayName", "N/A")
            email = profile.get("mail", profile.get("userPrincipalName", "N/A"))
            job_title = profile.get("jobTitle", "N/A")
            return f"Name: {display_name}\nEmail: {email}\nJob Title: {job_title}"
        else:
            return f"Failed to fetch profile: {response.status_code} - {response.text}"


@azure_tool(scopes=["https://management.azure.com/.default"])
async def list_resource_groups(config: RunnableConfig, subscription_id: str) -> str:
    """
    List all resource groups in the user's Azure subscription using delegated OBO access.
    """
    obo_token = get_current_obo_token()
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resourcegroups?api-version=2021-04-01"
    headers = {
        "Authorization": f"Bearer {obo_token}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            groups = response.json().get("value", [])
            if not groups:
                return "No resource groups found in this subscription."
            summary = "Resource groups in your subscription:\n\n"
            for g in groups:
                summary += f"- {g.get('name')}\n"
            return summary
        else:
            return f"Failed to list resource groups: {response.status_code} - {response.text}"


@azure_tool(scopes=["https://management.azure.com/.default"])
async def list_subscriptions(config: RunnableConfig) -> str:
    """
    List all Azure subscriptions the user has access to using delegated OBO access.
    """
    obo_token = get_current_obo_token()
    url = "https://management.azure.com/subscriptions?api-version=2021-01-01"
    headers = {
        "Authorization": f"Bearer {obo_token}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            subs = response.json().get("value", [])
            if not subs:
                return "No subscriptions found for this user."
            summary = "Azure subscriptions you have access to:\n\n"
            for s in subs:
                summary += f"- {s.get('displayName')} (ID: {s.get('subscriptionId')})\n"
            return summary
        else:
            return f"Failed to list subscriptions: {response.status_code} - {response.text}"
