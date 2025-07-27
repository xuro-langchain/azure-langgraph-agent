# Azure AD Authentication with LangGraph

This project demonstrates Azure AD (Microsoft Entra ID) authentication integration with LangGraph API, using MSAL for token management and Cosmos DB for persistent token storage.

## Setup

### Environment Variables

1. Create a `.env` file based off the `.env.example` file in the repo. You will fill in these environment variables as you continue setup.

2. Begin by adding the required LangSmith variables to trace application runs to LangSmith.

3. We also use OpenAI models in this application, so add your OpenAI API Key as well.

4. Generate a session secret to store as `SESSION_SECRET` in your env file. You can do this in a bash terminal by running:

    ```bash
    python -c "import secrets; print(secrets.token_urlsafe(32))"
    ```

### Azure Configuration

<details>
<summary>Basics</summary>

1. First, you must get sign up for an Azure account and create a Subscription.
    - [Azure for Students](https://azure.microsoft.com/en-us/free/students) gives you credits for free if you have a school related account.
    - With an account, you should have access to Microsoft Entra ID, and a default tenant should be configured for you.
    - You also should have access to CosmosDB.

</details>

<details>
<summary>Microsoft Entra ID</summary>

1. In the Azure home page search bar, navigate to "Microsoft Entra ID". This should bring you to your default tenant.
    - Record the tenant ID, this is `AAD_TENANT_ID` in your env file

2. In the "Add" button, create a new App Registration
    - This App Registration represents your LangGraph application to Azure. By creating one, you can now let Azure know when your LangGraph application is making requests to Azure for authn/z
    - Give the App Registration any name you want, and make it multitenant
    - Provide a redirect URL for **your frontend**. By default in this repo, this value should be `http://localhost:3000/auth/callback`. However, if you host this frontend at a different URL, it should be `https://<your-domain>/auth/callback`.

3. After creating the App Registration, you should see an Overview page for your app. Note the following for your environment file:
    - Your Application (client) ID - this is `AAD_CLIENT_ID` in your env file
    - Your Application ID URI - this is `AAD_APPLICATION_URI` in your env file

4. In the left hand navigation pane for your App Registration, click "Certificates and Secrets"
    - Create a new Client secret with any name you like
    - Copy the Value - this is `AAD_CLIENT_SECRET` in your env file

5. Click "Manifest" in the left hand navigation pane for your App Registration
    - Set "accessTokenAcceptedVersion": 2
    - Save your changes. This ensures that access tokens and id tokens us the v2 issuer format: `https://login.microsoftonline.com/{tenant_id}/v2.0`
    - If you don't set this, you'll get v1 tokens with issuer `https://sts.windows.net/{tenant_id}/` which will cause authentication failures.

6. Click "API Permissions" in the left hand navigation pane for your App Registration
    - Click *Add a Permission*, select *Microsoft Graph* and *Delegated Permissions*. Add "User.Read"
    - Click *Add a Permission*, select *APIs My Organization Uses* and search for *Azure Resource Manager*
    - Select *Azure Resource Manager* and *Delegated Permissions*. Add "user_impersonation" as a permission
    - These two API permissions allow your LangGraph Application to access Microsoft resources on behalf of a user (delegated access)
    - Specifically, it allows your LangGraph Application to read the user's profile information from Microsoft Graph, and act as that user in managing Azure Resources.
    - Users need to consent before your app will be able to finalize its access - this consent process happens during your LangGraph application's runtime through a pop-up.

8. Click "Expose an API" in the left hand navigation pane for your App Registration
    - Add a scope named "access". Allow admins and users to consent.
    - The display names and descriptions can be whatever you like
    - This represents a resource that you want your LangGraph app to expose - just like how Microsoft Graph exposes user profile information
    - In this case, we are setting an arbitrary scope to represent general access to LangGraph resources (i.e. viewing threads, assistants)
    - You can add more granular scopes and use Azure AD to track which users have permission to access LangGraph resources. See `backend/auth.py:authenticate` and `backend/auth.py:add_owner`.
    - [Helpful Guides](https://langchain-ai.github.io/langgraph/tutorials/auth/resource_auth/) are available on the above process.

</details>

<details>
<summary>CosmosDB</summary>

1. In the Azure home page search bar, navigate to "Azure Cosmos DB".

2. Click "Create" and select Azure Cosmos DB for NoSQL
    - Set "Learning" Workload Type (or higher if you intend to scale)
    - Select your *Azure Subscription* and create a *Resource Group* for your project
    - Proceed with the defaults and create the Azure Cosmos DB Account. You may need to adjust location to successfully create

3. When your resource is ready, go to its Overview page
    - Note the URI - the portion before the ":" is the `COSMOS_URL` in your env file. The portion after the ":" is your `COSMOS_PORT`, and should be by default `443`

4. In the left hand navigation bar, enter the Data Explorer
    - Click *Create New Container* - this will be where your LangGraph application will store sensitive secrets and tokens
    - Create a *new Database* - the name will be `COSMOS_DB` in your env file
    - Create a *Container* - the name will be `COSMOS_CONTAINER` in your env file
    - Create a *Partition Key* - the name **without** the leading slash will be `COSMOS_PARITION_KEY` in your env file
    - Set scaling to manual to limit resource spend and create

5. A [visual reference](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/quickstart-portal) of what the CosmosDB UX may be helpful

</details>

## Architecture

This application consists of:

1. LangGraph Server backend with custom FastAPI routes
    - `backend/agent.py` contains our LangGraph agent
    - `backend/app.py` contains our FastAPI authentication routes
    - `backend/auth.py` contains our LangGraph authentication logic, as well as helpers for our agent to be authorized to access Azure resources
    - `backend/secrets.py` contains logic to store sensitive access tokens in secure CosmosDB storage
    - `backend/tools.py` contains tools that our LangGraph agent can use, with most tools accessing Azure resources that require authorization.

2. Next.js Frontend
    - `frontend/app/auth/callback` contains our frontend callback page. This our Redirect URI we set in Azure, which determines where Azure will send our authorization code after we complete the browser login process. Notably, the Redirect URI must be a frontend route.
    - `frontend/app/page.tsx` represents our main page
    - `frontend/components/Chat.tsx` defines our main Chat component and message logic
    - `frontend/lib/auth.tsx` contains our handlers for calling our backend authentication endpoints to login using OAuth2.0 Auth Code Flow

## Running the Application

### Using the Scripts 

Note: These scripts should be modified in production settings. They will start your application in a development environment. All scripts **MUST** be run from the root directory of this repo.

1. Install dependencies using 
    ```bash
    scripts/install.sh
    ```
2. Start the application frontend and backend using
    ```bash
    scripts/run.sh
    ```
3. A browser window should open to the frontend (default localhost:3000).
4. After finishing usage of your application, shut it down using
    ```bash
    scripts/shutdown.sh
    ``` 

### Manually Running the Application

1. In terminal, start the backend by running:

    ```bash
    langgraph dev
    ```
    in the root directory of this repo. The backend will be available at `localhost:2024`

2. In a separate terminal, start the frontend by running:

    ```bash
    npm run dev
    ```
    in the `frontend` directory of this repo. The frontend will be available at `localhost:3000`

3. Navigate to `localhost:3000` to interact with the application.

NOTE: Starting manually will show the logs in your terminals for live debugging