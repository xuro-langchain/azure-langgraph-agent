# Azure AD Authentication with LangGraph

This project demonstrates Azure AD (Microsoft Entra ID) authentication integration with LangGraph API, using MSAL for token management and Cosmos DB for persistent token storage.

## Azure AD Configuration

### Important: Token Version Configuration

**You must set the token version to 2 in your Azure AD app manifest:**

1. Go to your Azure AD app registration
2. Navigate to **Manifest**
3. Find the `accessTokenAcceptedVersion` property
4. Set it to `2` (not `null` or `1`)
5. Save the manifest

This ensures that:
- Access tokens use the v2 issuer format: `https://login.microsoftonline.com/{tenant_id}/v2.0`
- ID tokens use the v2 issuer format: `https://login.microsoftonline.com/{tenant_id}/v2.0`

If you don't set this, you'll get v1 tokens with issuer `https://sts.windows.net/{tenant_id}/` which will cause authentication failures.

## Architecture

- **Frontend**: Next.js with TypeScript
- **Backend**: FastAPI with MSAL for Azure AD integration
- **Token Storage**: Cosmos DB for persistent MSAL token cache
- **Authentication**: Custom auth middleware for LangGraph API

## Features

- Azure AD authentication flow with delegated permissions
- Automatic token refresh
- Persistent token storage in Cosmos DB
- Custom authentication for LangGraph API
- Session management with cookies
- Microsoft Graph integration for calendar and profile access
- Delegated access demonstration with RBAC

## Getting Started

1. Configure your Azure AD app registration with token version 2
2. Set up your environment variables
3. Install dependencies: `pip install -r requirements.txt`
4. Start the backend: `python -m uvicorn backend.app:app --reload`
5. Start the frontend: `cd frontend && npm run dev`

## Token Flow

1. User logs in via Azure AD with delegated permissions
2. MSAL exchanges authorization code for tokens (including Microsoft Graph scopes)
3. Tokens are stored in Cosmos DB cache
4. Frontend requests tokens from backend
5. Backend validates tokens and returns them
6. Frontend includes tokens in LangGraph API requests
7. Custom auth middleware validates tokens for LangGraph API access
8. Agent uses delegated tokens to access user's Microsoft Graph data

## Azure AD Configuration

### Required API Permissions

Your Azure AD app registration needs the following delegated permissions:

- **Microsoft Graph**:
  - `Calendars.Read` - Read user's calendar
  - `User.Read` - Read user's profile
- **Your Application**:
  - `access` - Custom scope for your app

### Setting Up Delegated Permissions

1. Go to your Azure AD app registration
2. Navigate to **API permissions**
3. Click **Add a permission**
4. Select **Microsoft Graph** → **Delegated permissions**
5. Add the required permissions listed above
6. Grant admin consent for your organization

## Required Azure AD (Entra ID) App Permissions

To enable delegated access (OBO) to Microsoft Graph, Azure Resource Manager (ARM), or other Azure APIs, you must grant your app registration the appropriate delegated permissions in Entra ID (Azure AD):

### 1. Microsoft Graph
- **Delegated permissions:**
  - `User.Read`
  - `Calendars.Read` (if you want calendar access)
  - Any other Graph permissions your app needs

### 2. Azure Resource Manager (ARM)
- **Delegated permission:**
  - `user_impersonation` for the Azure Service Management API (App ID: `797f4846-ba00-4fd7-ba43-dac1f8f63013`)

### How to Add Permissions
1. Go to [Azure Portal > Azure Active Directory > App registrations](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade).
2. Select your app registration.
3. Go to **API permissions** > **Add a permission**.
4. For Microsoft Graph, choose **Microsoft Graph** > **Delegated permissions** and add the required permissions.
5. For ARM, choose **APIs my organization uses**, search for **Azure Service Management** (App ID: `797f4846-ba00-4fd7-ba43-dac1f8f63013`), select it, then add the **user_impersonation** delegated permission.
6. Click **Add permissions**.
7. (Recommended) Click **Grant admin consent** for your tenant.

**Note:**
- You must grant these permissions before your app can request tokens for these resources via OBO.
- If you add new permissions, it may take a few minutes for changes to propagate.
