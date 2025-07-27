

import os
import jwt
import time
import httpx
import asyncio

from dotenv import load_dotenv
from langgraph_sdk import Auth
from msal import ConfidentialClientApplication, SerializableTokenCache
from backend.secrets import load_token_cache_from_cosmos, get_cosmos_container

# Load environment variables
load_dotenv(override=True)

# Azure AD (Microsoft Entra ID) config
AAD_TENANT_ID = os.environ["AAD_TENANT_ID"]
AAD_CLIENT_ID = os.environ["AAD_CLIENT_ID"]
AAD_APPLICATION_URI = os.environ["AAD_APPLICATION_URI"]
AAD_CLIENT_SECRET = os.environ["AAD_CLIENT_SECRET"]
AAD_AUTHORITY = f"https://login.microsoftonline.com/{AAD_TENANT_ID}"
AAD_REDIRECT_URI = os.environ["AAD_REDIRECT_URI"]  # e.g., "http://localhost:8000/auth/callback"

# For verifying id_token
AAD_ISSUER = f"https://login.microsoftonline.com/{AAD_TENANT_ID}/v2.0"
AAD_JWKS_URL = f"https://login.microsoftonline.com/{AAD_TENANT_ID}/discovery/v2.0/keys"
_jwks_cache = None

# Initialize MSAL app
token_cache = SerializableTokenCache()
msal_app = ConfidentialClientApplication(
    client_id=AAD_CLIENT_ID,
    client_credential=AAD_CLIENT_SECRET,
    authority=AAD_AUTHORITY,
    token_cache=token_cache
)



# Initialize auth handler (following documentation pattern exactly)
auth = Auth()

## ------------------------------------------------------------------------------------------------
## AUTHENTICATION AND AUTHORIZATION TO OUR GRAPH
## ------------------------------------------------------------------------------------------------

# Authenticates user to our Graph using Azure AD as our IDP
@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    # Handle both string and bytes header keys
    access_token = headers.get("azure-access-token") or headers.get(b"azure-access-token")
    id_token = headers.get("azure-id-token") or headers.get(b"azure-id-token")
    
    if not access_token or not id_token:
        raise ValueError(f"❌ LangGraph Auth Error: Missing tokens. access_token: {bool(access_token)}, id_token: {bool(id_token)}")
    
    try:
        # For Azure AD v2, the audience is typically the client ID (GUID)
        await validate_access_token(access_token, AAD_CLIENT_ID, AAD_ISSUER, AAD_JWKS_URL)

        # Validate the id_token
        id_claims = await verify_id_token(id_token)
        # Optionally, extract oid and tid for further use
        oid = id_claims.get("oid")
        tid = id_claims.get("tid")
        if not oid or not tid:
            raise ValueError("❌ LangGraph Auth Error: id_token missing 'oid' or 'tid' claim")
        

        user_id = f"{oid}.{tid}"
        return {
            "identity": user_id,
            "email": id_claims.get("email"),
            "display_name": id_claims.get("name"),
            "__user_access_token": access_token,
        }
    except Exception as e:
        raise ValueError(f"❌ LangGraph Auth Error: {str(e)}")


# Authorization handler for our Graph
@auth.on
async def add_owner(ctx: Auth.types.AuthContext, value: dict) -> dict:
    """
    Authorization handler for all resources (assistants, threads, runs, etc).
    
    When disable_studio_auth is true, this handler is REQUIRED to allow
    LangGraph Studio to access internal resources like assistants.
    """
    # For assistants endpoint, we may not have a value dict
    # or it might be None for list operations
    if value is None:
        # For list/search operations, just return filter
        return {"owner": ctx.user.identity}
    
    # Add owner metadata to new resources
    filters = {"owner": ctx.user.identity}
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)
    
    # Return filter to restrict access to user's own resources
    # This ensures users can only see/access their own data
    return filters

# Export the auth object for use in langgraph.json
__all__ = ["auth"]



## ------------------------------------------------------------------------------------------------
## AAD TOKEN VALIDATION HELPERS
## ------------------------------------------------------------------------------------------------

async def get_azure_public_keys():
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(AAD_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache = resp.json()["keys"]
        return _jwks_cache

def get_signing_key(jwks, kid):
    for key in jwks:
        if key["kid"] == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    raise Exception("Public key not found for kid: " + kid)

async def verify_id_token(id_token):
    # Decode header to get kid
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header["kid"]
    # Get public keys and find the right one
    jwks = await get_azure_public_keys()
    public_key = get_signing_key(jwks, kid)
    # Now decode and verify
    payload = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=AAD_CLIENT_ID,
        issuer=AAD_ISSUER,
        options={"verify_exp": True, "verify_aud": True, "verify_iss": True}
    )
    return payload

# Helper: Validate an access token (for Graph or your app)
async def validate_access_token(token, audience, issuer, jwks_url):
    # Get unverified header to find kid
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header["kid"]
    # Fetch JWKS
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        jwks = resp.json()["keys"]
        public_key = None
        for key in jwks:
            if key["kid"] == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
        if not public_key:
            raise Exception("Public key not found for kid: " + kid)
        # Validate
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"verify_exp": True, "verify_aud": True, "verify_iss": True}
        )
        return payload


## ------------------------------------------------------------------------------------------------
## AUTHENTICATION AND AUTHORIZATION TO AAD RESOURCES
## ------------------------------------------------------------------------------------------------

# Acquire a token for a downstream resource (e.g., Microsoft Graph) using the user's access token (OBO flow).
def acquire_obo_token(user_token: str, scopes: list[str]) -> str:
    """
    Acquire a token for a downstream resource (e.g., Microsoft Graph) using the user's access token (OBO flow).
    """
    result = msal_app.acquire_token_on_behalf_of(user_assertion=user_token, scopes=scopes)
    if "access_token" not in result:
        raise Exception(f"❌ OBO Token Error: {result.get('error_description', result)}")
    obo_token = result["access_token"]
    return obo_token


# Get Azure access token to a given Azure resource, 
async def get_refreshed_azure_tokens(token_info, scopes):
    """Get a valid access token for defined Azure scopes."""
    access_token, id_token, refresh_token = await get_stored_azure_tokens(token_info, scopes)
    if access_token and id_token:
        return access_token, id_token
    elif token_info.get("account"):
        # Use acquire_token_silent which automatically handles refresh if needed
        # Wrap the blocking MSAL call in asyncio.to_thread
        result = await asyncio.to_thread(
            msal_app.acquire_token_silent,
            scopes=scopes,
            account=token_info["account"]
        )
        if "access_token" in result and "id_token" in result:
            return result["access_token"], result["id_token"]
        else:
            raise Exception(f"❌ Token Refresh Error: {result.get('error_description', 'Unknown error')}")
    else:
        raise Exception("❌ Token Refresh Error: Login is required to get access token")


# Get Azure access token to a given Azure resource, or refresh token if needed.
# Returns (access_token, id_token, refresh_token)
# token_info is the output of extract_info_from_cache
async def get_stored_azure_tokens(token_info, scopes):
    """Get an access token, id token, and refresh token for a given Azure resource."""
    now = int(time.time())
    for i, token in enumerate(token_info.get("access_tokens", [])):
        targets = token.get("target", "").split()

        # Filter out OpenID scopes when checking access token targets
        # OpenID scopes like 'email', 'profile', 'openid' are handled in ID token claims
        resource_scopes = [scope for scope in scopes if not scope in ['email', 'profile', 'openid']]
        
        # Check if all resource scopes are present in the token's targets
        if all(scope in targets for scope in resource_scopes):
            home_account_id = token.get("home_account_id")
            client_id = token.get("client_id")
            realm = token.get("realm")
            expires_on = int(token.get("expires_on", "0"))

            compatible_refresh_token = None
            for rt in token_info.get("refresh_tokens", []):
                if rt.get("home_account_id") == home_account_id and rt.get("client_id") == client_id and rt.get("realm") == realm:
                    compatible_refresh_token = rt["secret"]
                    break
                        
            if expires_on > now:
                matching_id_token = None
                for id_token in token_info.get("id_tokens", []):
                    if (id_token.get("home_account_id") == home_account_id and 
                        id_token.get("client_id") == client_id and
                        id_token.get("realm") == realm):
                        # Check if ID token is not expired using our verify helper
                        try:
                            # Use our existing verify_id_token helper to check expiration
                            await verify_id_token(id_token["secret"])
                            matching_id_token = id_token["secret"]
                            break
                        except Exception as e:
                            print(f"🔍 ID token expired or invalid: {e}")
                            continue
                if matching_id_token:
                    return token["secret"], matching_id_token, None  # Valid access token with matching ID token
                elif compatible_refresh_token:
                    return None, None, compatible_refresh_token
                return None, None, None
            else:
                if compatible_refresh_token:
                    return None, None, compatible_refresh_token
                return None, None, None
        else:
            print(f"❌ Retrieving Stored Tokens: Scope mismatch in candidate")
    print(f"❌ Retrieving Stored Tokens: No valid tokens found")
    return None, None, None

# Helper: Get sensitive token info from Cosmos DB cache
async def extract_info_from_cache(user_id, cosmos_container):
    """
    Loads and deserializes the MSAL token cache for the given user_id from Cosmos DB.
    Returns a dict with access_token, refresh_token, id_token, and their claims if available.
    user_id should be 'oid.tid'.
    """
    await load_token_cache_from_cosmos(token_cache, cosmos_container, user_id)
    
    # The cache is now loaded; extract tokens
    all_accounts = token_cache.find("Account")
    if not all_accounts:
        return None
        
    # Parse oid and tid from user_id
    try:
        oid, tid = user_id.split(".")
    except Exception:
        return None
        
    # Find the matching account
    matching_account = None
    for account in all_accounts:
        # Use the correct MSAL field names
        if account.get("local_account_id") == oid and account.get("realm") == tid:
            matching_account = account
            break
            
    if not matching_account:
        print(f"❌ Extracting Cache: No matching account found")
        return None
        
    # Find tokens for this account
    home_account_id = matching_account.get("home_account_id")
    access_tokens = [t for t in token_cache.find("AccessToken") if t.get("home_account_id") == home_account_id]
    id_tokens = [t for t in token_cache.find("IdToken") if t.get("home_account_id") == home_account_id]
    refresh_tokens = [t for t in token_cache.find("RefreshToken") if t.get("home_account_id") == home_account_id]

    return {
        "account": matching_account,
        "access_tokens": access_tokens,
        "id_tokens": id_tokens,
        "refresh_tokens": refresh_tokens
    }